# -*- coding: utf-8 -*-
"""Hotkey global — dispatcher por plataforma.

Re-exporta la implementación de `HotkeyBackend` que corresponda según
sys.platform, con el alias estable `HotkeyManager` que usa UI.py:

    hotkeys_linux.py    X11: XGrabKey real + fallback pynput
    hotkeys_windows.py  Win: RegisterHotKey + fallback pynput
    hotkeys_macos.py    Mac: Carbon RegisterEventHotKey + fallback pynput

API pública (compatible con el viejo UTILS/hotkeys.py):
    HotkeyManager(combo)   gestor listo: .triggered / .failed / .start() / .stop()
    normalize_hotkey()     "Ctrl+Alt+P" → (mods, key)
    hotkey_display()       "Ctrl+Alt+P" → texto para UI
    _QT_TO_MOD             mapa Qt.Modifier → nombre de modificador
"""

import sys

from UTILS.hotkeys.hotkey_interface import (HotkeyBackend,          # noqa: F401
                                            PynputFallbackListener,
                                            normalize_hotkey,
                                            hotkey_display,
                                            _QT_TO_MOD, _QTKEY_SPECIAL)

if sys.platform == "win32":
    from UTILS.hotkeys.hotkeys_windows import WindowsHotkeyManager as HotkeyManager
elif sys.platform == "darwin":
    from UTILS.hotkeys.hotkeys_macos import MacOSHotkeyManager as HotkeyManager
else:
    from UTILS.hotkeys.hotkeys_linux import LinuxHotkeyManager as HotkeyManager
