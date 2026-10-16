"""Ícones desenhados em código (sem arquivos externos) e miniaturas de mapas."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, QSize, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap

from mindforge.document import Document
from mindforge.model.topic import MindMap
from mindforge.view.painting import paint_marker


def marker_icon(key: str, size: int = 20) -> QIcon:
    pm = QPixmap(size * 2, size * 2)
    pm.setDevicePixelRatio(2)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    paint_marker(p, key, QRectF(1, 1, size - 2, size - 2))
    p.end()
    return QIcon(pm)


def draw_app_icon(p: QPainter, s: float) -> None:
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    bg = QPainterPath()
    bg.addRoundedRect(QRectF(s * 0.06, s * 0.06, s * 0.88, s * 0.88), s * 0.2, s * 0.2)
    p.fillPath(bg, QColor("#24364F"))
    c = QPointF(s * 0.5, s * 0.5)
    nodes = [(0.24, 0.3, "#E5534B"), (0.78, 0.28, "#F0883E"), (0.22, 0.72, "#3FA66B"),
             (0.78, 0.72, "#2F80ED")]
    for x, y, col in nodes:
        pt = QPointF(s * x, s * y)
        path = QPainterPath(c)
        path.cubicTo(QPointF((c.x() + pt.x()) / 2, c.y()), QPointF((c.x() + pt.x()) / 2, pt.y()), pt)
        p.setPen(QPen(QColor(col), s * 0.045, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(col))
        p.drawEllipse(pt, s * 0.075, s * 0.075)
    p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(c, s * 0.12, s * 0.12)


def app_icon() -> QIcon:
    icon = QIcon()
    for sz in (16, 32, 64, 128, 256, 512):
        pm = QPixmap(sz, sz)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        draw_app_icon(p, sz)
        p.end()
        icon.addPixmap(pm)
    return icon


def render_thumbnail(m: MindMap, size: QSize, dpr: float = 2.0) -> QPixmap:
    from mindforge.view.scene import MindScene   # import tardio (evita ciclo)
    doc = Document(m)
    scene = MindScene(doc)
    scene.sync()
    pm = QPixmap(round(size.width() * dpr), round(size.height() * dpr))
    pm.setDevicePixelRatio(dpr)
    pm.fill(QColor(scene.background_color))
    with scene.exporting() as rect:
        src = rect.adjusted(-30, -30, 30, 30)
        tw, th = size.width() - 12, size.height() - 12
        k = min(tw / src.width(), th / src.height())
        w, h = src.width() * k, src.height() * k
        target = QRectF((size.width() - w) / 2, (size.height() - h) / 2, w, h)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
        scene.render(p, target, src, Qt.AspectRatioMode.IgnoreAspectRatio)
        p.end()
    scene.deleteLater()
    return pm
