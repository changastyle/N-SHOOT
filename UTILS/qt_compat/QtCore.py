# -*- coding: utf-8 -*-
"""Re-export de QtCore del binding activo + alias pyqtSignal/pyqtSlot."""

from UTILS.qt_compat import BIND

if BIND == "PyQt6":
    from PyQt6.QtCore import *      # noqa: F401,F403
    from PyQt6.QtCore import pyqtSignal, pyqtSlot  # noqa: F401
elif BIND == "PySide6":
    from PySide6.QtCore import *    # noqa: F401,F403
    from PySide6.QtCore import Signal as pyqtSignal, Slot as pyqtSlot  # noqa: F401
else:
    raise ImportError("Ni PyQt6 ni PySide6 están disponibles")
