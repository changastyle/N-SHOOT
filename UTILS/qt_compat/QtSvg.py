# -*- coding: utf-8 -*-
"""Re-export de QtSvg del binding activo."""

from UTILS.qt_compat import BIND

if BIND == "PyQt6":
    from PyQt6.QtSvg import *       # noqa: F401,F403
elif BIND == "PySide6":
    from PySide6.QtSvg import *     # noqa: F401,F403
else:
    raise ImportError("Ni PyQt6 ni PySide6 están disponibles")
