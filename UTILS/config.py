# -*- coding: utf-8 -*-
"""Rutas, configuración persistente y autoarranque de Screenshot Tool.

Todo lo dependiente de SO (XDG vs APPDATA, .desktop vs Registry Run) está
delegado al backend de UTILS/system — este módulo queda 100 % portable."""

import json
from pathlib import Path

from UTILS.system import backend as _sys

APP_NAME    = "Screenshot Tool"
CONFIG_DIR  = _sys.config_dir()
CONFIG_FILE = CONFIG_DIR / "config.json"
CACHE_DIR   = _sys.cache_dir()

DEFAULTS = {
    "hotkey":         "F10",
    "window_hover":   True,              # resaltar ventana al pasar el mouse (Enter la captura)
    "save_folder":    str(_sys.default_save_folder()),
    "format":         "jpg",            # jpg | png | both
    "jpeg_quality":   95,
    "prefix":         "",               # prefijo del nombre de archivo
    "copy_clipboard": True,
    "sound":          True,
    "toast":          True,
    "float_preview":  True,
    "preview_seconds": 3.0,
    "magnifier":      False,            # lupa alrededor del cursor
    "magnifier_zoom": 5,
    "thirds_grid":    True,
    "accent":         "#00b050",
    "open_after":     "none",           # none | default | custom
    "editor_cmd":     "",               # comando con %f (ej: "gimp %f")
    "autostart":      True,
    "startup_notification": True,       # notificación "Listo" al arrancar
}

# El .desktop apunta al entry point del proyecto (no a este archivo UTILS/).
_ENTRY_SCRIPT = Path(__file__).resolve().parent.parent / "N-SHOOT.py"


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


def set_autostart(enable: bool) -> None:
    """Wrapper fino sobre el backend: pasa nombre de app + script de arranque."""
    _sys.set_autostart(enable, APP_NAME, _ENTRY_SCRIPT)


def autostart_enabled() -> bool:
    return _sys.autostart_enabled(APP_NAME)
