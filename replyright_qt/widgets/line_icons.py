from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget


class LineIcon(QWidget):
    """Small native line icon set for the sidebar.

    The app is packaged as a PyInstaller desktop build, so these icons are drawn
    with Qt instead of adding a web-font or SVG runtime dependency.
    """

    def __init__(self, name: str, size: int = 22, parent=None) -> None:
        super().__init__(parent)
        self._name = name
        self._color = QColor("#9fb6d8")
        self._active_color = QColor("#ffffff")
        self.setFixedSize(size, size)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

    def set_active(self, active: bool) -> None:
        self.setProperty("active", "true" if active else "false")
        self.update()

    def paintEvent(self, event) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        color = self._active_color if self.property("active") == "true" else self._color
        pen = QPen(color, 1.8, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        w = float(self.width())
        h = float(self.height())
        n = self._name

        if n == "inbox":
            painter.drawRoundedRect(4, 7, w - 8, h - 8, 3, 3)
            painter.drawLine(QPointF(4, 12), QPointF(8, 12))
            painter.drawLine(QPointF(w - 8, 12), QPointF(w - 4, 12))
            painter.drawLine(QPointF(8, 12), QPointF(10, 15))
            painter.drawLine(QPointF(w - 8, 12), QPointF(w - 10, 15))
        elif n == "urgent":
            path = QPainterPath()
            path.moveTo(w / 2, 3)
            path.lineTo(w - 4, h - 4)
            path.lineTo(4, h - 4)
            path.closeSubpath()
            painter.drawPath(path)
            painter.drawLine(QPointF(w / 2, 8), QPointF(w / 2, 14))
            painter.drawPoint(QPointF(w / 2, 17))
        elif n == "vip":
            self._draw_star(painter, w / 2, h / 2 + 1, 8, 3.6)
        elif n == "missing":
            painter.drawEllipse(4, 4, w - 8, h - 8)
            painter.drawPath(self._question_path(w, h))
            painter.drawPoint(QPointF(w / 2, h - 6))
        elif n == "kyc":
            path = QPainterPath()
            path.moveTo(w / 2, 3)
            path.lineTo(w - 5, 7)
            path.lineTo(w - 6, 14)
            path.quadTo(w / 2, h - 3, 6, 14)
            path.lineTo(5, 7)
            path.closeSubpath()
            painter.drawPath(path)
            painter.drawLine(QPointF(8, 11), QPointF(11, 14))
            painter.drawLine(QPointF(11, 14), QPointF(16, 9))
        elif n == "admin":
            painter.drawEllipse(7, 4, 8, 8)
            painter.drawArc(4, 12, 14, 9, 0, 180 * 16)
            painter.drawLine(QPointF(17, 6), QPointF(20, 6))
            painter.drawLine(QPointF(18.5, 4.5), QPointF(18.5, 7.5))
        elif n == "settings":
            painter.drawEllipse(7, 7, 8, 8)
            for i in range(8):
                a = math.radians(i * 45)
                x1 = w / 2 + math.cos(a) * 7
                y1 = h / 2 + math.sin(a) * 7
                x2 = w / 2 + math.cos(a) * 9
                y2 = h / 2 + math.sin(a) * 9
                painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        else:
            painter.drawEllipse(4, 4, w - 8, h - 8)

    def _draw_star(self, painter: QPainter, cx: float, cy: float, outer: float, inner: float) -> None:
        path = QPainterPath()
        for i in range(10):
            angle = math.radians(-90 + i * 36)
            radius = outer if i % 2 == 0 else inner
            point = QPointF(cx + math.cos(angle) * radius, cy + math.sin(angle) * radius)
            if i == 0:
                path.moveTo(point)
            else:
                path.lineTo(point)
        path.closeSubpath()
        painter.drawPath(path)

    def _question_path(self, w: float, h: float) -> QPainterPath:
        path = QPainterPath()
        path.moveTo(w / 2 - 4, h / 2 - 3)
        path.cubicTo(w / 2 - 3, h / 2 - 7, w / 2 + 5, h / 2 - 7, w / 2 + 4, h / 2 - 2)
        path.cubicTo(w / 2 + 4, h / 2 + 1, w / 2, h / 2 + 1, w / 2, h / 2 + 4)
        return path
