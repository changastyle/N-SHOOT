# -*- coding: utf-8 -*-
"""Implementación Windows de SystemBackend.

    - rutas:   %APPDATA% (config) / %LOCALAPPDATA% (caché)
    - autostart: valor en HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
    - abrir:   os.startfile
"""

import os
import sys
from pathlib import Path

from UTILS.system.system_interface import SystemBackend

_IS_WIN = sys.platform == "win32"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def _reg_name(name: str) -> str:
    """"Screenshot Tool" → "ScreenshotTool" (nombre del valor en el Run key)."""
    return name.replace(" ", "")


class WindowsSystemBackend(SystemBackend):
    """SystemBackend para Windows (winreg + shell)."""

    def config_dir(self) -> Path:
        return Path(os.environ.get("APPDATA",
                                   Path.home() / "AppData" / "Roaming")) / "screenshot-tool"

    def cache_dir(self) -> Path:
        return Path(os.environ.get("LOCALAPPDATA",
                                   Path.home() / "AppData" / "Local")) / "screenshot-tool"

    def default_save_folder(self) -> Path:
        return Path.home() / "Pictures" / "N-SHOOT"

    # ----------------------------------------------------------- autostart
    def _command(self, entry: Path) -> str:
        """Comando del valor Run según cómo corre la app:
        - Frozen (PyInstaller): el propio exe.
        - Dev: pythonw.exe (sin consola) + script; si no existe el pythonw
          del venv, cae a python.exe (mostraría consola)."""
        if getattr(sys, "frozen", False):
            return f'"{sys.executable}"'
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        exe = pythonw if pythonw.exists() else Path(sys.executable)
        return f'"{exe}" "{entry}"'

    def set_autostart(self, enable: bool, name: str, entry: Path) -> None:
        if not _IS_WIN:
            return
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                                winreg.KEY_SET_VALUE | winreg.KEY_QUERY_VALUE) as k:
                if enable:
                    winreg.SetValueEx(k, _reg_name(name), 0,
                                      winreg.REG_SZ, self._command(entry))
                else:
                    try:
                        winreg.DeleteValue(k, _reg_name(name))
                    except FileNotFoundError:
                        pass
        except Exception:
            pass

    def autostart_enabled(self, name: str) -> bool:
        if not _IS_WIN:
            return False
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY, 0,
                                winreg.KEY_QUERY_VALUE) as k:
                winreg.QueryValueEx(k, _reg_name(name))
            return True
        except Exception:
            return False

    # -------------------------------------------------------------- abrir
    def open_path(self, path) -> None:
        try:
            os.startfile(str(path))     # noqa: B018 — existe solo en Windows
        except Exception:
            pass
