# -*- coding: utf-8 -*-
"""Interfaz común de captura de pantalla (estilo Java: interfaz + impls).

`ScreenCaptureBackend` define el contrato que cumplen las implementaciones
por plataforma:

    screen_capture_linux.py    → LinuxScreenCapture
    screen_capture_windows.py  → WindowsScreenCapture

Cada backend instancia un singleton `_backend` y re-exporta sus métodos como
funciones de módulo (grab_screen / play_shutter / window_rect_at), así el
dispatcher UTILS/screen_capture/__init__.py y los consumidores (UI.py,
overlay.py) trabajan con funciones sueltas igual que antes.

También vive acá lo compartido entre backends: la síntesis del wav de
obturador (mismo sonido en todos los SO).
"""

import math
import struct
import wave
from abc import ABC, abstractmethod
from pathlib import Path


class ScreenCaptureBackend(ABC):
    """Interfaz del backend de captura."""

    @abstractmethod
    def grab_screen(self):
        """Captura el escritorio virtual completo.

        Devuelve (QImage, QPoint) donde el QPoint es el offset del monitor
        virtual (esquina superior izquierda en coords de pantalla)."""
        ...

    @abstractmethod
    def play_shutter(self) -> None:
        """Reproduce el sonido de obturador (no debe lanzar excepciones)."""
        ...

    @abstractmethod
    def window_rect_at(self, root_x: int, root_y: int):
        """Ventana top-level más al tope bajo el punto (coords de pantalla).

        Devuelve (QRect, título) o None."""
        ...


def make_shutter_wav(path: Path) -> None:
    """Genera el wav del obturador (click + clack sintetizado)."""
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
