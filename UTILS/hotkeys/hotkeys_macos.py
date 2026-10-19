# -*- coding: utf-8 -*-
"""Implementación macOS del hotkey global.

Primario:  _CarbonHotkeyThread → RegisterEventHotKey de Carbon (la tecla se
                                  consume y ninguna otra app la recibe; no
                                  requiere permiso de Accesibilidad). API
                                  deprecated desde 10.8 pero funcional.
                                  Requiere RunApplicationEventLoop: los
                                  eventos solo llegan al hilo que corre el
                                  event loop — igual que WM_HOTKEY en Win32.
Fallback:  PynputFallbackListener → escucha global (NO suprime la tecla y
                                  necesita permiso de Accesibilidad).
"""

import ctypes
import sys
import threading

from UTILS.deps import HAS_PYNPUT
from UTILS.hotkeys.hotkey_interface import (HotkeyBackend,
                                            PynputFallbackListener,
                                            normalize_hotkey)

_IS_MAC = sys.platform == "darwin"

if _IS_MAC:
    _carbon = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")

    class _EventHotKeyID(ctypes.Structure):
        _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]

    class _EventTypeSpec(ctypes.Structure):
        _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]

    _EventHandlerProc = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p,
                                         ctypes.c_void_p, ctypes.c_void_p)

    _carbon.GetEventDispatcherTarget.argtypes = []
    _carbon.GetEventDispatcherTarget.restype = ctypes.c_void_p
    _carbon.RegisterEventHotKey.argtypes = [
        ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID,
        ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_void_p)]
    _carbon.RegisterEventHotKey.restype = ctypes.c_int32
    _carbon.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
    _carbon.UnregisterEventHotKey.restype = ctypes.c_int32
    _carbon.InstallEventHandler.argtypes = [
        ctypes.c_void_p, _EventHandlerProc, ctypes.c_uint32,
        ctypes.POINTER(_EventTypeSpec), ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_void_p)]
    _carbon.InstallEventHandler.restype = ctypes.c_int32
    _carbon.RemoveEventHandler.argtypes = [ctypes.c_void_p]
    _carbon.RemoveEventHandler.restype = ctypes.c_int32
    _carbon.RunApplicationEventLoop.argtypes = []
    _carbon.RunApplicationEventLoop.restype = ctypes.c_int32
    _carbon.QuitApplicationEventLoop.argtypes = []
    _carbon.QuitApplicationEventLoop.restype = ctypes.c_int32
else:
    _carbon = None

# 'keyb' + kEventHotKeyPressed
_K_EVENT_CLASS_KEYBOARD = 0x6B657962
_K_EVENT_HOTKEY_PRESSED = 5
# modificadores Carbon: cmdKey / shiftKey / optionKey / controlKey
_MAC_MODS = {"super": 0x0100, "shift": 0x0200, "alt": 0x0800, "ctrl": 0x1000}

# nombre interno (normalize_hotkey) → virtual keycode ANSI de macOS
_MAC_VK = {
    "a": 0x00, "s": 0x01, "d": 0x02, "f": 0x03, "h": 0x04, "g": 0x05,
    "z": 0x06, "x": 0x07, "c": 0x08, "v": 0x09, "b": 0x0B, "q": 0x0C,
    "w": 0x0D, "e": 0x0E, "r": 0x0F, "y": 0x10, "t": 0x11,
    "1": 0x12, "2": 0x13, "3": 0x14, "4": 0x15, "6": 0x16, "5": 0x17,
    "9": 0x19, "7": 0x1A, "8": 0x1C, "0": 0x1D,
    "o": 0x1F, "u": 0x20, "i": 0x22, "p": 0x23, "l": 0x25, "j": 0x26,
    "k": 0x28, "n": 0x2D, "m": 0x2E,
    "return": 0x24, "tab": 0x30, "space": 0x31, "backspace": 0x33,
    "escape": 0x35, "delete": 0x75, "home": 0x73, "end": 0x77,
    "page_up": 0x74, "page_down": 0x79,
    "left": 0x7B, "right": 0x7C, "down": 0x7D, "up": 0x7E,
    "print_screen": 0x69,   # sin PrtSc en teclados Mac → F13
    "f1": 0x7A, "f2": 0x78, "f3": 0x63, "f4": 0x76, "f5": 0x60,
    "f6": 0x61, "f7": 0x62, "f8": 0x64, "f9": 0x65, "f10": 0x6D,
    "f11": 0x67, "f12": 0x6F, "f13": 0x69, "f14": 0x6B, "f15": 0x71,
    "f16": 0x6A, "f17": 0x40, "f18": 0x4F, "f19": 0x50, "f20": 0x5A,
}

_HOTKEY_SIG = 0x68746B31            # 'htk1'
_HOTKEY_ID = 1


class _CarbonHotkeyThread(threading.Thread):
    """Hilo dueño del hotkey: instala handler, registra y corre el event loop.

    Carbon entrega el evento al event loop del hilo que instaló el handler
    → todo ocurre dentro de run() y stop() lo despierta con
    QuitApplicationEventLoop() (segura desde otro hilo)."""

    def __init__(self, combo: str, on_trigger, on_fail):
        super().__init__(daemon=True, name="mac-hotkey")
        self.on_trigger = on_trigger
        self.on_fail = on_fail
        self._registered = threading.Event()
        self._handler_ref = ctypes.c_void_p()
        self._hotkey_ref = ctypes.c_void_p()
        # mantener vivo el callback CFUNCTYPE mientras el hilo viva
        self._proc = _EventHandlerProc(self._on_event) if _IS_MAC else None
        mods, key = normalize_hotkey(combo)
        self._mods = mods
        self._key = key

    def _on_event(self, _call_ref, _event_ref, _user_data):
        self.on_trigger()
        return 0    # noErr

    def run(self):
        if not _IS_MAC:
            self.on_fail()
            return
        try:
            keycode = _MAC_VK.get(self._key or "")
            if keycode is None:
                raise RuntimeError(f"tecla sin keycode: {self._key!r}")
            mods = 0
            for m in self._mods:
                mods |= _MAC_MODS.get(m, 0)
            spec = _EventTypeSpec(_K_EVENT_CLASS_KEYBOARD, _K_EVENT_HOTKEY_PRESSED)
            target = _carbon.GetEventDispatcherTarget()
            if _carbon.InstallEventHandler(target, self._proc, 1,
                                           ctypes.byref(spec), None,
                                           ctypes.byref(self._handler_ref)):
                raise RuntimeError("InstallEventHandler falló")
            hid = _EventHotKeyID(_HOTKEY_SIG, _HOTKEY_ID)
            if _carbon.RegisterEventHotKey(keycode, mods, hid, target, 0,
                                           ctypes.byref(self._hotkey_ref)):
                raise RuntimeError("RegisterEventHotKey falló (combo ocupado?)")
            self._registered.set()
            _carbon.RunApplicationEventLoop()
        except Exception:
            self._registered.set()       # desbloquea el chequeo de start()
            self.on_fail()
            return
        finally:
            if self._hotkey_ref:
                _carbon.UnregisterEventHotKey(self._hotkey_ref)
                self._hotkey_ref = ctypes.c_void_p()
            if self._handler_ref:
                _carbon.RemoveEventHandler(self._handler_ref)
                self._handler_ref = ctypes.c_void_p()

    def stop(self):
        try:
            _carbon.QuitApplicationEventLoop()
        except Exception:
            pass
        if self.is_alive():
            self.join(timeout=0.5)


class MacOSHotkeyManager(HotkeyBackend):
    """Implementación macOS de HotkeyBackend (Carbon + fallback pynput)."""

    def __init__(self, combo: str):
        # Inicializar campos ANTES de super().__init__: éste llama a start().
        self._mac = None
        self._py = None
        super().__init__(combo)

    def start(self, combo: str) -> bool:
        self.stop()
        self._combo = combo
        ok = False
        if _IS_MAC:
            self._mac = _CarbonHotkeyThread(combo, self.triggered.emit,
                                            self._fallback)
            self._mac.start()
            self._mac._registered.wait(timeout=0.5)
            if self._mac.is_alive():
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
        if self._mac:
            self._mac.stop()
            self._mac = None
        if self._py:
            self._py.stop()
            self._py = None
