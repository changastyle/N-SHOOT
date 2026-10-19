# -*- coding: utf-8 -*-
"""Diálogo de Preferencias (4 tabs) + HotkeyEdit: campo que captura
el próximo atajo presionado."""

from pathlib import Path

from UTILS.qt_compat.QtCore import Qt, pyqtSignal
from UTILS.qt_compat.QtGui import QColor, QKeySequence
from UTILS.qt_compat.QtWidgets import (QCheckBox, QColorDialog, QComboBox,
                                       QDialog, QDialogButtonBox,
                                       QDoubleSpinBox, QFileDialog,
                                       QFormLayout, QHBoxLayout, QLabel,
                                       QLineEdit, QPushButton, QSpinBox,
                                       QTabWidget, QVBoxLayout,
                             QWidget)

from UTILS.config import CONFIG_FILE
from UTILS.hotkeys import _QT_TO_MOD, hotkey_display


class HotkeyEdit(QLineEdit):
    """LineEdit readonly que captura el próximo atajo presionado."""
    changed = pyqtSignal()

    def __init__(self, value: str):
        super().__init__()
        self.setReadOnly(True)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setValue(value)

    def setValue(self, v: str):
        self.setText(hotkey_display(v) or "(ninguno)")
        self.hotkey_raw = v or ""

    def focusInEvent(self, e):
        super().focusInEvent(e)
        self.setText("⌨️ Presioná la tecla o el atajo…")

    def focusOutEvent(self, e):
        super().focusOutEvent(e)
        self.setValue(self.hotkey_raw)

    def keyPressEvent(self, e):
        mods = e.modifiers()
        key = e.key()
        if key in (Qt.Key.Key_Control, Qt.Key.Key_Alt, Qt.Key.Key_Shift,
                   Qt.Key.Key_Meta, Qt.Key.Key_AltGr, Qt.Key.Key_unknown):
            return  # esperando la tecla principal
        if key == Qt.Key.Key_Escape:  # esc = limpiar
            self.hotkey_raw = ""
            self.changed.emit()
            self.clearFocus()
            self.setValue("")
            return
        parts = [_QT_TO_MOD[m] for m in _QT_TO_MOD if mods & m]
        name = QKeySequence(key).toString()
        if not name:
            return
        self.hotkey_raw = "+".join(parts + [name])
        self.changed.emit()
        self.clearFocus()
        self.setValue(self.hotkey_raw)


class PreferencesDialog(QDialog):
    def __init__(self, cfg: dict, parent=None):
        super().__init__(parent)
        self.cfg = dict(cfg)
        self.setWindowTitle("Preferencias — Screenshot Tool")
        self.setMinimumWidth(520)
        self.setModal(False)

        tabs = QTabWidget()
        tabs.addTab(self._tab_capture(), "📷  Captura")
        tabs.addTab(self._tab_save(), "💾  Guardado")
        tabs.addTab(self._tab_look(), "🎨  Aspecto y sonido")
        tabs.addTab(self._tab_system(), "🖥️  Sistema")

        bb = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                              QDialogButtonBox.StandardButton.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)

        lay = QVBoxLayout(self)
        lay.addWidget(tabs)
        lay.addWidget(bb)

    # ------------------------------------------------------------- tabs
    def _tab_capture(self):
        w = QWidget()
        f = QFormLayout(w)
        self.hotkey = HotkeyEdit(self.cfg["hotkey"])
        self.hotkey.changed.connect(lambda: self.cfg.__setitem__("hotkey", self.hotkey.hotkey_raw))
        f.addRow("Atajo global:", self.hotkey)
        self.win_hover = QCheckBox("Resaltar ventana al pasar el mouse (Enter la captura)")
        self.win_hover.setChecked(self.cfg["window_hover"])
        f.addRow("", self.win_hover)
        return w

    def _tab_save(self):
        w = QWidget()
        f = QFormLayout(w)
        # carpeta
        h = QHBoxLayout()
        self.folder = QLineEdit(self.cfg["save_folder"])
        btn = QPushButton("📁 Elegir…")
        btn.clicked.connect(self._pick_folder)
        h.addWidget(self.folder)
        h.addWidget(btn)
        f.addRow("Carpeta destino:", h)
        # formato
        self.fmt = QComboBox()
        self.fmt.addItems(["jpg", "png", "both"])
        self.fmt.setCurrentText(self.cfg["format"])
        f.addRow("Formato:", self.fmt)
        self.quality = QSpinBox()
        self.quality.setRange(1, 100)
        self.quality.setValue(self.cfg["jpeg_quality"])
        f.addRow("Calidad JPEG:", self.quality)
        self.prefix = QLineEdit(self.cfg["prefix"])
        self.prefix.setPlaceholderText("ej: \"proy_\" → proy_20261016_143205.jpg")
        f.addRow("Prefijo nombre:", self.prefix)
        # acción extra
        self.open_combo = QComboBox()
        self.open_combo.addItems(["none", "default", "custom"])
        self.open_combo.setCurrentText(self.cfg["open_after"])
        self.open_combo.currentTextChanged.connect(
            lambda t: self.editor.setEnabled(t == "custom"))
        f.addRow("Abrir después:", self.open_combo)
        self.editor = QLineEdit(self.cfg["editor_cmd"])
        self.editor.setPlaceholderText("comando con %f, ej: gimp %f")
        self.editor.setEnabled(self.cfg["open_after"] == "custom")
        f.addRow("Comando:", self.editor)
        return w

    def _tab_look(self):
        w = QWidget()
        f = QFormLayout(w)
        self.copy = QCheckBox("Copiar siempre al portapapeles")
        self.copy.setChecked(self.cfg["copy_clipboard"])
        f.addRow(self.copy)
        self.toast = QCheckBox("Notificación «Guardado y copiado ✔»")
        self.toast.setChecked(self.cfg["toast"])
        f.addRow(self.toast)
        self.sound = QCheckBox("Sonido de obturador")
        self.sound.setChecked(self.cfg["sound"])
        f.addRow(self.sound)
        self.preview = QCheckBox("Preview flotante que se desvanece")
        self.preview.setChecked(self.cfg["float_preview"])
        f.addRow(self.preview)
        self.prev_secs = QDoubleSpinBox()
        self.prev_secs.setRange(0.5, 10.0)
        self.prev_secs.setSingleStep(0.5)
        self.prev_secs.setValue(self.cfg["preview_seconds"])
        f.addRow("Duración preview (s):", self.prev_secs)
        self.magnifier = QCheckBox("Mostrar lupa alrededor del cursor")
        self.magnifier.setChecked(self.cfg["magnifier"])
        f.addRow(self.magnifier)
        self.zoom = QSpinBox()
        self.zoom.setRange(2, 10)
        self.zoom.setValue(self.cfg["magnifier_zoom"])
        self.zoom.setEnabled(self.magnifier.isChecked())
        self.magnifier.toggled.connect(self.zoom.setEnabled)
        f.addRow("Zoom de la lupa:", self.zoom)
        self.thirds = QCheckBox("Mostrar regla de tercios")
        self.thirds.setChecked(self.cfg["thirds_grid"])
        f.addRow(self.thirds)
        h = QHBoxLayout()
        self.accent_btn = QPushButton(self.cfg["accent"])
        self.accent_btn.setStyleSheet(
            f"background:{self.cfg['accent']};color:#000;border-radius:6px;padding:6px;")
        self.accent_btn.clicked.connect(self._pick_accent)
        h.addWidget(self.accent_btn)
        h.addStretch(1)
        f.addRow("Color del borde:", h)
        return w

    def _tab_system(self):
        w = QWidget()
        f = QFormLayout(w)
        self.autostart = QCheckBox("Arrancar automáticamente al iniciar la sesión")
        self.autostart.setChecked(self.cfg["autostart"])
        f.addRow(self.autostart)
        self.startup_notif = QCheckBox("Mostrar notificación al iniciar la app")
        self.startup_notif.setChecked(self.cfg["startup_notification"])
        f.addRow(self.startup_notif)
        info = QLabel("Ubicación de config:\n"
                      f"{CONFIG_FILE}")
        info.setWordWrap(True)
        f.addRow(info)
        return w

    # ------------------------------------------------------------ helpers
    def _pick_folder(self):
        d = QFileDialog.getExistingDirectory(self, "Elegir carpeta de destino",
                                             self.folder.text() or str(Path.home()))
        if d:
            self.folder.setText(d)

    def _pick_accent(self):
        c = QColorDialog.getColor(QColor(self.cfg["accent"]), self, "Color del borde")
        if c.isValid():
            self.accent_btn.setText(c.name())
            self.accent_btn.setStyleSheet(
                f"background:{c.name()};color:#000;border-radius:6px;padding:6px;")
            self._accent_val = c.name()

    def result_config(self) -> dict:
        cfg = dict(self.cfg)
        cfg.update({
            "hotkey": self.hotkey.hotkey_raw or "",
            "window_hover": self.win_hover.isChecked(),
            "save_folder": self.folder.text().strip(),
            "format": self.fmt.currentText(),
            "jpeg_quality": self.quality.value(),
            "prefix": self.prefix.text(),
            "open_after": self.open_combo.currentText(),
            "editor_cmd": self.editor.text().strip(),
            "copy_clipboard": self.copy.isChecked(),
            "toast": self.toast.isChecked(),
            "sound": self.sound.isChecked(),
            "float_preview": self.preview.isChecked(),
            "preview_seconds": self.prev_secs.value(),
            "magnifier": self.magnifier.isChecked(),
            "magnifier_zoom": self.zoom.value(),
            "thirds_grid": self.thirds.isChecked(),
            "accent": getattr(self, "_accent_val", self.cfg["accent"]),
            "autostart": self.autostart.isChecked(),
            "startup_notification": self.startup_notif.isChecked(),
        })
        return cfg
