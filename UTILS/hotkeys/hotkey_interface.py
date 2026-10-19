# -*- coding: utf-8 -*-
"""Interfaz común de hotkey global (estilo Java: interfaz + implementaciones).

`HotkeyBackend` define el contrato que cumplen las implementaciones por
plataforma:

    hotkeys_linux.py    → LinuxHotkeyManager    (XGrabKey real + fallback)
    hotkeys_windows.py  → WindowsHotkeyManager  (RegisterHotKey + fallback)

Ciclo de vida: el constructor de la interfaz dispara start(combo); las
subclases deben inicializar sus campos ANTES de llamar a super().__init__().

Además vive acá todo lo que es 100 % portable: la normalización de combos
("Ctrl+Alt+P" / "F10" / "Print"), el formato para mostrar y el listener de
fallback vía pynput (funciona igual en todos los SO; no suprime la tecla).
"""

from abc import ABCMeta, abstractmethod

from UTILS.qt_compat.QtCore import QObject, Qt, pyqtSignal

from UTILS.deps import pkb

# Metaclass mixta: ABC (abstractmethod) + QObject (pyqtSignal).
_QObjectABC = type("QObjectABC", (type(QObject), ABCMeta), {})


class HotkeyBackend(QObject, metaclass=_QObjectABC):
    """Interfaz del gestor de hotkey global.

    Señales:
        triggered()  el usuario presionó el combo registrado
        failed()     no se pudo registrar ni el backend nativo ni el fallback
    """
    triggered = pyqtSignal()
    failed = pyqtSignal()

    def __init__(self, combo: str):
        super().__init__()
        self.start(combo)

    @abstractmethod
    def start(self, combo: str) -> bool:
        """(Re)registra el hotkey. Devuelve True si quedó escuchando."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Libera el hotkey y mata los hilos/listeners asociados."""
        ...


# ---------------------------------------------------------------------------
# Normalización de combos ("Ctrl+Alt+P" / "F10" / "Print")  — portable
# ---------------------------------------------------------------------------
_QTKEY_SPECIAL = {
    "print": "print_screen", "print screen": "print_screen", "prntscrn": "print_screen",
    "scroll lock": "scroll_lock", "scrolllock": "scroll_lock",
    "pgup": "page_up", "pgdown": "page_down", "pageup": "page_up", "pagedown": "page_down",
    "del": "delete", "ins": "insert", "esc": "escape", "space": "space",
    "enter": "return", "return": "return", "pause": "pause", "break": "pause",
}

_QT_TO_MOD = {
    Qt.KeyboardModifier.ControlModifier: "ctrl",
    Qt.KeyboardModifier.AltModifier: "alt",
    Qt.KeyboardModifier.ShiftModifier: "shift",
    Qt.KeyboardModifier.MetaModifier: "super",
}


def normalize_hotkey(s: str):
    """'Ctrl+Alt+P'/'F10'/'Print' → (set(mods), keyname) o (set(), None)."""
    mods, key = set(), None
    for part in [p.strip() for p in (s or "").split("+") if p.strip()]:
        low = part.lower()
        if low in ("ctrl", "control", "strg"):
            mods.add("ctrl")
        elif low in ("alt", "altgr"):
            mods.add("alt")
        elif low == "shift":
            mods.add("shift")
        elif low in ("super", "meta", "win", "cmd"):
            mods.add("super")
        else:
            key = _QTKEY_SPECIAL.get(low, low)
    return mods, key


def hotkey_display(s: str) -> str:
    mods, key = normalize_hotkey(s)
    order = ["ctrl", "alt", "shift", "super"]
    disp = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "super": "Super"}
    if not key:
        return ""
    parts = [disp[m] for m in order if m in mods]
    kdisp = {"print_screen": "PrtSc", "scroll_lock": "Scroll",
             "page_up": "PgUp", "page_down": "PgDown"}.get(key, key.upper() if len(key) <= 3 else key.title())
    if len(key) == 1:
        kdisp = key.upper()
    return "+".join(parts + [kdisp])


# ---------------------------------------------------------------------------
# Fallback portable: pynput (NO suprime la tecla; otra app puede reaccionar)
# ---------------------------------------------------------------------------
class PynputFallbackListener:
    """Listener global vía pynput — implementación compartida del fallback."""

    def __init__(self, combo, on_trigger):
        self.on_trigger = on_trigger
        mods, key = normalize_hotkey(combo)
        self._mods = mods
        self._key = key
        self._held = set()
        self._fired = False
        self.listener = None
        if key:
            self.listener = pkb.Listener(on_press=self._press, on_release=self._release)
            self.listener.start()

    def _norm_name(self, k):
        n = k.name if isinstance(k, pkb.Key) else (k.char or "").lower()
        if not n and isinstance(k, pkb.KeyCode):
            n = ""
        for pref, mod in (("ctrl", "ctrl"), ("alt", "alt"), ("shift", "shift"),
                          ("super", "super"), ("cmd", "super"), ("meta", "super")):
            if n.startswith(pref):
                return f"mod:{mod}"
        return n

    def _press(self, k):
        n = self._norm_name(k)
        if n.startswith("mod:"):
            self._held.add(n[4:])
            return
        if n == self._key and self._mods <= self._held:
            if not self._fired:
                self._fired = True
                self.on_trigger()

    def _release(self, k):
        n = self._norm_name(k)
        if n.startswith("mod:"):
            self._held.discard(n[4:])
        elif n == self._key:
            self._fired = False

    def stop(self):
        if self.listener:
            self.listener.stop()
