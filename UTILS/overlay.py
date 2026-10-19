# -*- coding: utf-8 -*-
"""Overlay de captura a pantalla completa (selección de área con crosshair,
lupa, regla de tercios y detección de ventana bajo el cursor), más los
widgets flotantes de feedback: Toast y FloatPreview."""

from pathlib import Path

from UTILS.qt_compat.QtCore import (QEasingCurve, QPoint, QPropertyAnimation,
                                    QRect, Qt, QTimer, pyqtSignal)
from UTILS.qt_compat.QtGui import (QColor, QCursor, QFont, QImage, QPainter,
                                   QPen, QPixmap)
from UTILS.qt_compat.QtWidgets import QApplication, QLabel, QMenu, QWidget

from UTILS.screen_capture import window_rect_at
from UTILS.hotkeys import hotkey_display
from UTILS.system import open_path


class CaptureOverlay(QWidget):
    """Pantalla congelada a fullscreen: mirita, guías, lupa, regla de tercios."""
    done = pyqtSignal(QRect, str)  # rect en coords del widget + título de ventana (si aplica)
    canceled = pyqtSignal()

    def __init__(self, frozen: QImage, img_origin: QPoint, cfg: dict):
        super().__init__()
        self.frozen = frozen
        self.img_origin = img_origin
        self.cfg = cfg
        self._virt = QApplication.primaryScreen().virtualGeometry()
        self._origin: QPoint | None = None
        self._cur = self.mapFromGlobal(QCursor.pos())
        self._hover_win: QRect | None = None
        self._hover_name = ""
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)

        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.X11BypassWindowManagerHint)
        self.setGeometry(self._virt)
        self.setMouseTracking(True)
        self.setCursor(Qt.CursorShape.BlankCursor)

        # detección de ventana bajo el cursor (throttleada)
        self._win_timer = QTimer(self)
        self._win_timer.setInterval(90)
        self._win_timer.timeout.connect(self._detect_window)
        self._win_timer.start()

        self._accent = QColor(cfg.get("accent", "#00c8ff"))
        self._zoom = int(cfg.get("magnifier_zoom", 5))
        self.activateWindow()
        self.raise_()
        self.show()
        self.grabKeyboard()          # override-redirect no toma foco solo; sin esto ESC/Enter no llegan

    # NOTA: no usar applicationStateChanged para auto-cerrar: con
    # X11BypassWindowManagerHint Qt reporta ApplicationInactive en
    # transiciones espurias (grabs de teclado/puntero) y cerraba el
    # overlay a mitad del drag dejando el grab de puntero colgado.

    # -------------------------------------------------------- geometría
    def _virt_origin(self) -> QPoint:
        return QPoint(self._virt.x(), self._virt.y())

    def _to_widget(self, r: QRect) -> QRect:
        o = self._virt_origin()
        return QRect(r.x() - o.x(), r.y() - o.y(), r.width(), r.height())

    def _scale(self):
        sx = self.frozen.width() / max(1, self._virt.width())
        sy = self.frozen.height() / max(1, self._virt.height())
        return sx, sy

    def _to_img(self, r: QRect) -> QRect:
        sx, sy = self._scale()
        return QRect(int((r.x() - self._virt.x()) * sx),
                     int((r.y() - self._virt.y()) * sy),
                     int(r.width() * sx), int(r.height() * sy))

    def _sel(self) -> QRect:
        if self._origin is None:
            return QRect()
        return QRect(self._origin, self._cur).normalized()

    # ------------------------------------------------------------ eventos
    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._origin = e.position().toPoint()
            self._hover_win = None
            self.update()
        elif e.button() == Qt.MouseButton.RightButton:
            self.canceled.emit()
            self.close()

    def mouseMoveEvent(self, e):
        self._cur = e.position().toPoint()
        self.update()

    def mouseReleaseEvent(self, e):
        if e.button() != Qt.MouseButton.LeftButton or self._origin is None:
            return
        r = self._sel()
        self._origin = None
        if r.width() < 6 or r.height() < 6:
            # arrastre demasiado chico → lo ignoramos, puede seguir seleccionando
            self.update()
            return
        # ventana topmost bajo el cursor al soltar → su título pasa al nombre
        # de archivo (mismo criterio que el highlight amarillo)
        o = self._virt_origin()
        res = window_rect_at(self._cur.x() + o.x(), self._cur.y() + o.y())
        self.done.emit(r, res[1] if res else "")
        self.close()

    def closeEvent(self, e):
        # Salir del modo captura dejando todo como estaba: parar el timer
        # de detección de ventana y soltar el grab de teclado (grabKeyboard
        # del __init__) para que el sistema recupere el input normal.
        self._win_timer.stop()
        self.releaseKeyboard()
        super().closeEvent(e)

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Escape:
            self.canceled.emit()
            self.close()
        elif e.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.confirm()

    def confirm(self):
        """Confirma la captura como si se hubiera presionado Enter:
        captura la ventana bajo el cursor (si no se está arrastrando).
        También lo llama la UI cuando el hotkey global se dispara de nuevo
        con el overlay abierto (F10 de nuevo = Enter).

        Hace una consulta fresca a window_rect_at: la cache del timer
        (_hover_win) puede estar vencida o ni existir si window_hover
        está desactivado."""
        if self._origin is not None:
            return
        o = self._virt_origin()
        res = window_rect_at(self._cur.x() + o.x(), self._cur.y() + o.y())
        if res:
            self.done.emit(self._to_widget(res[0]), res[1] or "")
        elif self._hover_win:
            # fallback: última ventana detectada por el timer
            self.done.emit(self._hover_win, self._hover_name)
        else:
            return
        self.close()

    def _detect_window(self):
        if self._origin is not None or not self.cfg.get("window_hover", True):
            return
        o = self._virt_origin()
        res = window_rect_at(self._cur.x() + o.x(), self._cur.y() + o.y())
        self._hover_win = self._to_widget(res[0]) if res else None
        self._hover_name = res[1][:60] if res else ""
        if self.isVisible():
            self.update()

    # ------------------------------------------------------------- paint
    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        full = self.rect()
        p.drawImage(full, self.frozen)
        # estilo Greenshot: NO se oscurece la pantalla; solo se tinta la selección

        sel = self._sel()
        dragging = self._origin is not None

        if not sel.isNull():
            sel = sel.intersected(full)
            # tint verde translúcido + borde del color de acento
            tint = QColor(self._accent)
            tint.setAlpha(50)
            p.fillRect(sel, tint)
            p.setPen(QPen(self._accent, 2))
            p.drawRect(sel)
            # regla de tercios (líneas oscuras: la zona ya está tintada clara)
            if self.cfg.get("thirds_grid", True):
                pen = QPen(QColor(0, 0, 0, 110), 1, Qt.PenStyle.DashLine)
                p.setPen(pen)
                for fx in (1 / 3, 2 / 3):
                    x = sel.x() + int(sel.width() * fx)
                    p.drawLine(x, sel.y(), x, sel.bottom())
                for fy in (1 / 3, 2 / 3):
                    y = sel.y() + int(sel.height() * fy)
                    p.drawLine(sel.x(), y, sel.right(), y)
            # handles con el color de acento
            p.setPen(QPen(QColor(0, 0, 0), 1))
            p.setBrush(self._accent)
            hs = 8
            hpts = [sel.topLeft(), QPoint(sel.center().x(), sel.top()),
                    sel.topRight(), QPoint(sel.left(), sel.center().y()),
                    QPoint(sel.right(), sel.center().y()), sel.bottomLeft(),
                    QPoint(sel.center().x(), sel.bottom()), sel.bottomRight()]
            for hp in hpts:
                p.drawRect(hp.x() - hs // 2, hp.y() - hs // 2, hs, hs)
            # dimensiones: texto verde adentro, abajo a la derecha (estilo Greenshot)
            label = f"{sel.width()} × {sel.height()}"
            f = QFont()
            f.setBold(True)
            f.setPointSize(12)
            p.setFont(f)
            fm = p.fontMetrics()
            lx = sel.right() - fm.horizontalAdvance(label) - 8
            ly = sel.bottom() - 8
            if sel.width() < fm.horizontalAdvance(label) + 20:
                lx = sel.right() + 6              # rect muy angosto → afuera
                ly = sel.bottom()
            dark = QColor(self._accent).darker(160)
            p.setPen(QColor(255, 255, 255, 170))
            p.drawText(lx + 1, ly + 1, label)     # sombra clara para legibilidad
            p.setPen(dark)
            p.drawText(lx, ly, label)

        # ventana resaltada (modo sin drag)
        if not dragging and self._hover_win:
            p.setPen(QPen(QColor(255, 190, 0, 230), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(self._hover_win)
            if self._hover_name:
                self._label(p, self._hover_name, self._hover_win.topLeft(), filechip=True)

        # crosshair negro grueso estilo Greenshot (halo claro para fondos oscuros)
        if not dragging:
            p.setPen(QPen(QColor(255, 255, 255, 130), 5))
            p.drawLine(0, self._cur.y(), full.width(), self._cur.y())
            p.drawLine(self._cur.x(), 0, self._cur.x(), full.height())
            p.setPen(QPen(QColor(0, 0, 0, 235), 3))
            p.drawLine(0, self._cur.y(), full.width(), self._cur.y())
            p.drawLine(self._cur.x(), 0, self._cur.x(), full.height())
            if self.cfg.get("magnifier", True):
                self._draw_magnifier(p)
            self._draw_hint(p)
        elif self.cfg.get("magnifier", True):
            self._draw_magnifier(p)

        p.end()

    def _label(self, p: QPainter, text: str, at: QPoint, above=False, filechip=False):
        f = QFont()
        f.setPointSize(10)
        f.setBold(True)
        p.setFont(f)
        fm = p.fontMetrics()
        w = fm.horizontalAdvance(text) + 14
        h = fm.height() + 8
        x = min(max(4, at.x()), self.width() - w - 4)
        y = at.y() - h - 6 if above and at.y() - h - 6 > 2 else at.y() + 6
        r = QRect(x, y, w, h)
        p.fillRect(r, QColor(10, 12, 16, 200))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawRect(r)
        p.setPen(QColor(255, 255, 255, 235))
        p.drawText(r, Qt.AlignmentFlag.AlignCenter, text)

    def _draw_magnifier(self, p: QPainter):
        src_size = 44
        z = max(2, self._zoom)
        box = src_size * z
        cx, cy = self._cur.x(), self._cur.y()
        # posición (cerca del cursor, flip si se va de pantalla)
        bx = cx + 20
        by = cy + 20
        if bx + box > self.width() - 4:
            bx = cx - box - 20
        if by + box > self.height() - 4:
            by = cy - box - 20
        sx, sy = self._scale()
        # recorte fuente (centrado en cursor)
        half = src_size // 2
        src = QRect(int((cx + self._virt.x() - self.img_origin.x()) * sx) - half * 2,
                    int((cy + self._virt.y() - self.img_origin.y()) * sy) - half * 2,
                    src_size * 2, src_size * 2)
        p.save()
        p.setClipRect(QRect(bx, by, box, box))
        p.drawImage(QRect(bx, by, box, box), self.frozen, src)
        p.restore()
        # retícula central
        p.setPen(QPen(QColor(255, 0, 90, 200), 1))
        mid = box // 2
        p.drawLine(bx, by + mid, bx + box, by + mid)
        p.drawLine(bx + mid, by, bx + mid, by + box)
        p.setPen(QPen(QColor(0, 0, 0), 2))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawRect(bx - 1, by - 1, box + 2, box + 2)
        p.setPen(QPen(QColor(255, 255, 255, 180), 1))
        p.drawRect(bx - 3, by - 3, box + 6, box + 6)
        # texto de coordenadas
        self._label(p, f"x={cx}  y={cy}", QPoint(bx, by + box + 10))

    def _draw_hint(self, p: QPainter):
        f = QFont()
        f.setPointSize(11)
        p.setFont(f)
        lines = []
        if self.cfg.get("window_hover", True):
            lines.append("🖱️  Clic y arrastrá para seleccionar un área")
            hk = hotkey_display(self.cfg.get("hotkey") or "")
            confirm = f"Enter / {hk}" if hk else "Enter"
            lines.append(f"📐  {confirm} → capturar la ventana señalada")
        else:
            lines.append("🖱️  Clic y arrastrá para seleccionar un área")
        lines.append("⎋  ESC o clic derecho para cancelar")
        fm = p.fontMetrics()
        w = max(fm.horizontalAdvance(l) for l in lines) + 40
        h = fm.height() * len(lines) + 22
        x = (self.width() - w) // 2
        y = self.height() - h - 30
        r = QRect(x, y, w, h)
        p.fillRect(r, QColor(10, 12, 16, 205))
        p.setPen(QPen(QColor(255, 255, 255, 40), 1))
        p.drawRect(r)
        p.setPen(QColor(255, 255, 255, 230))
        for i, l in enumerate(lines):
            p.drawText(QRect(x + 20, y + 11 + i * fm.height(), w - 40, fm.height()),
                       Qt.AlignmentFlag.AlignLeft, l)


class Toast(QLabel):
    """Cartelito flotante de confirmación que se cierra solo (~2.6 s)."""

    def __init__(self, text: str, anchor: QRect | None = None):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setStyleSheet(
            "QLabel{background:#111827;border:1px solid #3b82f6;border-radius:8px;"
            "color:#f9fafb;padding:10px 18px;font-size:12px;}")
        self.setText(text)
        self.adjustSize()
        ag = QApplication.primaryScreen().availableGeometry()
        if anchor and not anchor.isNull():
            x = anchor.x() + anchor.width() // 2 - self.width() // 2
            y = anchor.y() + anchor.height() + 20
        else:
            x = ag.center().x() - self.width() // 2
            y = ag.bottom() - self.height() - 28
        self.move(max(ag.left(), min(x, ag.right() - self.width())),
                  max(ag.top(), min(y, ag.bottom() - self.height())))
        self.show()
        QTimer.singleShot(2600, self.close)


class FloatPreview(QWidget):
    """Miniatura flotante de la captura que se desvanece tras N segundos.

    Interactiva: clic izquierdo abre el archivo en el visor de fotos,
    clic derecho muestra un menú (abrir, carpeta, copiar imagen, cerrar)
    y pasar el mouse por encima pausa el desvanecimiento."""

    def __init__(self, pix: QPixmap, seconds: float, anchor: QRect | None,
                 path=None):
        super().__init__()
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint |
                            Qt.WindowType.X11BypassWindowManagerHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(260, 190)
        self._path = Path(path) if path else None
        self._full = pix          # imagen completa (para copiar al portapapeles)
        self._pix = pix.scaled(240, 150, Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        lab = QLabel(self)
        lab.setPixmap(self._pix)
        lab.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lab.setGeometry(10, 10, 240, 150)
        lab.setStyleSheet("background:transparent;")
        hint = QLabel("clic: abrir  -  clic der: opciones", self)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setGeometry(10, 164, 240, 16)
        hint.setStyleSheet("color:#e5e7eb;font-size:10px;font-weight:bold;"
                           "background:rgba(17,24,39,190);border-radius:6px;")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        ag = QApplication.primaryScreen().availableGeometry()
        x = ag.right() - self.width() - 24
        y = ag.bottom() - self.height() - 24
        if anchor and not anchor.isNull():
            x = anchor.x() + anchor.width() - self.width() // 2
            y = anchor.y() + anchor.height() + 20
        self.move(max(ag.left(), min(x, ag.right() - self.width())),
                  max(ag.top(), min(y, ag.bottom() - self.height())))
        self.show()
        self._anim = QPropertyAnimation(self, b"windowOpacity")
        self._anim.setDuration(500)
        self._anim.setStartValue(1.0)
        self._anim.setEndValue(0.0)
        self._anim.setEasingCurve(QEasingCurve.Type.InOutQuad)
        # Timer como miembro: enterEvent lo pausa, leaveEvent lo reanuda.
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._anim.start)
        self._timer.start(int(seconds * 1000))
        self._anim.finished.connect(self.close)

    def enterEvent(self, e):
        # Pausar el fade mientras el mouse está encima del preview.
        self._timer.stop()
        self._anim.stop()
        self.setWindowOpacity(1.0)
        super().enterEvent(e)

    def leaveEvent(self, e):
        self._timer.start(1200)   # margen extra antes de seguir desvaneciendo
        super().leaveEvent(e)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            if self._path:
                open_path(self._path)
            self.close()
        elif e.button() == Qt.MouseButton.RightButton:
            self._menu(e.globalPosition().toPoint())
        else:
            super().mousePressEvent(e)

    def _menu(self, global_pos: QPoint):
        m = QMenu(self)
        a_open = m.addAction("🖼  Abrir en el visor")
        a_dir = m.addAction("📁  Abrir carpeta")
        a_copy = m.addAction("📋  Copiar imagen")
        m.addSeparator()
        a_close = m.addAction("✖  Cerrar")
        a_open.setEnabled(self._path is not None)
        a_dir.setEnabled(self._path is not None)
        act = m.exec(global_pos)
        if act is a_open and self._path:
            open_path(self._path)
            self.close()
        elif act is a_dir and self._path:
            open_path(self._path.parent)
            self.close()
        elif act is a_copy:
            QApplication.clipboard().setImage(self._full.toImage())
        elif act is a_close:
            self.close()
