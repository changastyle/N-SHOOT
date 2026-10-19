# -*- coding: utf-8 -*-
"""Implementación Linux/X11 de ScreenCaptureBackend.

Detalles de plataforma:
    - captura: mss (BGRX → QImage RGB32)
    - sonido:  wav sintetizado reproducido con paplay/aplay
    - ventana bajo el cursor: _NET_CLIENT_LIST_STACKING vía python-xlib

El backend se instancia una sola vez (_backend) y sus métodos se re-exportan
como funciones de módulo para que el dispatcher los use directo.
"""

import shutil
import subprocess

from UTILS.qt_compat.QtCore import QPoint, QRect
from UTILS.qt_compat.QtGui import QImage

from UTILS.config import CACHE_DIR
from UTILS.deps import HAS_XLIB, X, mss, xlib_display
from UTILS.screen_capture.screen_capture_interface import (
    ScreenCaptureBackend, make_shutter_wav)


class LinuxScreenCapture(ScreenCaptureBackend):
    """ScreenCaptureBackend para X11 (Cinnamon y cualquier WM con EWMH)."""

    def grab_screen(self) -> tuple:
        """Captura TODO el escritorio virtual con mss. → (QImage, offset QPoint)."""
        with mss.MSS() as sct:
            mon = sct.monitors[0]
            shot = sct.grab(mon)
        data = bytes(shot.raw)
        # mss devuelve BGRX con alfa=0 → ARGB32 quedaría totalmente transparente.
        # RGB32 fuerza alfa=255 (el 4º byte se ignora).
        img = QImage(data, shot.width, shot.height, shot.width * 4,
                     QImage.Format.Format_RGB32)
        img = img.copy()          # desacoplar del buffer temporal
        return img, QPoint(mon["left"], mon["top"])

    def play_shutter(self) -> None:
        """Sonidito de obturador (wav sintetizado, reproducido con paplay/aplay)."""
        wav = CACHE_DIR / "shutter.wav"
        try:
            if not wav.exists():
                CACHE_DIR.mkdir(parents=True, exist_ok=True)
                make_shutter_wav(wav)
            for player in ("paplay", "aplay"):
                if shutil.which(player):
                    subprocess.Popen([player, str(wav)], stdout=subprocess.DEVNULL,
                                     stderr=subprocess.DEVNULL)
                    return
        except Exception:
            pass

    def window_rect_at(self, root_x: int, root_y: int):
        """Ventana más al tope bajo el cursor (coords raíz). → (QRect, nombre) o None."""
        if not HAS_XLIB:
            return None
        try:
            disp = xlib_display.Display()
            root = disp.screen().root
            net = disp.intern_atom("_NET_CLIENT_LIST_STACKING")
            prop = root.get_full_property(net, X.AnyPropertyType)
            result = None
            if prop:
                for wid in reversed(prop.value):
                    try:
                        w = disp.create_resource_object("window", wid)
                        if w.get_attributes().map_state != 2:   # IsViewable
                            continue
                        g = w.get_geometry()
                        tl = w.translate_coords(root, 0, 0)
                        r = QRect(tl.x, tl.y, g.width, g.height)
                        if r.width() < 20 or r.height() < 20:
                            continue
                        if r.contains(root_x, root_y):
                            name = ""
                            try:
                                name = (w.get_wm_name() or "") or ""
                            except Exception:
                                name = ""
                            result = (r, name)
                            break
                    except Exception:
                        continue
            disp.close()
            return result
        except Exception:
            return None


# Singleton + fachada de funciones (misma API que antes del refactor).
_backend = LinuxScreenCapture()
grab_screen = _backend.grab_screen
play_shutter = _backend.play_shutter
window_rect_at = _backend.window_rect_at
