# -*- coding: utf-8 -*-
"""Detección de dependencias opcionales de Screenshot Tool.

- mss          → captura de pantalla (grab_screen)
- python-xlib  → grab real de hotkey (XGrabKey) + detección de ventanas
- pynput       → fallback de hotkey global (sin supresión de tecla)

Si una falta, queda en None y HAS_* = False; el código que la usa
está siempre detrás de un guard.
"""

try:
    import mss
    HAS_MSS = True
except Exception:
    mss = None
    HAS_MSS = False

try:
    from Xlib import X, XK
    from Xlib import display as xlib_display
    HAS_XLIB = True
except Exception:
    X = XK = xlib_display = None
    HAS_XLIB = False

try:
    from pynput import keyboard as pkb
    HAS_PYNPUT = True
except Exception:
    pkb = None
    HAS_PYNPUT = False
