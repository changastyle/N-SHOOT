#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
📷 Screenshot Tool — capturas de pantalla estilo GreenShot (pero mejor)
para Linux Mint / Cinnamon.

Flow:  F10 (configurable)  →  pantalla congelada  →  arrastrás el área
       →  crop  →  guardar (JPEG/PNG)  →  copiar al portapapeles
       + toast + preview flotante + sonido de obturador.

Se ejecuta en segundo plano con icono en el tray.
Diseñado para X11 (Cinnamon), con grab real de teclado vía XGrabKey.

El código vive en UTILS/:
    deps.py               dependencias opcionales (mss, xlib, pynput)
    config.py             rutas, config persistente y autoarranque
    hotkeys.py            hotkey global (XGrabKey real + fallback pynput)
    capture.py            captura de pantalla, sonido, ventana bajo el cursor
    overlay.py            overlay de selección + toast + preview flotante
    preferences.py        diálogo de preferencias
     UI.py                 app principal (tray, capturas, guardado)
"""

import sys
from pathlib import Path

# Poder hacer "import UTILS.xxx" sin depender del cwd:
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Qt 6.5+ necesita libxcb-cursor para el plugin xcb. Si el sistema no la tiene,
# usamos una copia local en ~/.local/lib/screenshot-tool. Debe cargarse ANTES
# de crear QApplication (el plugin xcb se inicializa ahí).
try:
    import ctypes
    _local_lib = Path.home() / ".local" / "lib" / "screenshot-tool" / "libxcb-cursor.so.0"
    if _local_lib.exists():
        ctypes.CDLL(str(_local_lib), mode=ctypes.RTLD_GLOBAL)
except Exception:
    pass

try:
    from PyQt6 import QtCore, QtGui, QtNetwork, QtWidgets  # noqa: F401
except ImportError:
    print("❌ Faltan dependencias. Instalá con:  pip install PyQt6 mss pynput python-xlib")
    sys.exit(1)

from UTILS.UI import main

if __name__ == "__main__":
    main()
