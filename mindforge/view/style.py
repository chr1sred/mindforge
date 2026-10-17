"""Aparência da interface (claro/escuro), inspirada no XMind.

Usa o estilo Fusion (idêntico em macOS, Windows e Linux) com paleta e
folha de estilo próprias. Acompanha o modo claro/escuro do sistema.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication


@dataclass(frozen=True)
class Chrome:
    dark: bool
    window: str
    panel: str
    surface: str
    surface_hover: str
    border: str
    text: str
    muted: str
    accent: str
    accent_soft: str
    card: str


DARK = Chrome(True, window="#1E1E21", panel="#252529", surface="#323238", surface_hover="#3C3C43",
              border="#3A3A41", text="#ECECEF", muted="#9A9AA3", accent="#0A84FF",
              accent_soft="#0A84FF33", card="#2C2C31")
LIGHT = Chrome(False, window="#F2F2F5", panel="#FAFAFB", surface="#FFFFFF", surface_hover="#EBEBEF",
               border="#DCDCE1", text="#1D1D1F", muted="#6E6E76", accent="#0A84FF",
               accent_soft="#0A84FF22", card="#FFFFFF")

_current = [LIGHT]


def chrome() -> Chrome:
    return _current[0]


def system_is_dark() -> bool:
    forced = os.environ.get("MINDFORGE_APARENCIA", "").lower()   # "claro" | "escuro"
    if forced in ("claro", "escuro"):
        return forced == "escuro"
    hints = QGuiApplication.styleHints()
    try:
        scheme = hints.colorScheme()
        if scheme == Qt.ColorScheme.Dark:
            return True
        if scheme == Qt.ColorScheme.Light:
            return False
    except AttributeError:
        pass
    return QGuiApplication.palette().color(QPalette.ColorRole.Window).lightness() < 128


def _palette(c: Chrome) -> QPalette:
    p = QPalette()
    R = QPalette.ColorRole
    p.setColor(R.Window, QColor(c.window))
    p.setColor(R.WindowText, QColor(c.text))
    p.setColor(R.Base, QColor(c.surface))
    p.setColor(R.AlternateBase, QColor(c.panel))
    p.setColor(R.Text, QColor(c.text))
    p.setColor(R.Button, QColor(c.surface))
    p.setColor(R.ButtonText, QColor(c.text))
    p.setColor(R.ToolTipBase, QColor(c.surface))
    p.setColor(R.ToolTipText, QColor(c.text))
    p.setColor(R.Highlight, QColor(c.accent))
    p.setColor(R.HighlightedText, QColor("#FFFFFF"))
    p.setColor(R.PlaceholderText, QColor(c.muted))
    p.setColor(R.Mid, QColor(c.muted))
    p.setColor(R.Link, QColor(c.accent))
    for role in (R.WindowText, R.Text, R.ButtonText):
        p.setColor(QPalette.ColorGroup.Disabled, role, QColor(c.muted))
    return p


def _ui_assets(c: Chrome) -> dict[str, str]:
    """Gera pequenos PNGs (seta, marca de seleção) usados pela folha de estilo."""
    import tempfile
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QImage, QPainter, QPen
    folder = os.path.join(tempfile.gettempdir(), f"mindforge-ui-{'escuro' if c.dark else 'claro'}")
    os.makedirs(folder, exist_ok=True)
    out = {}

    def make(name: str, w: int, h: int, draw) -> None:
        path = os.path.join(folder, f"{name}.png")
        img = QImage(w * 2, h * 2, QImage.Format.Format_ARGB32_Premultiplied)
        img.fill(Qt.GlobalColor.transparent)
        img.setDevicePixelRatio(2)
        p = QPainter(img)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        draw(p)
        p.end()
        img.save(path)
        out[name] = path.replace(os.sep, "/")

    def chevron(p, color):
        p.setPen(QPen(QColor(color), 1.6, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
        p.drawLine(QPointF(3, 4.5), QPointF(6, 7.5))
        p.drawLine(QPointF(6, 7.5), QPointF(9, 4.5))

    def check(p):
        p.setPen(QPen(QColor("#FFFFFF"), 2.0, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap,
                      Qt.PenJoinStyle.RoundJoin))
        p.drawLine(QPointF(4, 8.5), QPointF(7, 11.5))
        p.drawLine(QPointF(7, 11.5), QPointF(12.5, 5))

    make("chevron", 12, 12, lambda p: chevron(p, c.muted))
    make("chevron_text", 12, 12, lambda p: chevron(p, c.text))
    make("check", 16, 16, check)

    def dot(p):
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawEllipse(QPointF(8, 8), 3, 3)

    make("dot", 16, 16, dot)
    return out


def stylesheet(c: Chrome) -> str:
    a = _ui_assets(c)
    return f"""
    QMainWindow, QDialog {{ background: {c.window}; }}
    QWidget {{ font-size: 13px; }}
    QToolTip {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border};
                padding: 4px 6px; border-radius: 4px; }}

    /* ---------- barra superior ---------- */
    QToolBar#TopBar {{ background: {c.window}; border: none; border-bottom: 1px solid {c.border};
                      padding: 4px 8px; spacing: 2px; }}
    QToolBar#TopBar QToolButton {{ color: {c.text}; background: transparent; border: none;
                      border-radius: 6px; padding: 4px 8px; font-size: 11px; }}
    QToolBar#TopBar QToolButton:hover {{ background: {c.surface_hover}; }}
    QToolBar#TopBar QToolButton:pressed, QToolBar#TopBar QToolButton:checked {{ background: {c.accent_soft}; }}
    QToolBar#TopBar QToolButton::menu-indicator {{ image: none; width: 0; }}
    QToolBar#TopBar QToolButton[popupMode="1"] {{ padding-right: 16px; }}
    QToolBar#TopBar QToolButton::menu-button {{ border: none; width: 14px; background: transparent; }}
    QToolBar#TopBar QToolButton::menu-arrow {{ image: url({a["chevron_text"]}); width: 10px; height: 10px; }}
    QToolBar#TopBar::separator {{ background: {c.border}; width: 1px; margin: 8px 6px; }}

    /* ---------- painel lateral ---------- */
    QDockWidget {{ border: none; }}
    QWidget#SidePanel {{ background: {c.panel}; border-left: 1px solid {c.border}; }}
    QWidget#SidePanel QScrollArea, QWidget#SidePanel QScrollArea > QWidget > QWidget {{ background: transparent; border: none; }}
    QFrame#Segmented {{ background: {c.surface_hover}; border-radius: 8px; }}
    QPushButton#Segment {{ background: transparent; color: {c.muted}; border: none; border-radius: 6px;
                           padding: 5px 0; font-weight: 600; }}
    QPushButton#Segment:checked {{ background: {c.accent}; color: white; }}
    QPushButton#Segment:hover:!checked {{ color: {c.text}; }}
    QToolButton#SectionHeader {{ background: transparent; border: none; color: {c.text};
        font-size: 13px; font-weight: 700; padding: 4px 0; }}
    QToolButton#SectionHeader:hover {{ color: {c.accent}; }}
    QLabel#SectionTitle {{ color: {c.muted}; font-size: 12px; font-weight: 600; }}
    QLabel#Heading {{ color: {c.text}; font-size: 15px; font-weight: 700; }}
    QLabel#Muted {{ color: {c.muted}; }}
    QFrame#Separator {{ background: {c.border}; max-height: 1px; min-height: 1px; border: none; }}
    QLabel#RowLabel {{ color: {c.text}; }}

    QToolButton#ShapeButton, QToolButton#MarkerButton, QToolButton#StyleToggle {{
        background: {c.surface}; border: 1px solid {c.border}; border-radius: 6px; padding: 3px; }}
    QToolButton#ShapeButton:hover, QToolButton#MarkerButton:hover, QToolButton#StyleToggle:hover {{
        background: {c.surface_hover}; }}
    QToolButton#ShapeButton:checked, QToolButton#MarkerButton:checked, QToolButton#StyleToggle:checked {{
        border: 2px solid {c.accent}; background: {c.accent_soft}; }}
    QToolButton#Swatch {{ background: {c.surface}; border: 1px solid {c.border}; border-radius: 6px;
                          padding: 2px 6px; color: {c.text}; }}
    QToolButton#Swatch:hover {{ background: {c.surface_hover}; }}
    QToolButton#Swatch::menu-indicator {{ image: none; width: 0; }}
    QToolButton#Swatch:disabled {{ color: {c.muted}; background: {c.panel}; }}
    QToolButton#Card {{ background: {c.card}; border: 1px solid {c.border}; border-radius: 10px;
                        padding: 6px; color: {c.text}; font-size: 14px; text-align: left; }}
    QToolButton#Card:hover {{ border-color: {c.accent}; }}
    QToolButton#ThemeCard {{ background: transparent; border: 2px solid transparent; border-radius: 8px; padding: 2px; }}
    QToolButton#ThemeCard:hover {{ border-color: {c.border}; }}
    QToolButton#ThemeCard:checked {{ border-color: {c.accent}; }}
    QToolButton#PaletteItem {{ background: transparent; border: 2px solid transparent; border-radius: 9px;
                               padding: 4px 4px 6px 4px; color: {c.text}; font-size: 13px; }}
    QToolButton#PaletteItem:hover {{ background: {c.accent_soft}; }}
    QToolButton#PaletteItem:checked {{ border-color: {c.accent}; }}
    QToolButton#WheelButton {{ background: transparent; border: 2px solid transparent; border-radius: 26px;
                               padding: 2px; }}
    QToolButton#WheelButton:hover {{ border-color: {c.border}; }}
    QToolButton#WheelButton:checked {{ border-color: {c.accent}; }}
    QToolButton#ColorSlot {{ background: {c.card}; border: 1px dashed {c.border}; border-radius: 8px;
                             color: {c.muted}; font-size: 18px; }}
    QToolButton#ColorSlot:hover {{ border: 1px solid {c.accent}; }}
    QLabel#PreviewBox {{ background: {c.card}; border: 1px solid {c.border}; border-radius: 10px; color: {c.muted}; }}
    QLabel#Warning {{ color: #B4690E; }}
    QPushButton#LinkButton {{ background: transparent; border: none; color: {c.accent}; padding: 4px 0;
                              text-align: left; }}
    QPushButton#LinkButton:hover {{ text-decoration: underline; }}

    /* ---------- campos ---------- */
    QComboBox, QSpinBox, QLineEdit {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border};
        border-radius: 6px; padding: 4px 8px; min-height: 20px; selection-background-color: {c.accent}; }}
    QComboBox:hover, QSpinBox:hover, QLineEdit:hover {{ border-color: {c.muted}; }}
    QComboBox:focus, QSpinBox:focus, QLineEdit:focus {{ border-color: {c.accent}; }}
    QComboBox::drop-down {{ border: none; width: 22px; }}
    QComboBox::down-arrow {{ image: url({a["chevron"]}); width: 12px; height: 12px; }}
    QSpinBox::up-button, QSpinBox::down-button {{ width: 0; border: none; }}
    QComboBox QAbstractItemView {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border};
        selection-background-color: {c.accent}; outline: none; padding: 4px; }}
    QPlainTextEdit {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border};
        border-radius: 8px; padding: 6px; selection-background-color: {c.accent}; }}
    QPlainTextEdit:focus {{ border-color: {c.accent}; }}
    QPushButton {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border};
        border-radius: 6px; padding: 5px 14px; }}
    QPushButton:hover {{ background: {c.surface_hover}; }}
    QPushButton:default {{ background: {c.accent}; color: white; border-color: {c.accent}; }}
    QCheckBox {{ color: {c.text}; spacing: 8px; }}
    QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {c.muted};
                            background: {c.surface}; }}
    QCheckBox::indicator:checked {{ background: {c.accent}; border-color: {c.accent}; image: url({a["check"]}); }}
    QCheckBox::indicator:hover {{ border-color: {c.accent}; }}
    QRadioButton {{ color: {c.text}; spacing: 8px; }}
    QRadioButton::indicator {{ width: 16px; height: 16px; border-radius: 8px; border: 1px solid {c.muted};
                               background: {c.surface}; }}
    QRadioButton::indicator:checked {{ background: {c.accent}; border-color: {c.accent}; image: url({a["dot"]}); }}
    QRadioButton::indicator:hover {{ border-color: {c.accent}; }}
    QGroupBox {{ color: {c.muted}; border: 1px solid {c.border}; border-radius: 8px; margin-top: 14px;
                 padding: 10px 8px 8px 8px; font-weight: 600; }}
    QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; }}

    /* ---------- menus, status, rolagem ---------- */
    QMenuBar {{ background: {c.window}; color: {c.text}; }}
    QMenuBar::item:selected {{ background: {c.surface_hover}; border-radius: 4px; }}
    QMenu {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border}; border-radius: 8px;
             padding: 4px; }}
    QMenu::item {{ padding: 6px 22px 6px 12px; border-radius: 5px; }}
    QMenu::item:selected {{ background: {c.accent}; color: white; }}
    QMenu::item:disabled {{ color: {c.muted}; }}
    QMenu::separator {{ height: 1px; background: {c.border}; margin: 4px 8px; }}
    QStatusBar {{ background: {c.window}; color: {c.muted}; border-top: 1px solid {c.border}; }}
    QStatusBar::item {{ border: none; }}
    QStatusBar QToolButton {{ background: transparent; border: none; border-radius: 5px; color: {c.text};
                              padding: 2px 6px; }}
    QStatusBar QToolButton:hover {{ background: {c.surface_hover}; }}
    QStatusBar QToolButton::menu-indicator {{ image: url({a["chevron"]}); width: 10px; height: 10px;
                                              subcontrol-position: right center; }}
    QStatusBar QToolButton[popupMode="2"] {{ padding-right: 14px; }}
    QWidget#FindBar {{ background: {c.panel}; border-top: 1px solid {c.border}; }}
    QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
    QScrollBar::handle:vertical {{ background: {c.border}; border-radius: 3px; min-height: 30px; }}
    QScrollBar::handle:vertical:hover {{ background: {c.muted}; }}
    QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
    QScrollBar::handle:horizontal {{ background: {c.border}; border-radius: 3px; min-width: 30px; }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    QListWidget {{ background: {c.surface}; color: {c.text}; border: 1px solid {c.border}; border-radius: 8px; }}
    QListWidget::item {{ border: 2px solid transparent; border-radius: 10px; padding: 4px; color: {c.text}; }}
    QListWidget::item:hover {{ border-color: {c.border}; }}
    QListWidget::item:selected {{ background: transparent; border-color: {c.accent}; color: {c.text}; }}
    QTableWidget {{ background: {c.surface}; color: {c.text}; gridline-color: {c.border};
                    border: 1px solid {c.border}; border-radius: 6px; }}
    QHeaderView::section {{ background: {c.panel}; color: {c.muted}; border: none; padding: 6px; }}
    QFrame#Popup {{ background: {c.surface}; border: 1px solid {c.border}; border-radius: 12px; }}
    QFrame#Popup QLabel#SectionTitle {{ font-size: 13px; color: {c.text}; }}
    """


def apply(app: QApplication) -> Chrome:
    c = DARK if system_is_dark() else LIGHT
    _current[0] = c
    app.setStyle("Fusion")
    app.setPalette(_palette(c))
    app.setStyleSheet(stylesheet(c))
    return c
