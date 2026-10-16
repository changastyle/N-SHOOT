# -*- coding: utf-8 -*-
"""Captura de pantalla (mss), sonido de obturador sintetizado y detección
de la ventana bajo el cursor vía _NET_CLIENT_LIST_STACKING (xlib)."""

import math
import shutil
import struct
import subprocess
import wave
from pathlib import Path

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QImage

from UTILS.config import CACHE_DIR
from UTILS.deps import HAS_XLIB, X, mss, xlib_display


def grab_screen() -> tuple:
    """Captura TODO el escritorio virtual con mss. Devuelve (QImage, offset(QPoint))."""
    with mss.MSS() as sct:
        mon = sct.monitors[0]
        shot = sct.grab(mon)
    data = bytes(shot.raw)
    # mss devuelve BGRX con alfa=0 → ARGB32 quedaría totalmente transparente.
    # RGB32 fuerza alfa=255 (el 4º byte se ignora).
    img = QImage(data, shot.width, shot.height, shot.width * 4, QImage.Format.Format_RGB32)
    img = img.copy()          # desacoplar del buffer temporal
    return img, QPoint(mon["left"], mon["top"])


def play_shutter() -> None:
    """Sonidito de obturador (wav sintetizado, reproducido con paplay/aplay)."""
    wav = CACHE_DIR / "shutter.wav"
    try:
        if not wav.exists():
            CACHE_DIR.mkdir(parents=True, exist_ok=True)
            _make_shutter_wav(wav)
        for player in ("paplay", "aplay"):
            if shutil.which(player):
                subprocess.Popen([player, str(wav)], stdout=subprocess.DEVNULL,
                                 stderr=subprocess.DEVNULL)
                return
    except Exception:
        pass


def _make_shutter_wav(path: Path) -> None:
    sr = 44100
    dur = 0.20
    n = int(sr * dur)
    frames = []
    for i in range(n):
        t = i / sr
        s = 0.0
        # primer 'click'
        s += math.exp(-t / 0.004) * math.sin(2 * math.pi * 1500 * t)
        # segundo 'clack'
        t2 = t - 0.07
        if t2 > 0:
            env = math.exp(-t2 / 0.025)
            s += env * (0.7 * math.sin(2 * math.pi * 700 * t2) +
                        0.3 * math.sin(2 * math.pi * 2600 * t2))
        v = max(-1.0, min(1.0, s * 0.8))
        frames.append(int(v * 32000))
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(struct.pack(f"<{len(frames)}h", *frames))


def window_rect_at(root_x: int, root_y: int):
    """Ventana más al tope bajo el cursor (coords raíz). → (QRect, nombre) o None."""
    if not HAS_XLIB:
        return None
    try:
        disp = xlib_display.Display()
        root = disp.screen().root
        net = disp.intern_atom("_NET_CLIENT_LIST_STACKING")
        prop = root.get_full_property(net, X.AnyPropertyType)
        result = None
        if prop:
            for wid in reversed(prop.value):
                try:
                    w = disp.create_resource_object("window", wid)
                    if w.get_attributes().map_state != 2:   # IsViewable
                        continue
                    g = w.get_geometry()
                    tl = w.translate_coords(root, 0, 0)
                    r = QRect(tl.x, tl.y, g.width, g.height)
                    if r.width() < 20 or r.height() < 20:
                        continue
                    if r.contains(root_x, root_y):
                        name = ""
                        try:
                            name = (w.get_wm_name() or "") or ""
                        except Exception:
                            name = ""
                        result = (r, name)
                        break
                except Exception:
                    continue
        disp.close()
        return result
    except Exception:
        return None
