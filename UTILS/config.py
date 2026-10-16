# -*- coding: utf-8 -*-
"""Rutas, configuración persistente y autoarranque de Screenshot Tool."""

import json
import os
import sys
from pathlib import Path

APP_NAME    = "Screenshot Tool"
CONFIG_DIR  = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "screenshot-tool"
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR   = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "screenshot-tool"
AUTOSTART_PATH = Path.home() / ".config" / "autostart" / "screenshot-tool.desktop"

DEFAULT_PICTURES = "Imágenes" if (Path.home() / "Imágenes").is_dir() else "Pictures"

DEFAULTS = {
    "hotkey":         "F10",
    "window_hover":   True,              # resaltar ventana al pasar el mouse (Enter la captura)
    "save_folder":    str(Path.home() / DEFAULT_PICTURES / "Screenshots"),
    "format":         "jpg",            # jpg | png | both
    "jpeg_quality":   95,
    "prefix":         "",               # prefijo del nombre de archivo
    "copy_clipboard": True,
    "sound":          True,
    "toast":          True,
    "float_preview":  True,
    "preview_seconds": 3.0,
    "magnifier_zoom": 5,
    "thirds_grid":    True,
    "accent":         "#00c8ff",
    "open_after":     "none",           # none | default | custom
    "editor_cmd":     "",               # comando con %f (ej: "gimp %f")
    "autostart":      True,
}

# El .desktop apunta al entry point del proyecto (no a este archivo UTILS/).
_ENTRY_SCRIPT = Path(__file__).resolve().parent.parent / "screenshot_tray_linux.py"


def load_config() -> dict:
    cfg = dict(DEFAULTS)
    try:
        if CONFIG_FILE.exists():
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except Exception:
        pass
    return cfg


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


def set_autostart(enable: bool, entry_script: Path | None = None) -> None:
    try:
        if enable:
            AUTOSTART_PATH.parent.mkdir(parents=True, exist_ok=True)
            script = Path(entry_script) if entry_script else _ENTRY_SCRIPT
            # sys.executable ya apunta al python del venv; NO resolver el symlink
            # (resolve() lleva a /usr/bin/python3.x, que no tiene las dependencias)
            py = Path(sys.executable)
            AUTOSTART_PATH.write_text(
                "[Desktop Entry]\n"
                "Type=Application\n"
                f"Exec={py} {script}\n"
                "Hidden=false\n"
                "NoDisplay=false\n"
                f"Name={APP_NAME}\n"
                "Comment=Capturas de pantalla rápidas con hotkey (F10)\n"
                "Categories=Utility;Graphics;\n",
                encoding="utf-8")
        else:
            if AUTOSTART_PATH.exists():
                AUTOSTART_PATH.unlink()
    except Exception:
        pass


def autostart_enabled() -> bool:
    return AUTOSTART_PATH.exists()
