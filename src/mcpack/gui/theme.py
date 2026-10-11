"""Tasarım belirteçleri (renk, boşluk, yarıçap) + uygulama geneli QSS.

Tüm renkler burada TEK YERDE tanımlanır; widget'lar renkleri asla elle
yazmaz, `COLORS[...]` ya da QSS'teki dinamik özellikleri (`role`, `tone`,
`variant`) kullanır. Kategorik renkler (kaynak/loader) CVD-güvenli bir
paletten seçildi; durum renkleri (success/warning/danger) metinde değil
nokta/çip/şerit gibi işaretlerde kullanılır.
"""

from __future__ import annotations

from PySide6.QtGui import QColor, QFont, QPalette
from PySide6.QtWidgets import QApplication

COLORS: dict[str, str] = {
    "bg": "#0f1115",
    "surface": "#151820",
    "surface_2": "#1b1f29",
    "elevated": "#222735",
    "hover": "#262c3b",
    "border": "#262b37",
    "border_strong": "#353c4d",
    "text": "#e7e9ef",
    "text_muted": "#9aa3b4",
    "text_dim": "#6c7486",
    "accent": "#6d8cff",
    "accent_hover": "#859fff",
    "accent_press": "#5874e0",
    "accent_soft": "#1d2647",
    "on_accent": "#ffffff",
    "success": "#3ccf91",
    "success_soft": "#13301f",
    "warning": "#f5b544",
    "warning_soft": "#33280f",
    "danger": "#f2555a",
    "danger_soft": "#3a1719",
    "info": "#4fb6f0",
    "info_soft": "#112b3b",
    "console_bg": "#0a0c10",
    "selection": "#2a3560",
}

CATEGORY_COLORS: dict[str, str] = {
    "modrinth": "#1bd96a",
    "curseforge": "#f16436",
    "wurst": "#d55181",
    "meteor": "#9085e9",
    "vanilla": "#7d8798",
    "fabric": "#dbb36b",
    "quilt": "#c873d6",
    "forge": "#6b8cff",
    "neoforge": "#f08a4b",
}

LEVEL_COLORS: dict[str, str] = {
    "DEBUG": COLORS["text_dim"],
    "INFO": COLORS["text_muted"],
    "WARNING": COLORS["warning"],
    "ERROR": COLORS["danger"],
    "CRITICAL": "#ff3b6b",
}

TONES = {
    "neutral": (COLORS["elevated"], COLORS["text_muted"]),
    "accent": (COLORS["accent_soft"], COLORS["accent_hover"]),
    "success": (COLORS["success_soft"], COLORS["success"]),
    "warning": (COLORS["warning_soft"], COLORS["warning"]),
    "danger": (COLORS["danger_soft"], COLORS["danger"]),
    "info": (COLORS["info_soft"], COLORS["info"]),
}

RADIUS = 10
MONO_FAMILIES = ["JetBrains Mono", "Cascadia Code", "Fira Code", "DejaVu Sans Mono", "Consolas", "monospace"]


def category_color(key: str) -> str:
    return CATEGORY_COLORS.get(key, COLORS["text_dim"])


def readable_on(color_hex: str) -> str:
    return "#10131a" if QColor(color_hex).lightness() > 150 else "#ffffff"


def mono_font(point_size: int = 10) -> QFont:
    font = QFont()
    font.setFamilies(MONO_FAMILIES)
    font.setStyleHint(QFont.StyleHint.Monospace)
    font.setPointSize(point_size)
    return font


def _asset(name: str) -> str:
    """QSS url() için mutlak, ileri eğik çizgili yol (PyInstaller'da _MEIPASS/assets)."""
    import sys
    from pathlib import Path

    base = getattr(sys, "_MEIPASS", None)
    root = Path(base) / "assets" if base else Path(__file__).resolve().parent.parent / "assets"
    return (root / name).as_posix()


def _qss() -> str:
    c = COLORS
    return f"""
* {{ outline: none; }}
QWidget {{
    background-color: transparent;
    color: {c['text']};
    font-size: 13px;
    selection-background-color: {c['selection']};
    selection-color: {c['text']};
}}
QMainWindow, QDialog, #AppRoot {{ background-color: {c['bg']}; }}
QToolTip {{
    background-color: {c['elevated']}; color: {c['text']};
    border: 1px solid {c['border_strong']}; border-radius: 6px; padding: 6px 8px;
}}

/* ---- kenar çubuğu ---- */
#Sidebar {{ background-color: {c['surface']}; border-right: 1px solid {c['border']}; }}
#SidebarBrand {{ font-size: 15px; font-weight: 700; padding: 4px 6px; }}
#SidebarCaption {{ color: {c['text_dim']}; font-size: 11px; font-weight: 600; padding: 10px 10px 4px 10px; }}
QPushButton[variant="nav"] {{
    text-align: left; padding: 9px 12px; border: none; border-radius: 8px;
    background: transparent; color: {c['text_muted']}; font-weight: 500;
}}
QPushButton[variant="nav"]:hover {{ background-color: {c['hover']}; color: {c['text']}; }}
QPushButton[variant="nav"]:checked {{
    background-color: {c['accent_soft']}; color: {c['text']}; font-weight: 600;
}}

/* ---- butonlar ---- */
QPushButton, QToolButton {{
    background-color: {c['surface_2']}; color: {c['text']};
    border: 1px solid {c['border_strong']}; border-radius: 8px; padding: 7px 14px;
}}
QPushButton:hover, QToolButton:hover {{ background-color: {c['hover']}; border-color: #46506a; }}
QPushButton:pressed, QToolButton:pressed {{ background-color: {c['elevated']}; }}
QPushButton:disabled, QToolButton:disabled {{ color: {c['text_dim']}; background-color: {c['surface']}; border-color: {c['border']}; }}
QPushButton[variant="primary"] {{ background-color: {c['accent']}; color: {c['on_accent']}; border: 1px solid {c['accent']}; font-weight: 600; }}
QPushButton[variant="primary"]:hover {{ background-color: {c['accent_hover']}; border-color: {c['accent_hover']}; }}
QPushButton[variant="primary"]:pressed {{ background-color: {c['accent_press']}; }}
QPushButton[variant="primary"]:disabled {{ background-color: {c['accent_soft']}; color: {c['text_dim']}; border-color: {c['accent_soft']}; }}
QPushButton[variant="danger"] {{ background-color: {c['danger_soft']}; color: {c['danger']}; border: 1px solid #5a2427; }}
QPushButton[variant="danger"]:hover {{ background-color: #4a1d20; }}
QPushButton[variant="ghost"], QToolButton[variant="ghost"] {{ background: transparent; border: 1px solid transparent; color: {c['text_muted']}; }}
QPushButton[variant="ghost"]:hover, QToolButton[variant="ghost"]:hover {{ background-color: {c['hover']}; color: {c['text']}; }}
QPushButton[variant="chip"] {{ padding: 4px 10px; border-radius: 13px; font-size: 12px; background: {c['surface_2']}; color: {c['text_muted']}; }}
QPushButton[variant="chip"]:checked {{ background: {c['accent_soft']}; color: {c['text']}; border-color: {c['accent']}; }}
QToolButton::menu-indicator {{ image: none; width: 0; }}

/* ---- giriş alanları ---- */
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox, QPlainTextEdit, QTextEdit {{
    background-color: {c['surface']}; border: 1px solid {c['border_strong']};
    border-radius: 8px; padding: 6px 10px; color: {c['text']};
}}
QLineEdit:focus, QComboBox:focus, QSpinBox:focus, QPlainTextEdit:focus {{ border-color: {c['accent']}; }}
QLineEdit:disabled, QComboBox:disabled, QSpinBox:disabled {{ color: {c['text_dim']}; background-color: {c['bg']}; }}
QLineEdit[variant="search"] {{ padding-left: 30px; border-radius: 17px; }}
QComboBox::drop-down {{ border: none; width: 22px; }}
QComboBox::down-arrow {{ image: url("{_asset('chevron-down.svg')}"); width: 12px; height: 12px; margin-right: 8px; }}
QSpinBox::up-arrow, QSpinBox::down-arrow {{ width: 0; height: 0; }}
QComboBox QAbstractItemView {{
    background-color: {c['elevated']}; border: 1px solid {c['border_strong']}; border-radius: 8px;
    selection-background-color: {c['selection']}; padding: 4px;
}}
QSpinBox::up-button, QSpinBox::down-button {{ width: 16px; border: none; background: transparent; }}
QCheckBox {{ spacing: 8px; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {c['border_strong']}; background: {c['surface']}; }}
QCheckBox::indicator:checked {{ background: {c['accent']}; border-color: {c['accent']}; }}
QCheckBox::indicator:hover {{ border-color: {c['accent']}; }}

/* ---- kartlar / paneller ---- */
QFrame[card="true"] {{ background-color: {c['surface']}; border: 1px solid {c['border']}; border-radius: {RADIUS}px; }}
QFrame[card="hover"] {{ background-color: {c['surface']}; border: 1px solid {c['border']}; border-radius: {RADIUS}px; }}
QFrame[card="hover"]:hover {{ background-color: {c['surface_2']}; border-color: {c['border_strong']}; }}
QFrame[card="selected"] {{ background-color: {c['surface_2']}; border: 1px solid {c['accent']}; border-radius: {RADIUS}px; }}
QFrame[separator="true"] {{ background-color: {c['border']}; max-height: 1px; min-height: 1px; border: none; }}
QLabel[role="title"] {{ font-size: 22px; font-weight: 700; }}
QLabel[role="h2"] {{ font-size: 16px; font-weight: 700; }}
QLabel[role="h3"] {{ font-size: 13px; font-weight: 700; }}
QLabel[role="muted"] {{ color: {c['text_muted']}; }}
QLabel[role="dim"] {{ color: {c['text_dim']}; font-size: 12px; }}
QLabel[role="stat"] {{ font-size: 24px; font-weight: 700; }}
QLabel[role="kbd"] {{ background: {c['elevated']}; border: 1px solid {c['border_strong']}; border-radius: 4px; padding: 1px 6px; color: {c['text_muted']}; font-size: 11px; }}
QLabel[role="notice"] {{ background: {c['warning_soft']}; color: {c['warning']}; border: 1px solid #5a4516; border-radius: 8px; padding: 10px 12px; }}
QLabel[role="notice-danger"] {{ background: {c['danger_soft']}; color: {c['danger']}; border: 1px solid #5a2427; border-radius: 8px; padding: 10px 12px; }}
QLabel[role="notice-info"] {{ background: {c['info_soft']}; color: {c['info']}; border: 1px solid #1d4a63; border-radius: 8px; padding: 10px 12px; }}

/* ---- tablolar / listeler ---- */
QTableView, QTreeView, QListView, QListWidget, QTableWidget, QTreeWidget {{
    background-color: {c['surface']}; alternate-background-color: {c['surface_2']};
    border: 1px solid {c['border']}; border-radius: {RADIUS}px; gridline-color: transparent;
}}
QTableView::item, QTreeView::item, QListView::item, QListWidget::item, QTableWidget::item {{ padding: 6px 8px; border: none; }}
QTableView::item:selected, QTreeView::item:selected, QListView::item:selected, QListWidget::item:selected, QTableWidget::item:selected {{
    background-color: {c['selection']}; color: {c['text']};
}}
QTableView::item:hover, QTreeView::item:hover, QListView::item:hover, QListWidget::item:hover {{ background-color: {c['hover']}; }}
QHeaderView {{ background: transparent; }}
QHeaderView::section {{
    background-color: {c['surface']}; color: {c['text_muted']}; font-weight: 600; font-size: 12px;
    border: none; border-bottom: 1px solid {c['border']}; padding: 8px;
}}
QTableCornerButton::section {{ background: {c['surface']}; border: none; }}

/* ---- sekmeler ---- */
QTabWidget::pane {{ border: none; top: -1px; }}
QTabBar {{ background: transparent; }}
QTabBar::tab {{
    background: transparent; color: {c['text_muted']}; padding: 8px 14px; margin-right: 2px;
    border: none; border-bottom: 2px solid transparent; font-weight: 500;
}}
QTabBar::tab:hover {{ color: {c['text']}; }}
QTabBar::tab:selected {{ color: {c['text']}; border-bottom: 2px solid {c['accent']}; font-weight: 600; }}

/* ---- kaydırma çubukları ---- */
QScrollArea {{ border: none; background: transparent; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 2px; }}
QScrollBar::handle:vertical {{ background: {c['border_strong']}; border-radius: 4px; min-height: 28px; }}
QScrollBar::handle:vertical:hover {{ background: #4a5268; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 2px; }}
QScrollBar::handle:horizontal {{ background: {c['border_strong']}; border-radius: 4px; min-width: 28px; }}
QScrollBar::add-line, QScrollBar::sub-line, QScrollBar::add-page, QScrollBar::sub-page {{ width: 0; height: 0; background: none; }}

/* ---- menü / ilerleme / durum çubuğu ---- */
QMenu {{ background-color: {c['elevated']}; border: 1px solid {c['border_strong']}; border-radius: 8px; padding: 5px; }}
QMenu::item {{ padding: 7px 18px 7px 12px; border-radius: 5px; }}
QMenu::item:selected {{ background-color: {c['selection']}; }}
QMenu::item:disabled {{ color: {c['text_dim']}; }}
QMenu::separator {{ height: 1px; background: {c['border']}; margin: 4px 6px; }}
QProgressBar {{ background-color: {c['surface_2']}; border: none; border-radius: 4px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background-color: {c['accent']}; border-radius: 4px; }}
QStatusBar {{ background-color: {c['surface']}; border-top: 1px solid {c['border']}; color: {c['text_muted']}; }}
QStatusBar::item {{ border: none; }}
QStatusBar QPushButton {{ padding: 2px 10px; border-radius: 6px; font-size: 12px; background: transparent; border: 1px solid transparent; color: {c['text_muted']}; }}
QStatusBar QPushButton:hover {{ background: {c['hover']}; color: {c['text']}; }}
QSplitter::handle {{ background: {c['border']}; }}
QSplitter::handle:horizontal {{ width: 1px; }}
QSplitter::handle:vertical {{ height: 1px; }}

/* ---- konsol ---- */
QPlainTextEdit[variant="console"], QTextEdit[variant="console"] {{
    background-color: {c['console_bg']}; border: 1px solid {c['border']}; border-radius: {RADIUS}px;
    padding: 8px; color: #cfd6e4;
}}

/* ---- toast ---- */
QFrame[toast="true"] {{ background-color: {c['elevated']}; border: 1px solid {c['border_strong']}; border-radius: 10px; }}

/* ---- komut paleti ---- */
#Palette {{ background-color: {c['surface']}; border: 1px solid {c['border_strong']}; border-radius: 14px; }}
#Palette QLineEdit {{ font-size: 15px; padding: 12px 14px; border: none; border-bottom: 1px solid {c['border']}; border-radius: 0; background: transparent; }}
#Palette QListWidget {{ border: none; background: transparent; }}
"""


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    palette = QPalette()
    c = COLORS
    palette.setColor(QPalette.ColorRole.Window, QColor(c["bg"]))
    palette.setColor(QPalette.ColorRole.WindowText, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.Base, QColor(c["surface"]))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor(c["surface_2"]))
    palette.setColor(QPalette.ColorRole.Text, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.Button, QColor(c["surface_2"]))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.Highlight, QColor(c["selection"]))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor(c["elevated"]))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor(c["text"]))
    palette.setColor(QPalette.ColorRole.PlaceholderText, QColor(c["text_dim"]))
    palette.setColor(QPalette.ColorRole.Link, QColor(c["accent_hover"]))
    for role in (QPalette.ColorRole.Text, QPalette.ColorRole.WindowText, QPalette.ColorRole.ButtonText):
        palette.setColor(QPalette.ColorGroup.Disabled, role, QColor(c["text_dim"]))
    app.setPalette(palette)
    app.setStyleSheet(_qss())
