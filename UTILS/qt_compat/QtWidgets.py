# -*- coding: utf-8 -*-
"""Re-export de QtWidgets del binding activo."""

from UTILS.qt_compat import BIND

if BIND == "PyQt6":
    from PyQt6.QtWidgets import *   # noqa: F401,F403
elif BIND == "PySide6":
    from PySide6.QtWidgets import * # noqa: F401,F403
else:
    raise ImportError("Ni PyQt6 ni PySide6 están disponibles")
