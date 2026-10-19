# -*- coding: utf-8 -*-
"""Implementación Windows del hotkey global.

Primario:  _RegisterHotKeyThread → RegisterHotKey (la tecla se consume y
                                    ninguna otra app la recibe, igual que
                                    XGrabKey en Linux). Requiere un message
                                    loop: Win32 solo entrega WM_HOTKEY al
                                    hilo que registró la combinación.
Fallback:  PynputFallbackListener → escucha global de teclado (la tecla NO
                                    se suprime, otra app puede reaccionar).
"""

import ctypes
import sys
import threading
import time
from ctypes import wintypes

from UTILS.deps import HAS_PYNPUT
from UTILS.hotkeys.hotkey_interface import (HotkeyBackend,
                                            PynputFallbackListener,
                                            normalize_hotkey)

_IS_WIN = sys.platform == "win32"

if _IS_WIN:
    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    _user32.RegisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int,
                                       wintypes.UINT, wintypes.UINT]
    _user32.RegisterHotKey.restype = wintypes.BOOL
    _user32.UnregisterHotKey.argtypes = [wintypes.HWND, ctypes.c_int]
    _user32.UnregisterHotKey.restype = wintypes.BOOL
    _user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG),
                                    wintypes.HWND, wintypes.UINT, wintypes.UINT]
    _user32.GetMessageW.restype = ctypes.c_int
    _user32.PostThreadMessageW.argtypes = [wintypes.DWORD, wintypes.UINT,
                                           wintypes.WPARAM, wintypes.LPARAM]
    _user32.PostThreadMessageW.restype = wintypes.BOOL
    _kernel32.GetCurrentThreadId.argtypes = []
    _kernel32.GetCurrentThreadId.restype = wintypes.DWORD
else:
    _user32 = _kernel32 = None

_WM_HOTKEY = 0x0312
_WM_QUIT = 0x0012
_MOD_NOREPEAT = 0x4000          # no repetir mientras la tecla queda apretada
_WIN_MODS = {"alt": 0x0001, "ctrl": 0x0002, "shift": 0x0004, "super": 0x0008}

# nombre interno (normalize_hotkey) → virtual-key code
_VK_MAP = {
    "print_screen": 0x2C, "scroll_lock": 0x91, "pause": 0x13,
    "page_up": 0x21, "page_down": 0x22, "insert": 0x2D, "delete": 0x2E,
    "home": 0x24, "end": 0x23, "escape": 0x1B, "return": 0x0D,
    "space": 0x20, "backspace": 0x08, "tab": 0x09,
    "up": 0x26, "down": 0x28, "left": 0x25, "right": 0x27,
    "num_lock": 0x90, "caps_lock": 0x14,
}


def _vk_for(key: str):
    """Nombre interno → virtual-key code (o None si no es mapeable)."""
    if not key:
        return None
    if len(key) == 1 and key.isalnum():
        return ord(key.upper())          # 'a'-'z' / '0'-'9' coinciden con VK
    if key.startswith("f") and key[1:].isdigit():
        n = int(key[1:])
        if 1 <= n <= 24:
            return 0x6F + n              # VK_F1..VK_F24
    if key.startswith("num"):            # numpad: "num0".."num9"
        tail = key[3:]
        if tail.isdigit():
            return 0x60 + int(tail)
    return _VK_MAP.get(key)


class _RegisterHotKeyThread(threading.Thread):
    """Hilo dueño del hotkey: registra, corre el message loop y desregistra.

    Win32 exige que WM_HOTKEY lo reciba el MISMO hilo que llamó a
    RegisterHotKey → el registro ocurre dentro de run() y stop() lo
    despierta con PostThreadMessage(WM_QUIT)."""

    _HOTKEY_ID = 1

    def __init__(self, combo: str, on_trigger, on_fail):
        super().__init__(daemon=True, name="win-hotkey")
        self.on_trigger = on_trigger
        self.on_fail = on_fail
        self._tid = None
        self._registered = threading.Event()
        mods, key = normalize_hotkey(combo)
        self._mods = mods
        self._key = key

    def run(self):
        if not _IS_WIN:
            self.on_fail()
            return
        try:
            vk = _vk_for(self._key)
            if vk is None:
                raise RuntimeError(f"tecla sin VK: {self._key!r}")
            fs_mods = _MOD_NOREPEAT
            for m in self._mods:
                fs_mods |= _WIN_MODS.get(m, 0)
            # El message queue del hilo debe existir ANTES de que stop()
            # pueda postearle: forzarlo con PeekMessage es el patrón estándar.
            msg = wintypes.MSG()
            _user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)
            self._tid = _kernel32.GetCurrentThreadId()
            if not _user32.RegisterHotKey(None, self._HOTKEY_ID, fs_mods, vk):
                raise RuntimeError("RegisterHotKey devolvió 0 (combo ocupado?)")
            self._registered.set()
            while _user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                if msg.message == _WM_HOTKEY:
                    self.on_trigger()
            _user32.UnregisterHotKey(None, self._HOTKEY_ID)
        except Exception:
            self._registered.set()       # desbloquea el chequeo de start()
            self.on_fail()

    def stop(self):
        if self._tid is not None:
            try:
                _user32.PostThreadMessageW(self._tid, _WM_QUIT, 0, 0)
            except Exception:
                pass
        if self.is_alive():
            self.join(timeout=0.5)


if _IS_WIN:
    _user32.PeekMessageW.argtypes = [ctypes.POINTER(wintypes.MSG),
                                     wintypes.HWND, wintypes.UINT,
                                     wintypes.UINT, wintypes.UINT]
    _user32.PeekMessageW.restype = wintypes.BOOL


class WindowsHotkeyManager(HotkeyBackend):
    """Implementación Windows de HotkeyBackend (RegisterHotKey + fallback)."""

    def __init__(self, combo: str):
        # Inicializar campos ANTES de super().__init__: éste llama a start().
        self._win = None
        self._py = None
        super().__init__(combo)

    def start(self, combo: str) -> bool:
        self.stop()
        self._combo = combo
        ok = False
        if _IS_WIN:
            self._win = _RegisterHotKeyThread(combo, self.triggered.emit,
                                              self._fallback)
            self._win.start()
            self._win._registered.wait(timeout=0.5)
            if self._win.is_alive():
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
        if self._win:
            self._win.stop()
            self._win = None
        if self._py:
            self._py.stop()
            self._py = None
