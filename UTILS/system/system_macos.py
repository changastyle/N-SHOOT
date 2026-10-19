# -*- coding: utf-8 -*-
"""Implementación macOS de SystemBackend.

    - rutas:   ~/Library/Application Support (config) / ~/Library/Caches
    - autostart: LaunchAgent — plist en ~/Library/LaunchAgents con RunAtLoad
    - abrir:   open
"""

import os
import plistlib
import subprocess
import sys
from pathlib import Path

from UTILS.system.system_interface import SystemBackend


def _label(name: str) -> str:
    """"Screenshot Tool" → "com.screenshot-tool" (Label del LaunchAgent)."""
    return "com." + name.lower().replace(" ", "-")


class MacOSSystemBackend(SystemBackend):
    """SystemBackend para macOS (LaunchAgents + plistlib)."""

    def config_dir(self) -> Path:
        return Path.home() / "Library" / "Application Support" / "screenshot-tool"

    def cache_dir(self) -> Path:
        return Path.home() / "Library" / "Caches" / "screenshot-tool"

    def default_save_folder(self) -> Path:
        return Path.home() / "Pictures" / "Screenshots"

    # ----------------------------------------------------------- autostart
    def _plist_path(self, name: str) -> Path:
        return Path.home() / "Library" / "LaunchAgents" / f"{_label(name)}.plist"

    def _program_args(self, entry: Path) -> list:
        """ProgramArguments del plist según cómo corre la app:
        - Frozen (PyInstaller/.app): el propio binario.
        - Dev: python + script."""
        if getattr(sys, "frozen", False):
            exe = os.environ.get("APPIMAGE") or sys.executable
            return [str(Path(exe))]
        return [str(Path(sys.executable)), str(entry)]

    def set_autostart(self, enable: bool, name: str, entry: Path) -> None:
        try:
            path = self._plist_path(name)
            if enable:
                path.parent.mkdir(parents=True, exist_ok=True)
                plist = {
                    "Label": _label(name),
                    "ProgramArguments": self._program_args(entry),
                    "RunAtLoad": True,
                }
                path.write_bytes(plistlib.dumps(plist))
            else:
                if path.exists():
                    path.unlink()
        except Exception:
            pass

    def autostart_enabled(self, name: str) -> bool:
        return self._plist_path(name).exists()

    # -------------------------------------------------------------- abrir
    def open_path(self, path) -> None:
        try:
            subprocess.Popen(["open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
