# -*- coding: utf-8 -*-
"""Capa de compatibilidad de binding Qt.

Motivo: en Windows con Smart App Control / WDAC activo, las DLL nativas de
PyQt6 (sip*.pyd, Qt6*.dll de Riverbank) son bloqueadas por la política de
reputación. Los binarios de PySide6 (firmados por Qt Group) sí pasan el
filtro.

IMPORTANTE — por qué el orden importa: un import de PyQt6 que FALLA deja
Qt6Core.dll/Qt6Gui.dll de Riverbank cargados parcialmente en el proceso; al
intentar PySide6 después, Windows resuelve `Qt6Core.dll` por nombre y
devuelve la copia ya cargada (la de PyQt6) → "No se encontró el proceso
especificado". O sea, el fallback tiene que probar primero el binding que
va a funcionar: no sirve intentar PyQt6 y luego PySide6 en el mismo
proceso. Por eso el orden depende de la plataforma:

    win32   → PySide6 primero (SAC-safe), luego PyQt6
    otros   → PyQt6 primero (binding original), luego PySide6

Si el primero ni siquiera está instalado (ModuleNotFoundError, sin DLLs
cargadas) el segundo intenta limpio.

La API de ambos bindings en Qt6 es prácticamente idéntica; las únicas
diferencias que usa este proyecto se normalizan en QtCore.py:

    pyqtSignal  → Signal
    pyqtSlot    → Slot

Uso — reemplazar el módulo de origen en los imports:

    from PyQt6.QtCore import Qt, pyqtSignal
    ↓
    from UTILS.qt_compat.QtCore import Qt, pyqtSignal
"""

import sys

BIND: str | None = None
"""'PyQt6' | 'PySide6' | None — binding seleccionado (None = ninguno carga)."""

_ORDER = ("PySide6", "PyQt6") if sys.platform == "win32" else ("PyQt6", "PySide6")

for _name in _ORDER:
    try:
        _pkg = __import__(_name, fromlist=[
            "QtCore", "QtGui", "QtNetwork", "QtSvg", "QtWidgets"])
        QtCore = _pkg.QtCore       # noqa: F401
        QtGui = _pkg.QtGui         # noqa: F401
        QtNetwork = _pkg.QtNetwork # noqa: F401
        QtSvg = _pkg.QtSvg         # noqa: F401
        QtWidgets = _pkg.QtWidgets # noqa: F401
        BIND = _name
        break
    except ImportError:
        continue

HAS_QT = BIND is not None
