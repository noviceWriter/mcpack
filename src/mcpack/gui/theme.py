"""Karanlık tema QSS (proje-amacı.md §2.6)."""

ACCENT = "#5b8def"
ACCENT_DIM = "#3d6bb3"
BG = "#191a1d"
PANEL_BG = "#232428"
FIELD_BG = "#2b2d31"
BORDER = "#34363b"
TEXT = "#e3e3e6"
TEXT_MUTED = "#8a8d93"

SOURCE_MODRINTH = "#1bd96a"
SOURCE_CURSEFORGE = "#f16436"

LOADER_VANILLA = "#6b7280"
LOADER_FABRIC = "#dbb86b"
LOADER_QUILT = "#a855f7"
LOADER_FORGE = "#4b6bdb"
LOADER_NEOFORGE = "#f97316"

DARK_STYLESHEET = f"""
QWidget {{
    background-color: {BG};
    color: {TEXT};
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background-color: {BG};
}}

QGroupBox {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
    border-radius: 6px;
    margin-top: 14px;
    padding: 10px 8px 8px 8px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: -2px;
    padding: 0 4px;
    color: {ACCENT};
}}

QListWidget, QTableWidget, QTreeWidget, QLineEdit, QTextEdit, QComboBox {{
    background-color: {FIELD_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 4px;
    selection-background-color: {ACCENT_DIM};
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
    border: 1px solid {ACCENT};
}}
QListWidget::item, QTableWidget::item {{
    padding: 3px;
    border: none;
}}
QListWidget::item:selected, QTableWidget::item:selected {{
    background-color: {ACCENT_DIM};
    color: #ffffff;
}}
QListWidget::item:hover, QTableWidget::item:hover {{
    background-color: #2f333a;
}}
QTableWidget {{
    gridline-color: {BORDER};
    alternate-background-color: #26282c;
}}
QTableWidget::item {{
    border-bottom: 1px solid {BORDER};
}}

QPushButton {{
    background-color: {FIELD_BG};
    border: 1px solid {BORDER};
    border-radius: 5px;
    padding: 7px 14px;
}}
QPushButton:hover {{
    background-color: #33363c;
    border: 1px solid #4a4d54;
}}
QPushButton:pressed {{
    background-color: {ACCENT_DIM};
}}
QPushButton:disabled {{
    color: {TEXT_MUTED};
    background-color: {FIELD_BG};
}}

QPushButton#primary {{
    background-color: {ACCENT_DIM};
    border: 1px solid {ACCENT};
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background-color: {ACCENT};
}}
QPushButton#danger {{
    color: #ff9a9a;
}}

QHeaderView::section {{
    background-color: {PANEL_BG};
    color: {TEXT_MUTED};
    border: none;
    border-bottom: 1px solid {BORDER};
    border-right: 1px solid {BORDER};
    padding: 5px;
    font-weight: 600;
}}
QTableCornerButton::section {{
    background-color: {PANEL_BG};
    border: none;
}}

QSplitter::handle {{
    background-color: {BG};
    width: 4px;
}}

QProgressBar {{
    border: 1px solid {BORDER};
    border-radius: 5px;
    text-align: center;
    background-color: {FIELD_BG};
}}
QProgressBar::chunk {{
    background-color: {ACCENT};
    border-radius: 4px;
}}

QLabel[role="heading"] {{
    font-weight: 700;
    font-size: 14px;
    padding: 2px 0;
    color: {TEXT};
}}
QLabel[role="muted"] {{
    color: {TEXT_MUTED};
    font-size: 12px;
}}
QLabel[role="badge-modrinth"] {{
    color: {SOURCE_MODRINTH};
    font-weight: 600;
}}
QLabel[role="badge-curseforge"] {{
    color: {SOURCE_CURSEFORGE};
    font-weight: 600;
}}

QMenuBar {{
    background-color: {PANEL_BG};
    border-bottom: 1px solid {BORDER};
}}
QMenuBar::item:selected {{
    background-color: {FIELD_BG};
}}
QMenu {{
    background-color: {PANEL_BG};
    border: 1px solid {BORDER};
}}
QMenu::item:selected {{
    background-color: {ACCENT_DIM};
}}

QScrollBar:vertical {{
    background-color: {BG};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: #3a3d41;
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: #4a4d54;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


def source_color(value: str) -> str:
    return {"modrinth": SOURCE_MODRINTH, "curseforge": SOURCE_CURSEFORGE}.get(value, TEXT_MUTED)


def loader_color(value: str) -> str:
    return {
        "vanilla": LOADER_VANILLA,
        "fabric": LOADER_FABRIC,
        "quilt": LOADER_QUILT,
        "forge": LOADER_FORGE,
        "neoforge": LOADER_NEOFORGE,
    }.get(value, LOADER_VANILLA)
