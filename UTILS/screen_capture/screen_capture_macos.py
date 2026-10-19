# -*- coding: utf-8 -*-
"""Implementación macOS de ScreenCaptureBackend.

Detalles de plataforma:
    - captura: mss (requiere permiso de "Grabación de pantalla" desde Catalina)
    - sonido:  wav sintetizado reproducido con afplay (builtin)
    - ventana bajo el cursor: CGWindowListCopyWindowInfo vía pyobjc
      (pyobjc-framework-Quartz, dependencia opcional — sin ella el hover
      de ventanas simplemente devuelve None)

El backend se instancia una sola vez (_backend) y sus métodos se re-exportan
como funciones de módulo para que el dispatcher los use directo.
"""

import os
import shutil
import subprocess

from UTILS.qt_compat.QtCore import QPoint, QRect
from UTILS.qt_compat.QtGui import QImage

from UTILS.config import CACHE_DIR
from UTILS.deps import HAS_QUARTZ, Quartz, mss
from UTILS.screen_capture.screen_capture_interface import (
    ScreenCaptureBackend, make_shutter_wav)


class MacOSScreenCapture(ScreenCaptureBackend):
    """ScreenCaptureBackend para macOS (Quartz/CGWindowList)."""

    def grab_screen(self) -> tuple:
        """Captura TODO el escritorio virtual con mss. → (QImage, offset QPoint)."""
        with mss.MSS() as sct:
            mon = sct.monitors[0]
            shot = sct.grab(mon)
        data = bytes(shot.raw)
        # mss devuelve BGRA → RGB32 fuerza alfa=255 (el 4º byte se ignora).
        img = QImage(data, shot.width, shot.height, shot.width * 4,
                     QImage.Format.Format_RGB32)
        img = img.copy()          # desacoplar del buffer temporal
        return img, QPoint(mon["left"], mon["top"])

    def play_shutter(self) -> None:
        """Sonidito de obturador (wav sintetizado, reproducido con afplay)."""
        wav = CACHE_DIR / "shutter.wav"
        try:
            if not wav.exists():
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                make_shutter_wav(wav)
            if shutil.which("afplay"):
                subprocess.Popen(["afplay", str(wav)],
                                 stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def window_rect_at(self, root_x: int, root_y: int):
        """Ventana más al tope bajo el cursor (coords de pantalla).

        → (QRect, nombre) o None. CGWindowListCopyWindowInfo devuelve las
        ventanas on-screen en orden front-to-back (equivalente al Z-order
        de EnumWindows / _NET_CLIENT_LIST_STACKING al revés). Se filtran:
        nuestras propias ventanas, capas ≠ 0 (dock, menubar, overlays del
        sistema) y rects < 20px."""
        if not HAS_QUARTZ:
            return None
        try:
            opts = (Quartz.kCGWindowListOptionOnScreenOnly |
                    Quartz.kCGWindowListExcludeDesktopElements)
            wins = Quartz.CGWindowListCopyWindowInfo(opts,
                                                     Quartz.kCGNullWindowID)
            own_pid = os.getpid()
            for w in wins or []:
                try:
                    if w.get("kCGWindowLayer", 0) != 0:
                        continue
                    if w.get("kCGWindowOwnerPID") == own_pid:
                        continue
                    b = w.get("kCGWindowBounds", {})
                    r = QRect(int(b.get("X", 0)), int(b.get("Y", 0)),
                              int(b.get("Width", 0)), int(b.get("Height", 0)))
                    if r.width() < 20 or r.height() < 20:
                        continue
                    if r.contains(root_x, root_y):
                        name = (w.get("kCGWindowName")
                                or w.get("kCGWindowOwnerName") or "")
                        return (r, name)
                except Exception:
                    continue
            return None
        except Exception:
            return None


# Singleton + fachada de funciones (misma API que antes del refactor).
_backend = MacOSScreenCapture()
grab_screen = _backend.grab_screen
play_shutter = _backend.play_shutter
window_rect_at = _backend.window_rect_at
