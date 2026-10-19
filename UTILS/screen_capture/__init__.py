# -*- coding: utf-8 -*-
"""Captura de pantalla — dispatcher por plataforma.

Re-exporta la implementación de `ScreenCaptureBackend` que corresponda según
sys.platform, así UI.py y overlay.py no necesitan saber en qué SO corren:

    screen_capture_linux.py    X11: mss + paplay/aplay + _NET_CLIENT_LIST_STACKING
    screen_capture_windows.py  Win: mss + winsound + EnumWindows/GetWindowRect
    screen_capture_macos.py    Mac: mss + afplay + CGWindowListCopyWindowInfo

API exportada por ambos backends (fachada de funciones sobre el singleton):
    grab_screen()          -> (QImage, offset QPoint)
    play_shutter()         -> None
    window_rect_at(x, y)   -> (QRect, título) | None

En plataformas sin backend propio (otros unix) cae al backend Linux:
mss funciona igual y las piezas X11/audio quedan guardadas y en no-op.
"""

import sys

from UTILS.screen_capture.screen_capture_interface import (   # noqa: F401
    ScreenCaptureBackend)

if sys.platform == "win32":
    from UTILS.screen_capture.screen_capture_windows import (  # noqa: F401
        WindowsScreenCapture, grab_screen, play_shutter, window_rect_at)
elif sys.platform == "darwin":
    from UTILS.screen_capture.screen_capture_macos import (    # noqa: F401
        MacOSScreenCapture, grab_screen, play_shutter, window_rect_at)
else:
    from UTILS.screen_capture.screen_capture_linux import (    # noqa: F401
        LinuxScreenCapture, grab_screen, play_shutter, window_rect_at)
