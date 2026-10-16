# -*- coding: utf-8 -*-
"""UI de Screenshot Tool: ícono en el tray, coordinación de capturas
(selección / pantalla completa), guardado y preferencias.

Todo el stack Qt (QApplication, tray, overlays, diálogos) vive acá y corre
en el hilo PRINCIPAL. En Qt6/xcb un QApplication creado en un hilo
secundario mapea ventanas y corre timers pero jamás despacha eventos de
input (mouse/teclado) — el overlay se congela al primer click.
El hotkey global sí corre en su propio hilo (XGrabListener, hotkeys.py).
"""

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from PyQt6.QtCore import (QByteArray, QObject, QPoint, QRect, QRectF, Qt,
                          QTimer)
from PyQt6.QtGui import (QAction, QColor, QCursor, QIcon, QImage, QPainter,
                         QPen, QPixmap)
from PyQt6.QtNetwork import QLocalServer, QLocalSocket
from PyQt6.QtWidgets import (QApplication, QMenu, QMessageBox,
                             QSystemTrayIcon, QWidget)

from UTILS.capture import grab_screen, play_shutter
from UTILS.config import (APP_NAME, autostart_enabled, load_config,
                          save_config, set_autostart)
from UTILS.deps import HAS_MSS, HAS_PYNPUT, HAS_XLIB
from UTILS.hotkeys import HotkeyManager, hotkey_display
from UTILS.overlay import CaptureOverlay, FloatPreview, Toast
from UTILS.preferences import PreferencesDialog


def _icon_from_svg(svg_text: str) -> QIcon:
    """Renderiza un SVG a un QIcon con pixmaps reales en varios tamaños.

    En Cinnamon el tray es StatusNotifierItem (D-Bus): el ícono se publica
    como IconPixmap, así que un QIcon cargado sólo desde archivo/tema puede
    quedar vacío y mostrarse invisible. Pixmaps rasterizados garantizan
    un ícono visible."""
    try:
        from PyQt6.QtSvg import QSvgRenderer
    except ImportError:
        return QIcon()
    renderer = QSvgRenderer(QByteArray(svg_text.encode("utf-8")))
    if not renderer.isValid():
        return QIcon()
    icon = QIcon()
    for size in (16, 22, 24, 32, 48):
        img = QImage(size, size, QImage.Format.Format_ARGB32)
        img.fill(Qt.GlobalColor.transparent)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        renderer.render(p, QRectF(0, 0, size, size))
        p.end()
        icon.addPixmap(QPixmap.fromImage(img))
    return icon


class ScreenshotApp(QObject):
    def __init__(self, qapp: QApplication):
        super().__init__()
        self.qapp = qapp
        self.cfg = load_config()
        self._overlay = None
        self._frozen = None
        self._img_origin = QPoint(0, 0)
        self._sct = None
        self._prefs = None
        self._hotkey = None
        self._popups = []

        self._make_tray()
        self._start_hotkey()

    # ------------------------------------------------------------- tray
    def _tray_icon(self) -> QIcon:
        # Preferimos el SVG embebido (SVGIconGenerator): no depende de
        # archivos externos y siempre produce pixmaps reales para SNI.
        svg_text = ""
        try:
            from UTILS.SVGIconGenerator import build_svg
            svg_text = build_svg()
        except Exception:
            pass
        if not svg_text:
            root = Path(__file__).resolve().parent.parent
            for rel in ("icon.svg", "CI-CD-LOCAL/ICONS/icon.svg"):
                f = root / rel
                if f.exists():
                    try:
                        svg_text = f.read_text(encoding="utf-8")
                    except OSError:
                        continue
                    break
        if svg_text:
            ic = _icon_from_svg(svg_text)
            if not ic.isNull():
                return ic
        ic = QIcon.fromTheme("camera-photo")
        if not ic.isNull():
            return ic
        pm = QPixmap(64, 64)
        pm.fill(QColor("#1e293b"))
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(QPen(QColor("#e2e8f0"), 4))
        p.drawRect(10, 18, 44, 34)
        p.drawRect(24, 10, 16, 8)
        p.setBrush(QColor("#e2e8f0"))
        p.drawEllipse(22, 26, 20, 20)
        p.end()
        return QIcon(pm)

    def _make_tray(self):
        self.tray = QSystemTrayIcon(self._tray_icon())
        self.tray.setToolTip(f"{APP_NAME} — presioná {hotkey_display(self.cfg['hotkey']) or '(sin hotkey)'}")
        menu = QMenu()
        # IMPORTANTE: las QAction se crean CON padre (menu). Sin padre, Python
        # pierde la referencia al salir de la función, el GC destruye la acción
        # y Qt la remueve del menú → el menú queda VACÍO (por eso Cinnamon no
        # mostraba nada al hacer click).
        a_open = QAction("📂  Abrir carpeta de capturas", menu)
        a_open.triggered.connect(self._open_folder)
        menu.addAction(a_open)
        a_pref = QAction("⚙️  Preferencias…", menu)
        a_pref.triggered.connect(self.open_preferences)
        menu.addAction(a_pref)
        menu.addSeparator()
        a_quit = QAction("❌  Salir", menu)
        a_quit.triggered.connect(self._quit)
        menu.addAction(a_quit)

        self._menu = menu
        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray)
        self.tray.show()

    def _on_tray(self, reason):
        # En Cinnamon (xapp-status / StatusNotifierItem) el applet dibuja el
        # menú vía dbusmenu en click derecho; en click izquierdo sólo emite
        # activated() y espera que la app haga popup(). La guardia
        # isVisible() evita un doble popup en trays XEmbed donde Qt sí
        # muestra el context menu automáticamente.
        # El popup se difiere con singleShot(0): llamarlo de forma síncrona
        # dentro del handler D-Bus puede quedar atrapado por el grab del
        # click y el menú se cierra al instante.
        menu = self.tray.contextMenu()
        if (reason in (QSystemTrayIcon.ActivationReason.Trigger,
                       QSystemTrayIcon.ActivationReason.Context)
                and menu and not menu.isVisible()):
            QTimer.singleShot(0, lambda: menu.popup(QCursor.pos()))

    # ----------------------------------------------------------- hotkey
    def _start_hotkey(self):
        if self._hotkey:
            self._hotkey.stop()
        combo = self.cfg.get("hotkey", "")
        self._hotkey = HotkeyManager(combo)
        self._hotkey.triggered.connect(self.capture_selected)
        self._hotkey.failed.connect(self._hotkey_fail)

    def _hotkey_fail(self):
        if not HAS_PYNPUT and not HAS_XLIB:
            self.tray.showMessage(APP_NAME,
                                  "⚠️ No se pudo registrar el atajo global "
                                  "(falta pynput o python-xlib).",
                                  QSystemTrayIcon.MessageIcon.Critical, 6000)

    # ---------------------------------------------------------- capturas
    def _ensure_grab(self):
        if not HAS_MSS:
            self.tray.showMessage(APP_NAME, "⚠️ Falta librería mss.",
                                  QSystemTrayIcon.MessageIcon.Critical, 5000)
            return False
        self._frozen, self._img_origin = grab_screen()
        return True

    def _reset_capture(self):
        """Vuelve al estado inicial: sin overlay y sin la imagen congelada
        en memoria (un frame full-screen son varios MB)."""
        self._overlay = None
        self._frozen = None
        self._img_origin = QPoint(0, 0)

    def capture_selected(self):
        if self._overlay:
            return     # ya hay una captura en curso
        if not self._ensure_grab():
            return
        self._overlay = CaptureOverlay(self._frozen, self._img_origin, self.cfg)
        self._overlay.done.connect(self._on_sel_done)
        self._overlay.canceled.connect(self._reset_capture)
        self._overlay.destroyed.connect(self._reset_capture)

    def capture_full(self):
        if not self._ensure_grab():
            return
        virt = QApplication.primaryScreen().virtualGeometry()
        r = QRect(0, 0, self._frozen.width(), self._frozen.height())
        img = self._frozen.copy(r)
        self._save(img, QRect(virt))
        self._reset_capture()

    def _on_sel_done(self, r: QRect):
        img_rect = self._img_from_widget(r)
        img = self._frozen.copy(img_rect)
        virt = QApplication.primaryScreen().virtualGeometry()
        self._save(img, virt)
        self._reset_capture()

    def _img_from_widget(self, r: QRect) -> QRect:
        virt = QApplication.primaryScreen().virtualGeometry()
        sx = self._frozen.width() / max(1, virt.width())
        sy = self._frozen.height() / max(1, virt.height())
        return QRect(int((r.x() - virt.x()) * sx), int((r.y() - virt.y()) * sy),
                     int(r.width() * sx), int(r.height() * sy))

    # ----------------------------------------------------------- guardado
    def _save(self, img: QImage, sel_widget_rect: QRect | None = None):
        folder = Path(self.cfg["save_folder"])
        try:
            folder.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            self.tray.showMessage(APP_NAME, f"⚠️ No pude crear {folder}: {e}",
                                  QSystemTrayIcon.MessageIcon.Critical, 5000)
            return
        fmts = ["jpg", "png"] if self.cfg["format"] == "both" else [self.cfg["format"]]
        base = f"{self.cfg['prefix']}{datetime.now():%Y%m%d_%H%M%S}"
        paths = []
        for f in fmts:
            path = folder / f"{base}.{f}"
            ok = img.save(str(path), "JPG" if f == "jpg" else "PNG",
                          self.cfg["jpeg_quality"])
            if ok:
                paths.append(path)
        if not paths:
            self.tray.showMessage(APP_NAME, "⚠️ No se pudo guardar la imagen.",
                                  QSystemTrayIcon.MessageIcon.Critical, 5000)
            return
        target = paths[0]
        if self.cfg["copy_clipboard"]:
            QApplication.clipboard().setImage(img)
        if self.cfg["sound"]:
            play_shutter()
        text = "✔ Guardado y copiado al portapapeles" if self.cfg["copy_clipboard"] \
            else f"✔ Guardado: {folder.name}/{target.name}"
        self._last_anchor = sel_widget_rect
        if self.cfg["toast"]:
            QTimer.singleShot(60, lambda: self._popup(Toast(text, sel_widget_rect)))
        if self.cfg["float_preview"]:
            QTimer.singleShot(80, lambda: self._popup(FloatPreview(
                QPixmap.fromImage(img), self.cfg["preview_seconds"], sel_widget_rect)))
        # abrir después
        oa = self.cfg["open_after"]
        if oa == "default":
            subprocess.Popen(["xdg-open", str(target)],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif oa == "custom" and self.cfg["editor_cmd"]:
            cmd = self.cfg["editor_cmd"].replace("%f", str(target))
            subprocess.Popen(cmd, shell=True, stdout=subprocess.DEVNULL,
                             stderr=subprocess.DEVNULL)

    def _popup(self, w: QWidget) -> None:
        """Mantiene viva la referencia para que el GC no destruya la ventana flotante."""
        self._popups.append(w)
        w.destroyed.connect(lambda *_: self._popups.remove(w) if w in self._popups else None)

    # ------------------------------------------------------------ más UI
    def open_preferences(self):
        if self._prefs:
            self._prefs.raise_()
            self._prefs.activateWindow()
            return
        d = PreferencesDialog(self.cfg)
        d.show()
        self._prefs = d
        d.destroyed.connect(lambda: setattr(self, "_prefs", None))

        def apply():
            self.cfg = d.result_config()
            save_config(self.cfg)
            if self.cfg["autostart"]:
                set_autostart(True)
            elif autostart_enabled():
                set_autostart(False)
            self._start_hotkey()
            self.tray.setToolTip(f"{APP_NAME} — presioná "
                                 f"{hotkey_display(self.cfg['hotkey']) or '(sin hotkey)'}")
        d.accepted.connect(apply)

    def _open_folder(self):
        f = Path(self.cfg["save_folder"])
        f.mkdir(parents=True, exist_ok=True)
        subprocess.Popen(["xdg-open", str(f)],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _toggle_autostart(self, on: bool):
        set_autostart(on)
        self.cfg["autostart"] = on
        save_config(self.cfg)

    def _about(self):
        QMessageBox.information(
            None, APP_NAME,
            f"<b>{APP_NAME}</b><br/>Capturas estilo GreenShot para Linux Mint.<br/><br/>"
            f"Atajo actual: <b>{hotkey_display(self.cfg['hotkey']) or '(ninguno)'}</b><br/>"
            "F10 (o tu atajo) → seleccioná el área → se guarda y copia solo.<br/><br/>"
            "Config: ~/.config/screenshot-tool/config.json")

    def _quit(self):
        try:
            self._hotkey.stop()
        except Exception:
            pass
        self.tray.hide()
        self.qapp.quit()


def single_instance():
    """Devuelve el QLocalServer si somos la única instancia, None si ya hay otra.
    El server se devuelve para que el llamador mantenga la referencia viva."""
    key = "screenshot-tool-singleton"
    sock = QLocalSocket()
    sock.connectToServer(key)
    if sock.waitForConnected(200):
        sock.disconnectFromServer()
        return None
    QLocalServer.removeServer(key)
    server = QLocalServer()
    server.listen(key)
    return server


def main():
    # Qt exige el hilo principal en X11: un QApplication en worker thread
    # nunca recibe input (verificado). Todo el UI vive en este módulo igual.
    qapp = QApplication(sys.argv)
    qapp.setApplicationName("screenshot-tool")
    qapp.setQuitOnLastWindowClosed(False)

    server = single_instance()
    if server is None:
        print("⚠️ Screenshot Tool ya está corriendo.")
        sys.exit(0)
    qapp._single_instance_server = server   # mantener vivo el lock

    app = ScreenshotApp(qapp)
    hk = hotkey_display(app.cfg["hotkey"])
    app.tray.showMessage(
        APP_NAME,
        f"Listo 📸\nAtajo actual: {hk or '(ninguno, configurá en Preferencias)'}",
        QSystemTrayIcon.MessageIcon.Information, 4000)
    sys.exit(qapp.exec())
