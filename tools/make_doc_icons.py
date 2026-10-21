"""Gera o ícone dos documentos .mfmap em todos os formatos (rode: python tools/make_doc_icons.py).

Saída em assets/doc/: mfmap.icns (macOS), mfmap.ico (Windows) e mfmap-<N>.png (Linux e geral).
O desenho é feito por código (uma fonte só); tamanhos pequenos usam uma versão simplificada.
Requer PySide6 e Pillow (requirements-dev.txt).
"""
import io
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtGui import QColor, QFont, QImage, QLinearGradient, QPainter, QPainterPath, QPen  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
OUT = os.path.join(ROOT, "assets", "doc")
SIZES = (16, 32, 48, 64, 128, 256, 512, 1024)
NAVY = "#2E2A6B"
BRANCHES = ("#F24F4B", "#F59E57", "#F2C94C", "#27BE7E")


def draw(size: int) -> QImage:
    small = size <= 32
    label = size >= 128          # a etiqueta só é legível a partir de 128 px
    img = QImage(size, size, QImage.Format.Format_ARGB32)
    img.fill(0)
    p = QPainter(img)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.scale(size / 1024, size / 1024)
    # folha com canto dobrado
    L, T, R, B = (150, 40, 874, 984) if small else (170, 60, 854, 964)
    fold = 200 if small else 170
    rad = 60 if small else 40
    page = QPainterPath()
    page.moveTo(L + rad, T)
    page.lineTo(R - fold, T)
    page.lineTo(R, T + fold)
    page.lineTo(R, B - rad)
    page.quadTo(R, B, R - rad, B)
    page.lineTo(L + rad, B)
    page.quadTo(L, B, L, B - rad)
    page.lineTo(L, T + rad)
    page.quadTo(L, T, L + rad, T)
    if not small:                               # sombra suave
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(0, 0, 0, 38))
        p.translate(0, 12)
        p.drawPath(page)
        p.translate(0, -12)
    g = QLinearGradient(0, T, 0, B)
    g.setColorAt(0, QColor("#FFFFFF"))
    g.setColorAt(1, QColor("#EEF1F6"))
    p.setBrush(g)
    p.setPen(QPen(QColor("#B9C0CC" if small else "#D3D8E0"), 40 if small else 6))
    p.drawPath(page)
    corner = QPainterPath()
    corner.moveTo(R - fold, T)
    corner.lineTo(R - fold, T + fold - 30)
    corner.quadTo(R - fold, T + fold, R - fold + 30, T + fold)
    corner.lineTo(R, T + fold)
    corner.closeSubpath()
    p.setPen(Qt.PenStyle.NoPen)
    p.setBrush(QColor("#DCE1E9"))
    p.drawPath(corner)
    # mini mapa mental
    cx, cy = 512, (470 if label else 540)
    if small:       # versão simplificada: central + 2 ramos grossos
        ends = [(780, 400), (780, 720)]
        cols = BRANCHES[:1] + BRANCHES[3:]
        lw, bw, bh, cw, ch = 70, 170, 110, 330, 190
    else:
        ends = [(684, cy - 135), (684, cy + 135), (340, cy - 135), (340, cy + 135)]
        cols = BRANCHES
        lw, bw, bh, cw, ch = (22, 118, 64, 250, 112) if label else (34, 124, 84, 270, 140)
    for (ex, ey), c in zip(ends, cols):
        right = ex > cx
        p.setPen(QPen(QColor(c), lw, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.setBrush(Qt.BrushStyle.NoBrush)
        path = QPainterPath(QPointF(cx + (1 if right else -1) * cw * 0.4, cy))
        mid = (cx + ex) / 2
        path.cubicTo(QPointF(mid, cy), QPointF(mid, ey), QPointF(ex, ey))
        p.drawPath(path)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(c))
        x = ex if right else ex - bw
        if small:
            x = min(x, R - 60 - bw)
        p.drawRoundedRect(QRectF(x, ey - bh / 2, bw, bh), bh * 0.32, bh * 0.32)
    p.setBrush(QColor(NAVY))
    left_c = cx - cw / 2 if not small else 230
    p.drawRoundedRect(QRectF(left_c, cy - ch / 2, cw, ch), ch * 0.3, ch * 0.3)
    if label:       # etiqueta
        p.drawRoundedRect(QRectF(310, 780, 404, 104), 30, 30)
        f = QFont("Inter")
        f.setPixelSize(68)
        f.setBold(True)
        p.setFont(f)
        p.setPen(QColor("#FFFFFF"))
        p.drawText(QRectF(310, 780, 404, 104), Qt.AlignmentFlag.AlignCenter, "MFMAP")
    p.end()
    return img


def to_pil(img: QImage) -> Image.Image:
    buf = QBuffer()
    buf.open(QBuffer.OpenModeFlag.ReadWrite)
    img.save(buf, "PNG")
    return Image.open(io.BytesIO(bytes(buf.data()))).convert("RGBA")


def main() -> None:
    app = QApplication.instance() or QApplication(sys.argv)
    sys.path.insert(0, ROOT)
    from mindforge.view.painting import ensure_fonts        # Inter embutida (etiqueta)
    ensure_fonts()
    os.makedirs(OUT, exist_ok=True)
    imgs = {s: to_pil(draw(s)) for s in SIZES}
    for s, im in imgs.items():
        if s <= 512:
            im.save(os.path.join(OUT, f"mfmap-{s}.png"))
    big = imgs[1024]
    big.save(os.path.join(OUT, "mfmap.icns"), append_images=[imgs[s] for s in (16, 32, 64, 128, 256, 512)])
    imgs[256].save(os.path.join(OUT, "mfmap.ico"), sizes=[(s, s) for s in (16, 32, 48, 64, 128, 256)],
                   append_images=[imgs[s] for s in (16, 32, 48, 64, 128)])
    del app
    print("ícones gerados em", OUT)


if __name__ == "__main__":
    main()
