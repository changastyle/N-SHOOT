# -*- coding: utf-8 -*-
"""Implementación Linux/X11 del hotkey global.

Primario:  _XGrabListener  → XGrabKey real (la tecla se consume y nadie más
                             la recibe). Requiere python-xlib.
Fallback:  PynputFallbackListener → escucha global de teclado (la tecla NO
                             se suprime, otra app puede reaccionar también).
"""

import threading
import time
from itertools import combinations

from UTILS.deps import HAS_PYNPUT, HAS_XLIB, X, XK, xlib_display
from UTILS.hotkeys.hotkey_interface import (HotkeyBackend,
                                            PynputFallbackListener,
                                            normalize_hotkey)


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


class LinuxHotkeyManager(HotkeyBackend):
    """Implementación Linux de HotkeyBackend (XGrabKey + fallback pynput)."""

    def __init__(self, combo: str):
        # Inicializar campos ANTES de super().__init__: éste llama a start().
        self._x = None
        self._py = None
        super().__init__(combo)

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
            self._py = PynputFallbackListener(self._combo, self.triggered.emit)
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
