# -*- coding: utf-8 -*-
"""Interfaz común de integración con el SO (estilo Java: interfaz + impls).

`SystemBackend` define el contrato que cumplen las implementaciones por
plataforma:

    system_linux.py    → LinuxSystemBackend    (XDG + .desktop + xdg-open)
    system_windows.py  → WindowsSystemBackend  (APPDATA + Registry Run + startfile)

El dispatcher UTILS/system/__init__.py instancia el singleton `backend` y
re-exporta sus métodos como funciones sueltas (config_dir(), open_path()...).

Nota de diseño: `set_autostart` recibe `name` y `entry` (script de
arranque) en vez de importar config.py — así se evita el import circular
config → system → config.
"""

from abc import ABC, abstractmethod
from pathlib import Path


class SystemBackend(ABC):
    """Interfaz de integración con el sistema operativo."""

    @abstractmethod
    def config_dir(self) -> Path:
        """Directorio de configuración persistente de la app."""
        ...

    @abstractmethod
    def cache_dir(self) -> Path:
        """Directorio de caché (wav de obturador, temporales)."""
        ...

    @abstractmethod
    def default_save_folder(self) -> Path:
        """Carpeta de capturas por defecto (~/Pictures/Screenshots o similar)."""
        ...

    @abstractmethod
    def set_autostart(self, enable: bool, name: str, entry: Path) -> None:
        """Registra/desregistra el arranque automático con la sesión.

        `name` es el nombre visible de la app; `entry` el script/binario a
        lanzar. Cada impl construye su propio comando (Exec= vs Run key)."""
        ...

    @abstractmethod
    def autostart_enabled(self, name: str) -> bool:
        """True si el autoarranque está registrado para `name`."""
        ...

    @abstractmethod
    def open_path(self, path) -> None:
        """Abre un archivo o carpeta con la aplicación por defecto del SO
        (xdg-open / os.startfile). No debe lanzar excepciones."""
        ...
