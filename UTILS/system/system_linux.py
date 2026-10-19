# -*- coding: utf-8 -*-
"""Implementación Linux/XDG de SystemBackend.

    - rutas:   XDG_CONFIG_HOME / XDG_CACHE_HOME (~/.config, ~/.cache)
    - autostart: archivo .desktop en ~/.config/autostart
    - abrir:   xdg-open
"""

import os
import subprocess
import sys
from pathlib import Path

from UTILS.system.system_interface import SystemBackend


def _slug(name: str) -> str:
    """"Screenshot Tool" → "screenshot-tool" (nombre del .desktop)."""
    return name.lower().replace(" ", "-")


class LinuxSystemBackend(SystemBackend):
    """SystemBackend para Linux freedesktop (XDG)."""

    def config_dir(self) -> Path:
        return Path(os.environ.get("XDG_CONFIG_HOME",
                                   Path.home() / ".config")) / "screenshot-tool"

    def cache_dir(self) -> Path:
        return Path(os.environ.get("XDG_CACHE_HOME",
                                   Path.home() / ".cache")) / "screenshot-tool"

    def default_save_folder(self) -> Path:
        pictures = "Imágenes" if (Path.home() / "Imágenes").is_dir() else "Pictures"
        return Path.home() / pictures / "Screenshots"

    # ----------------------------------------------------------- autostart
    def _autostart_path(self, name: str) -> Path:
        return Path.home() / ".config" / "autostart" / f"{_slug(name)}.desktop"

    def _exec_line(self, entry: Path) -> str:
        """Comando Exec= para el .desktop según cómo corre la app:
        - AppImage/PyInstaller: el propio binario (env APPIMAGE si existe, que
          es la ruta real del .AppImage; sys.executable apunta al mount temporal).
        - Dev (.venv): python del venv + script, sin resolver el symlink
          (resolve() llevaría a /usr/bin/python3.x, sin las dependencias)."""
        if getattr(sys, "frozen", False):
            exe = os.environ.get("APPIMAGE") or sys.executable
            return str(Path(exe))
        return f"{Path(sys.executable)} {entry}"

    def set_autostart(self, enable: bool, name: str, entry: Path) -> None:
        try:
            path = self._autostart_path(name)
            if enable:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(
                    "[Desktop Entry]\n"
                    "Type=Application\n"
                    f"Exec={self._exec_line(entry)}\n"
                    "Hidden=false\n"
                    "NoDisplay=false\n"
                    f"Name={name}\n"
                    "Comment=Capturas de pantalla rápidas con hotkey (F10)\n"
                    "Categories=Utility;Graphics;\n",
                    encoding="utf-8")
            else:
                if path.exists():
                    path.unlink()
        except Exception:
            pass

    def autostart_enabled(self, name: str) -> bool:
        return self._autostart_path(name).exists()

    # -------------------------------------------------------------- abrir
    def open_path(self, path) -> None:
        try:
            subprocess.Popen(["xdg-open", str(path)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
