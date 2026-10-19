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
    hotkeys/              paquete de hotkey global por plataforma:
        hotkey_interface.py        interfaz HotkeyBackend + helpers compartidos
        hotkeys_linux.py           XGrabKey real + fallback pynput
        hotkeys_windows.py         RegisterHotKey + fallback pynput
        __init__.py                dispatcher → HotkeyManager
    screen_capture/       paquete de captura por plataforma:
        screen_capture_interface.py  interfaz ScreenCaptureBackend + wav obturador
        screen_capture_linux.py      backend X11 (mss + paplay/aplay + xlib)
        screen_capture_windows.py    backend Windows (mss + winsound + user32)
        screen_capture_macos.py      backend macOS (mss + afplay + Quartz)
        __init__.py                  dispatcher → grab_screen/play_shutter/...
    system/               paquete de integración con el SO:
        system_interface.py          interfaz SystemBackend
        system_linux.py              XDG paths + autostart .desktop + xdg-open
        system_windows.py            APPDATA + autostart Registry Run + startfile
        system_macos.py              ~/Library + autostart LaunchAgent + open
        __init__.py                  dispatcher → config_dir/open_path/...
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
    from UTILS.qt_compat import BIND
    assert BIND, "sin binding"
except (ImportError, AssertionError) as e:
    print(f"❌ No se pudo importar Qt (PyQt6 ni PySide6): {e}")
    print("   Si faltan paquetes:  pip install -r requirements.txt")
    print("   Si es 'DLL load failed ... directiva de Control de aplicaciones': "
          "Smart App Control / WDAC está bloqueando las DLLs del binding "
          "(Windows Security → App & browser control).")
    sys.exit(1)

from UTILS.UI import main

if __name__ == "__main__":
    main()
