# -*- coding: utf-8 -*-
"""Hotkey global de Screenshot Tool.

Primario:  _XGrabListener  → XGrabKey real (la tecla se consume y nadie más
                             la recibe). Requiere python-xlib.
Fallback:  _PynputListener → escucha global de teclado (la tecla NO se suprime,
                             otra app puede reaccionar también).
"""

import threading
import time
from itertools import combinations

from PyQt6.QtCore import QObject, Qt, pyqtSignal

from UTILS.deps import HAS_PYNPUT, HAS_XLIB, X, XK, pkb, xlib_display

# ---------------------------------------------------------------------------
# Normalización de combos ("Ctrl+Alt+P" / "F10" / "Print")
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


def _keysym_name(internal: str) -> str:
    special = {
        "print_screen": "Print", "scroll_lock": "Scroll_Lock",
        "page_up": "Prior", "page_down": "Next", "insert": "Insert",
        "home": "Home", "end": "End", "delete": "Delete", "pause": "Pause",
        "escape": "Escape", "return": "Return", "space": "space",
    }
    if len(internal) == 1:
        return internal
    if internal.startswith("f") and internal[1:].isdigit():
        return f"F{internal[1:]}"
    return special.get(internal, internal.capitalize())


def _lock_subsets():
    """Variantes de modifiers para ignorar CapsLock/NumLock/ScrollLock."""
    optional = [X.LockMask, X.Mod2Mask, X.Mod5Mask] if HAS_XLIB else []
    return [set(c) for i in range(len(optional) + 1) for c in combinations(optional, i)]


class _XGrabListener(threading.Thread):
    """Grab REAL de la tecla a nivel X11: la app la consume y NADIE más la recibe."""

    def __init__(self, combo: str, on_trigger, on_fail):
        super().__init__(daemon=True, name="xgrab-hotkey")
        self.on_trigger = on_trigger
        self.on_fail = on_fail
        self._stop_evt = threading.Event()
        self._disp = None
        self._root = None
        self._keycode = 0
        self._base = 0
        mods, key = normalize_hotkey(combo)
        self._mods = mods
        self._key = key

    def run(self):
        if not (HAS_XLIB and self._key):
            self.on_fail()
            return
        disp = None
        try:
            disp = xlib_display.Display()
            self._disp = disp
            # Los errores de protocolo (p.ej. BadAccess en GrabKey) llegan
            # ASINCRÓNICOS: python-xlib por defecto sólo los imprime y el
            # grab queda silenciosamente sin efecto. Con handler propio los
            # detectamos tras sync() y caemos al fallback como corresponde.
            errs = []
            disp.set_error_handler(lambda err, req: errs.append(err))
            root = disp.screen().root
            ks = XK.string_to_keysym(_keysym_name(self._key))
            keycode = disp.keysym_to_keycode(ks) if ks else 0
            if not keycode:
                raise RuntimeError("keysym sin keycode")
            base = 0
            fmap = {"ctrl": X.ControlMask, "alt": X.Mod1Mask,
                    "super": X.Mod4Mask, "shift": X.ShiftMask}
            for m in self._mods:
                base |= fmap.get(m, 0)
            self._root = root
            self._keycode = keycode
            self._base = base
            self._grab(root, keycode, base)
            disp.sync()
            if errs:
                raise RuntimeError(f"grab_key: {errs[0].__class__.__name__}")
        except Exception:
            try:
                if disp is not None:
                    disp.close()
            except Exception:
                pass
            self.on_fail()
            return
        while not self._stop_evt.is_set():
            try:
                ev = disp.next_event()
            except Exception:
                break
            if getattr(ev, "type", None) == X.KeyPress:
                self.on_trigger()
            elif getattr(ev, "type", None) == X.MappingNotify and \
                    getattr(ev, "category", 0) == X.MappingKeyboard:
                try:
                    disp.refresh_keyboard_mapping(ev)
                    ks = XK.string_to_keysym(_keysym_name(self._key))
                    keycode = disp.keysym_to_keycode(ks) if ks else 0
                    if keycode:
                        self._keycode = keycode
                        self._grab(root, keycode, base)
                except Exception:
                    pass
        try:
            self._ungrab()
            disp.close()
        except Exception:
            pass

    def _ungrab(self):
        """Libera todas las variantes del grab en la conexión propia.
        Thread-safe: python-xlib serializa los envíos; puede llamarse desde
        stop() mientras el hilo está bloqueado en next_event()."""
        disp, root, keycode, base = self._disp, self._root, self._keycode, self._base
        if disp is None or root is None or not keycode:
            return
        for extra in _lock_subsets():
            mask = base
            for bit in extra:
                mask |= bit
            root.ungrab_key(keycode, mask)
        disp.flush()

    def _grab(self, root, keycode, base):
        for extra in _lock_subsets():
            mask = base
            for bit in extra:
                mask |= bit
            root.grab_key(keycode, mask, True, X.GrabModeAsync, X.GrabModeAsync)

    def stop(self):
        self._stop_evt.set()
        try:
            # Liberar los grabs ANTES de cerrar: si la conexión muere con los
            # passive grabs aún activos, el server tarda en soltarlos y el
            # próximo grab_key (re-registro al guardar preferencias) recibe
            # BadAccess y el hotkey queda muerto.
            self._ungrab()
        except Exception:
            pass
        try:
            if self._disp is not None:
                self._disp.close()   # desbloquea next_event() del hilo
        except Exception:
            pass
        if self.is_alive():
            self.join(timeout=0.5)   # no re-grabar hasta que el hilo murió


class _PynputListener:
    """Fallback: listener global vía pynput (la clave no se suprime, algún app puede reaccionar)."""

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


class HotkeyManager(QObject):
    triggered = pyqtSignal()
    failed = pyqtSignal()

    def __init__(self, combo: str):
        super().__init__()
        self._x = None
        self._py = None
        self.start(combo)

    def start(self, combo: str) -> bool:
        self.stop()
        self._combo = combo
        ok = False
        if HAS_XLIB:
            self._x = _XGrabListener(combo, self.triggered.emit, self._fallback)
            self._x.start()
            time.sleep(0.05)
            if self._x.is_alive():
                ok = True
        if not ok:
            ok = self._fallback()
        return ok

    def _fallback(self) -> bool:
        if self._py is not None:
            return self._py.listener is not None
        if not HAS_PYNPUT:
            self.failed.emit()
            return False
        try:
            self._py = _PynputListener(self._combo, self.triggered.emit)
            return self._py.listener is not None
        except Exception:
            self._py = None
            return False

    def stop(self):
        if self._x:
            self._x.stop()
            self._x = None
        if self._py:
            self._py.stop()
            self._py = None
