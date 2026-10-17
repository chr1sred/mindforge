"""Ícones vetoriais desenhados em código (traço fino, no estilo do macOS)."""
from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QPainter, QPainterPath, QPen, QPixmap
from mindforge.i18n import tr

S = 24.0   # grade de desenho


def _pen(color: QColor, w: float = 1.6) -> QPen:
    return QPen(color, w, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap, Qt.PenJoinStyle.RoundJoin)


def _topic(p: QPainter, c: QColor) -> None:
    p.drawRoundedRect(QRectF(3, 7, 18, 10), 3, 3)


def _add_topic(p: QPainter, c: QColor) -> None:
    p.drawRoundedRect(QRectF(2.5, 8, 13, 8), 2.5, 2.5)
    p.drawLine(QPointF(19.5, 8.5), QPointF(19.5, 15.5))
    p.drawLine(QPointF(16, 12), QPointF(23, 12))


def _subtopic(p: QPainter, c: QColor) -> None:
    p.drawRoundedRect(QRectF(2, 4, 10, 6), 2, 2)
    path = QPainterPath(QPointF(7, 10))
    path.lineTo(QPointF(7, 17))
    path.lineTo(QPointF(12, 17))
    p.drawPath(path)
    p.drawRoundedRect(QRectF(12, 14, 10, 6), 2, 2)


def _floating(p: QPainter, c: QColor) -> None:
    pen = p.pen()
    pen.setStyle(Qt.PenStyle.DashLine)
    pen.setDashPattern([2, 2])
    p.setPen(pen)
    p.drawRoundedRect(QRectF(3, 7, 18, 10), 3, 3)


def _relation(p: QPainter, c: QColor) -> None:
    path = QPainterPath(QPointF(4, 18))
    path.cubicTo(QPointF(4, 6), QPointF(20, 6), QPointF(20, 16))
    p.drawPath(path)
    p.drawLine(QPointF(20, 16), QPointF(17, 13))
    p.drawLine(QPointF(20, 16), QPointF(22.5, 12.5))
    p.setBrush(c)
    p.drawEllipse(QPointF(4, 18), 1.6, 1.6)


def _undo(p: QPainter, c: QColor) -> None:
    path = QPainterPath(QPointF(8, 6))
    path.lineTo(QPointF(4, 10))
    path.lineTo(QPointF(8, 14))
    p.drawPath(path)
    arc = QPainterPath(QPointF(4, 10))
    arc.lineTo(QPointF(14, 10))
    arc.cubicTo(QPointF(22, 10), QPointF(22, 20), QPointF(14, 20))
    arc.lineTo(QPointF(9, 20))
    p.drawPath(arc)


def _redo(p: QPainter, c: QColor) -> None:
    p.translate(S, 0)
    p.scale(-1, 1)
    _undo(p, c)


def _export(p: QPainter, c: QColor) -> None:
    path = QPainterPath(QPointF(8, 10))
    path.lineTo(QPointF(5, 10))
    path.lineTo(QPointF(5, 21))
    path.lineTo(QPointF(19, 21))
    path.lineTo(QPointF(19, 10))
    path.lineTo(QPointF(16, 10))
    p.drawPath(path)
    p.drawLine(QPointF(12, 3), QPointF(12, 15))
    p.drawLine(QPointF(12, 3), QPointF(8.5, 6.5))
    p.drawLine(QPointF(12, 3), QPointF(15.5, 6.5))


def _search(p: QPainter, c: QColor) -> None:
    p.drawEllipse(QPointF(10.5, 10.5), 6, 6)
    p.drawLine(QPointF(15, 15), QPointF(20.5, 20.5))


def _panel(p: QPainter, c: QColor) -> None:
    p.drawRoundedRect(QRectF(3, 5, 18, 14), 2.5, 2.5)
    p.drawLine(QPointF(14.5, 5), QPointF(14.5, 19))


def _fullscreen(p: QPainter, c: QColor) -> None:
    for (x, y, dx, dy) in ((4, 4, 1, 1), (20, 4, -1, 1), (4, 20, 1, -1), (20, 20, -1, -1)):
        path = QPainterPath(QPointF(x, y + 5 * dy))
        path.lineTo(QPointF(x, y))
        path.lineTo(QPointF(x + 5 * dx, y))
        p.drawPath(path)


def _zoom_in(p: QPainter, c: QColor) -> None:
    p.drawLine(QPointF(6, 12), QPointF(18, 12))
    p.drawLine(QPointF(12, 6), QPointF(12, 18))


def _zoom_out(p: QPainter, c: QColor) -> None:
    p.drawLine(QPointF(6, 12), QPointF(18, 12))


def _fit(p: QPainter, c: QColor) -> None:
    _fullscreen(p, c)
    p.drawRoundedRect(QRectF(8.5, 9.5, 7, 5), 1.2, 1.2)


def _marker(p: QPainter, c: QColor) -> None:
    p.drawLine(QPointF(6, 3), QPointF(6, 21))
    path = QPainterPath(QPointF(6, 4))
    path.lineTo(QPointF(19, 8.5))
    path.lineTo(QPointF(6, 13))
    p.drawPath(path)


def _note(p: QPainter, c: QColor) -> None:
    p.drawRoundedRect(QRectF(5, 3, 14, 18), 2, 2)
    for y in (8, 12, 16):
        p.drawLine(QPointF(8.5, y), QPointF(15.5, y))


def _chevron(p: QPainter, c: QColor) -> None:
    p.drawLine(QPointF(7, 10), QPointF(12, 15))
    p.drawLine(QPointF(12, 15), QPointF(17, 10))


def _chevron_right(p: QPainter, c: QColor) -> None:
    p.drawLine(QPointF(10, 7), QPointF(15, 12))
    p.drawLine(QPointF(15, 12), QPointF(10, 17))


def _align(p: QPainter, widths, anchor: str) -> None:
    for i, w in enumerate(widths):
        y = 6 + i * 4
        x0 = {"left": 4, "center": 12 - w / 2, "right": 20 - w}[anchor]
        p.drawLine(QPointF(x0, y), QPointF(x0 + w, y))


def _align_left(p: QPainter, c: QColor) -> None:
    _align(p, (16, 11, 16, 9), "left")


def _align_center(p: QPainter, c: QColor) -> None:
    _align(p, (16, 10, 16, 8), "center")


def _align_right(p: QPainter, c: QColor) -> None:
    _align(p, (16, 11, 16, 9), "right")


def _new(p: QPainter, c: QColor) -> None:
    path = QPainterPath(QPointF(14, 3))
    path.lineTo(QPointF(6, 3))
    path.lineTo(QPointF(6, 21))
    path.lineTo(QPointF(18, 21))
    path.lineTo(QPointF(18, 7))
    path.closeSubpath()
    p.drawPath(path)
    p.drawLine(QPointF(12, 10), QPointF(12, 17))
    p.drawLine(QPointF(8.5, 13.5), QPointF(15.5, 13.5))


def _open(p: QPainter, c: QColor) -> None:
    path = QPainterPath(QPointF(3, 19))
    path.lineTo(QPointF(3, 5))
    path.lineTo(QPointF(9, 5))
    path.lineTo(QPointF(11, 7.5))
    path.lineTo(QPointF(20, 7.5))
    path.lineTo(QPointF(20, 10))
    p.drawPath(path)
    path = QPainterPath(QPointF(3, 19))
    path.lineTo(QPointF(6.5, 10.5))
    path.lineTo(QPointF(22, 10.5))
    path.lineTo(QPointF(18.5, 19))
    path.closeSubpath()
    p.drawPath(path)


def _save(p: QPainter, c: QColor) -> None:
    p.drawRoundedRect(QRectF(4, 4, 16, 16), 2.5, 2.5)
    p.drawRect(QRectF(8, 4, 8, 5))
    p.drawRoundedRect(QRectF(7.5, 13, 9, 7), 1, 1)


_DRAW: dict[str, Callable[[QPainter, QColor], None]] = {
    "topic": _topic, "add_topic": _add_topic, "subtopic": _subtopic, "floating": _floating,
    "relation": _relation, "undo": _undo, "redo": _redo, "export": _export, "search": _search,
    "panel": _panel, "fullscreen": _fullscreen, "zoom_in": _zoom_in, "zoom_out": _zoom_out,
    "fit": _fit, "marker": _marker, "note": _note, "chevron": _chevron, "new": _new,
    "open": _open, "save": _save, "chevron_right": _chevron_right,
    "align_left": _align_left, "align_center": _align_center, "align_right": _align_right,
}


def icon(name: str, color: str, size: int = 24) -> QIcon:
    ic = QIcon()
    for scale in (1, 2, 3):
        pm = QPixmap(size * scale, size * scale)
        pm.setDevicePixelRatio(scale)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        p.scale(size / S, size / S)
        col = QColor(color)
        p.setPen(_pen(col))
        p.setBrush(Qt.BrushStyle.NoBrush)
        _DRAW[name](p, col)
        p.end()
        ic.addPixmap(pm)
    return ic


def shape_icon(shape: str, color: str, fill: str, w: int = 34, h: int = 22) -> QIcon:
    """Miniatura das formas de tópico para o seletor de forma."""
    from mindforge.view.painting import shape_path
    ic = QIcon()
    for scale in (1, 2):
        pm = QPixmap(w * scale, h * scale)
        pm.setDevicePixelRatio(scale)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        r = QRectF(3, 4, w - 6, h - 8)
        col = QColor(color)
        if shape == "padrao":
            p.setPen(_pen(col, 1.3))
            p.setFont(p.font())
            f = p.font()
            f.setPixelSize(10)
            f.setBold(True)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, h), int(Qt.AlignmentFlag.AlignCenter), tr("Auto"))
        elif shape in ("sublinhado", "sublinhado_duplo"):
            p.setPen(_pen(col, 1.6))
            p.drawLine(QPointF(r.left(), r.bottom()), QPointF(r.right(), r.bottom()))
            if shape == "sublinhado_duplo":
                p.drawLine(QPointF(r.left(), r.bottom() - 3.5), QPointF(r.right(), r.bottom() - 3.5))
        elif shape == "nenhuma":
            p.setPen(_pen(col, 1.2))
            f = p.font()
            f.setPixelSize(11)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, h), int(Qt.AlignmentFlag.AlignCenter), "Aa")
        else:
            path = shape_path(shape, r)
            if path is not None:
                p.setPen(_pen(col, 1.4))
                p.setBrush(QColor(fill))
                p.drawPath(path)
        p.end()
        ic.addPixmap(pm)
    return ic


def _pixmap_icon(w: int, h: int, draw) -> QIcon:
    ic = QIcon()
    for scale in (1, 2):
        pm = QPixmap(w * scale, h * scale)
        pm.setDevicePixelRatio(scale)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        draw(p)
        p.end()
        ic.addPixmap(pm)
    return ic


def branch_style_icon(style: str, color: str, w: int = 44, h: int = 28) -> QIcon:
    from mindforge.view.branches import draw_group
    kids = [("a", (w - 4.0, 4.0)), ("b", (w - 4.0, h / 2)), ("c", (w - 4.0, h - 4.0))]

    def draw(p: QPainter) -> None:
        d = draw_group(style, "right", (4.0, h / 2), kids, {k: color for k, _ in kids}, color, "nenhum", 1.6,
                       radius=5.0)
        p.setPen(_pen(QColor(color), 1.6))
        for st in d.strokes:
            p.drawPath(st.path)
    return _pixmap_icon(w, h, draw)


def line_end_icon(kind: str, color: str, w: int = 44, h: int = 20) -> QIcon:
    from mindforge.view.branches import end_mark

    def draw(p: QPainter) -> None:
        col = QColor(color)
        p.setPen(_pen(col, 1.6))
        tip = QPointF(w - 6, h / 2)
        p.drawLine(QPointF(6, h / 2), tip)
        m = end_mark(kind, tip, (1.0, 0.0), 1.6)
        if m is not None:
            path, filled = m
            if filled:
                p.setPen(Qt.PenStyle.NoPen)
                p.setBrush(col)
            p.drawPath(path)
    return _pixmap_icon(w, h, draw)


def pattern_icon(pattern: str, color: str, w: int = 56, h: int = 14) -> QIcon:
    from mindforge.view.painting import pattern_pen

    def draw(p: QPainter) -> None:
        if pattern == "nenhum":
            p.setPen(_pen(QColor(color), 1.0))
            f = p.font()
            f.setPixelSize(10)
            p.setFont(f)
            p.drawText(QRectF(0, 0, w, h), int(Qt.AlignmentFlag.AlignCenter), tr("Nenhum"))
            return
        p.setPen(pattern_pen(QColor(color), 1.8, pattern))
        p.drawLine(QPointF(3, h / 2), QPointF(w - 3, h / 2))
    return _pixmap_icon(w, h, draw)
