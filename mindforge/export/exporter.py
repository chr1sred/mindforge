"""Exportação para PNG (com transparência), SVG e PDF vetoriais.

A cena é renderizada em "modo exportação": sem destaque de seleção, sem
cursor de edição e, opcionalmente, apenas o ramo selecionado. A área
exportada é calculada a partir do que realmente foi desenhado (caixas,
linhas, relações e indicadores) + margem.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from PySide6.QtCore import QMarginsF, QRectF, QSize, QSizeF, Qt
from PySide6.QtGui import QColor, QImage, QPageLayout, QPageSize, QPainter, QPdfWriter
from PySide6.QtSvg import QSvgGenerator

from mindforge import APP_NAME, __version__
from mindforge.view.scene import MindScene

MAX_PNG_SIDE = 32000           # limite de dimensão do QImage
MAX_PNG_PIXELS = 160_000_000   # ~640 MB em ARGB32: acima disso a escala é reduzida
PDF_MAX_PT = 14400.0           # limite de página do PDF (200 polegadas)
PX_TO_PT = 0.75                # 96 px = 72 pt


class ExportError(Exception):
    pass


@dataclass
class ExportOptions:
    fmt: str = "png"                  # png | svg | pdf
    scale: float = 2.0                # PNG
    transparent: bool = True          # PNG / SVG
    margin: float = 32.0
    only_ids: Optional[set] = None    # exporta apenas este ramo
    text_as_paths: bool = False       # SVG: textos em curvas
    pdf_page: str = "mapa"            # mapa | a4_paisagem | a4_retrato | a3_paisagem
    pdf_background: bool = True
    title: str = ""


@dataclass
class ExportResult:
    path: str
    width: int = 0
    height: int = 0
    notes: list[str] = field(default_factory=list)


def _render_hints(p: QPainter) -> None:
    p.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    p.setRenderHint(QPainter.RenderHint.TextAntialiasing, True)
    p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)


def _source_rect(content: QRectF, margin: float) -> QRectF:
    if content.isNull() or content.width() <= 0:
        raise ExportError("Não há nada para exportar.")
    return content.adjusted(-margin, -margin, margin, margin)


def export_png(scene: MindScene, path: str, opt: ExportOptions) -> ExportResult:
    res = ExportResult(path)
    with scene.exporting(opt.only_ids, False, opt.transparent) as content:
        src = _source_rect(content, opt.margin)
        scale = max(0.25, float(opt.scale))
        max_scale = min(MAX_PNG_SIDE / src.width(), MAX_PNG_SIDE / src.height(),
                        (MAX_PNG_PIXELS / (src.width() * src.height())) ** 0.5)
        if scale > max_scale:
            scale = max_scale
            res.notes.append(f"O mapa é muito grande: a escala foi reduzida para {scale:.2f}x.")
        w, h = max(1, round(src.width() * scale)), max(1, round(src.height() * scale))
        img = QImage(w, h, QImage.Format.Format_ARGB32_Premultiplied)
        if img.isNull():
            raise ExportError("Memória insuficiente para gerar a imagem. Tente uma escala menor.")
        img.fill(Qt.GlobalColor.transparent if opt.transparent else QColor(scene.background_color))
        dpm = round(2835 * scale)       # 72 dpi × escala (metadado de resolução)
        img.setDotsPerMeterX(dpm)
        img.setDotsPerMeterY(dpm)
        p = QPainter(img)
        _render_hints(p)
        scene.render(p, QRectF(0, 0, w, h), src, Qt.AspectRatioMode.IgnoreAspectRatio)
        p.end()
    if not img.save(path, "PNG"):
        raise ExportError("Não foi possível gravar o arquivo PNG.")
    res.width, res.height = w, h
    return res


def export_svg(scene: MindScene, path: str, opt: ExportOptions) -> ExportResult:
    res = ExportResult(path)
    with scene.exporting(opt.only_ids, opt.text_as_paths, opt.transparent) as content:
        src = _source_rect(content, opt.margin)
        w, h = round(src.width()), round(src.height())
        gen = QSvgGenerator()
        gen.setFileName(path)
        gen.setSize(QSize(w, h))
        gen.setViewBox(QRectF(0, 0, w, h))
        gen.setResolution(96)
        gen.setTitle(opt.title or APP_NAME)
        gen.setDescription(f"Gerado por {APP_NAME} {__version__}")
        p = QPainter()
        if not p.begin(gen):
            raise ExportError("Não foi possível gravar o arquivo SVG.")
        _render_hints(p)
        if not opt.transparent:
            p.fillRect(QRectF(0, 0, w, h), QColor(scene.background_color))
        scene.render(p, QRectF(0, 0, w, h), src, Qt.AspectRatioMode.IgnoreAspectRatio)
        p.end()
    res.width, res.height = w, h
    return res


_PAGES = {
    "a4_paisagem": (QPageSize.PageSizeId.A4, QPageLayout.Orientation.Landscape),
    "a4_retrato": (QPageSize.PageSizeId.A4, QPageLayout.Orientation.Portrait),
    "a3_paisagem": (QPageSize.PageSizeId.A3, QPageLayout.Orientation.Landscape),
}


def export_pdf(scene: MindScene, path: str, opt: ExportOptions) -> ExportResult:
    res = ExportResult(path)
    with scene.exporting(opt.only_ids, False, False) as content:
        src = _source_rect(content, opt.margin)
        writer = QPdfWriter(path)
        writer.setCreator(f"{APP_NAME} {__version__}")
        writer.setTitle(opt.title or APP_NAME)
        writer.setResolution(300)
        if opt.pdf_page in _PAGES:
            size_id, orient = _PAGES[opt.pdf_page]
            layout = QPageLayout(QPageSize(size_id), orient, QMarginsF(28, 28, 28, 28),
                                 QPageLayout.Unit.Point)
        else:
            wpt, hpt = src.width() * PX_TO_PT, src.height() * PX_TO_PT
            factor = min(1.0, PDF_MAX_PT / max(wpt, hpt))
            if factor < 1.0:
                res.notes.append("O mapa excede o tamanho máximo de página do PDF; foi reduzido proporcionalmente.")
            size = QPageSize(QSizeF(wpt * factor, hpt * factor), QPageSize.Unit.Point, "Mapa",
                             QPageSize.SizeMatchPolicy.ExactMatch)
            orient = QPageLayout.Orientation.Portrait
            layout = QPageLayout(size, orient, QMarginsF(0, 0, 0, 0), QPageLayout.Unit.Point)
        writer.setPageLayout(layout)
        p = QPainter()
        if not p.begin(writer):
            raise ExportError("Não foi possível gravar o arquivo PDF (o arquivo está aberto em outro programa?).")
        _render_hints(p)
        page = QRectF(writer.pageLayout().paintRectPixels(writer.resolution()))
        page.moveTo(0, 0)
        if opt.pdf_background:
            p.fillRect(page, QColor(scene.background_color))
        # mantém a proporção e centraliza na página
        k = min(page.width() / src.width(), page.height() / src.height())
        tw, th = src.width() * k, src.height() * k
        target = QRectF(page.x() + (page.width() - tw) / 2, page.y() + (page.height() - th) / 2, tw, th)
        scene.render(p, target, src, Qt.AspectRatioMode.IgnoreAspectRatio)
        p.end()
        res.width, res.height = round(src.width()), round(src.height())
    return res


def export_file(scene: MindScene, path: str, opt: ExportOptions) -> ExportResult:
    fn = {"png": export_png, "svg": export_svg, "pdf": export_pdf}.get(opt.fmt)
    if fn is None:
        raise ExportError(f"Formato desconhecido: {opt.fmt}")
    return fn(scene, path, opt)
