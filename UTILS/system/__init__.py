# -*- coding: utf-8 -*-
"""Integración con el SO — dispatcher por plataforma.

Re-exporta la implementación de `SystemBackend` que corresponda según
sys.platform como un singleton `backend` + fachada de funciones:

    system_linux.py    XDG paths + autostart .desktop + xdg-open
    system_windows.py  APPDATA + autostart Registry Run + os.startfile
    system_macos.py    ~/Library + autostart LaunchAgent + open

API exportada:
    config_dir() / cache_dir() / default_save_folder()  -> Path
    set_autostart(enable, name, entry) / autostart_enabled(name)
    open_path(path)
"""

import sys

from UTILS.system.system_interface import SystemBackend          # noqa: F401

if sys.platform == "win32":
    from UTILS.system.system_windows import WindowsSystemBackend as _Impl
elif sys.platform == "darwin":
    from UTILS.system.system_macos import MacOSSystemBackend as _Impl
else:
    from UTILS.system.system_linux import LinuxSystemBackend as _Impl

backend = _Impl()

# Fachada de funciones (mismo patrón que UTILS/screen_capture).
config_dir = backend.config_dir
cache_dir = backend.cache_dir
default_save_folder = backend.default_save_folder
set_autostart = backend.set_autostart
autostart_enabled = backend.autostart_enabled
open_path = backend.open_path
