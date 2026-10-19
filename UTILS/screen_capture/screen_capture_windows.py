# -*- coding: utf-8 -*-
"""Implementación Windows de ScreenCaptureBackend.

Detalles de plataforma:
    - captura: mss (BGRX/BGRA → QImage RGB32)
    - sonido:  wav sintetizado reproducido con winsound (stdlib)
    - ventana bajo el cursor: EnumWindows en Z-order (equivalente a
      _NET_CLIENT_LIST_STACKING) + GetWindowRect / GetWindowTextW vía ctypes

El backend se instancia una sola vez (_backend) y sus métodos se re-exportan
como funciones de módulo para que el dispatcher los use directo.
"""

import ctypes
import os
import sys
from ctypes import wintypes

from UTILS.qt_compat.QtCore import QPoint, QRect
from UTILS.qt_compat.QtGui import QImage

from UTILS.config import CACHE_DIR
from UTILS.deps import mss
from UTILS.screen_capture.screen_capture_interface import (
    ScreenCaptureBackend, make_shutter_wav)

# ---------------------------------------------------------------------------
# user32 (todas las funciones con argtypes/restype explícitos: sin ellos los
# HWND de 64 bits se truncan a c_int y las ventanas quedan "no encontradas").
# ---------------------------------------------------------------------------
_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND,
                                      wintypes.LPARAM)
    _user32.EnumWindows.argtypes = [_WNDENUMPROC, wintypes.LPARAM]
    _user32.EnumWindows.restype = wintypes.BOOL
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsWindowVisible.restype = wintypes.BOOL
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _user32.IsIconic.restype = wintypes.BOOL
    _user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.GetWindowLongW.restype = wintypes.LONG
    _user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _user32.GetWindowRect.restype = wintypes.BOOL
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextLengthW.restype = ctypes.c_int
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowTextW.restype = ctypes.c_int
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                                 ctypes.POINTER(wintypes.DWORD)]
    _user32.GetWindowThreadProcessId.restype = wintypes.DWORD
    _dwmapi = ctypes.WinDLL("dwmapi", use_last_error=True)
    _dwmapi.DwmGetWindowAttribute.argtypes = [wintypes.HWND, wintypes.DWORD,
                                              ctypes.c_void_p, wintypes.DWORD]
    _dwmapi.DwmGetWindowAttribute.restype = ctypes.c_long   # HRESULT
else:
    _user32 = _dwmapi = None
    _WNDENUMPROC = None

_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x00000080
_DWMWA_CLOAKED = 14   # apps UWP suspendidas quedan "cloaked": visibles pero no dibujadas


class WindowsScreenCapture(ScreenCaptureBackend):
    """ScreenCaptureBackend para Windows (user32/dwmapi vía ctypes)."""

    def grab_screen(self) -> tuple:
        """Captura TODO el escritorio virtual con mss. → (QImage, offset QPoint)."""
        with mss.MSS() as sct:
            mon = sct.monitors[0]
            shot = sct.grab(mon)
        data = bytes(shot.raw)
        # mss devuelve BGRX/BGRA → RGB32 fuerza alfa=255 (el 4º byte se ignora).
        img = QImage(data, shot.width, shot.height, shot.width * 4,
                     QImage.Format.Format_RGB32)
        img = img.copy()          # desacoplar del buffer temporal
        return img, QPoint(mon["left"], mon["top"])

    def play_shutter(self) -> None:
        """Sonidito de obturador (wav sintetizado, reproducido con winsound)."""
        try:
            import winsound
            wav = CACHE_DIR / "shutter.wav"
            if not wav.exists():
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                make_shutter_wav(wav)
            winsound.PlaySound(str(wav),
                               winsound.SND_FILENAME | winsound.SND_ASYNC |
                               winsound.SND_NODEFAULT)
        except Exception:
            pass

    def _is_cloaked(self, hwnd) -> bool:
        """Ventana UWP suspendida/cloaked: IsWindowVisible dice True pero no se dibuja."""
        val = wintypes.DWORD()
        hr = _dwmapi.DwmGetWindowAttribute(hwnd, _DWMWA_CLOAKED,
                                         ctypes.byref(val), ctypes.sizeof(val))
        return hr == 0 and val.value != 0

    def window_rect_at(self, root_x: int, root_y: int):
        """Ventana top-level más al tope bajo el cursor (coords de pantalla).

        → (QRect, título) o None. EnumWindows itera las ventanas top-level en
        Z-order (topmost primero) igual que _NET_CLIENT_LIST_STACKING al revés
        en el backend Linux. Se filtran:
          - nuestras propias ventanas (el overlay cubre TODA la pantalla durante
            la selección: sin este filtro siempre "detectaría" el overlay),
          - tool windows, minimizadas y cloaked (UWP suspendidas)."""
        if not _IS_WIN:
            return None
        found = []
        own_pid = os.getpid()

        def _enum(hwnd, _lparam):
            try:
                if not _user32.IsWindowVisible(hwnd) or _user32.IsIconic(hwnd):
                    return True
                if _user32.GetWindowLongW(hwnd, _GWL_EXSTYLE) & _WS_EX_TOOLWINDOW:
                    return True
                pid = wintypes.DWORD()
                _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                if pid.value == own_pid:
                    return True
                if self._is_cloaked(hwnd):
                    return True
                rect = wintypes.RECT()
                if not _user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                    return True
                r = QRect(rect.left, rect.top,
                          rect.right - rect.left, rect.bottom - rect.top)
                if r.width() < 20 or r.height() < 20 or not r.contains(root_x, root_y):
                    return True
                name = ""
                n = _user32.GetWindowTextLengthW(hwnd)
                if n > 0:
                    buf = ctypes.create_unicode_buffer(n + 1)
                    _user32.GetWindowTextW(hwnd, buf, n + 1)
                    name = buf.value or ""
                found.append((r, name))
                return False   # primera coincidencia en Z-order = topmost
            except Exception:
                return True

        try:
            # ctypes mantiene viva la referencia al callback durante la llamada.
            _user32.EnumWindows(_WNDENUMPROC(_enum), 0)
        except Exception:
            return None
        return found[0] if found else None


# Singleton + fachada de funciones (misma API que antes del refactor).
_backend = WindowsScreenCapture()
grab_screen = _backend.grab_screen
play_shutter = _backend.play_shutter
window_rect_at = _backend.window_rect_at
