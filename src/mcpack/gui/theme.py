"""Açık/koyu tema QSS (proje-amacı.md §2.6 — "karanlık tema destekli olsun",
kullanıcı isteğiyle açık tema da eklendi)."""

from __future__ import annotations

# Kategorik rozet renkleri (kaynak: Modrinth/CurseForge, loader: Fabric/Quilt/
# Forge/NeoForge) — dataviz skill'inin doğrulanmış, CVD-güvenli 8 renkli
# kategorik paletinden (references/palette.md) alındı: sabit sıra, mavi
# (accent) ve kırmızı (danger/critical durum rengi) ile çakışmasın diye
# atlandı. Modrinth/CurseForge kendi gerçek marka renklerine en yakın
# slot'larla eşleşti (yeşil/turuncu). Kaynak ve loader rozetleri arayüzde
# hiçbir zaman aynı anda/yan yana görünmediği için palet sırasını ikisi de
# baştan kullanabildi; NeoForge'un CurseForge ile aynı turuncuyu paylaşması
# bu yüzden çakışma yaratmıyor (ikisi de gerçek markasıyla örtüşüyor).
_CATEGORY_COLORS: dict[str, dict[str, str]] = {
    "modrinth": {"light": "#1baf7a", "dark": "#199e70"},  # slot 3 aqua/yeşil
    "curseforge": {"light": "#eb6834", "dark": "#d95926"},  # slot 2 turuncu
    "vanilla": {"light": "#6b7280", "dark": "#6b7280"},  # nötr gri — kategori değil, "loader yok" durumu
    "fabric": {"light": "#eda100", "dark": "#c98500"},  # slot 4 sarı
    "quilt": {"light": "#e87ba4", "dark": "#d55181"},  # slot 5 magenta
    "forge": {"light": "#4a3aa7", "dark": "#9085e9"},  # slot 7 mor
    "neoforge": {"light": "#eb6834", "dark": "#d95926"},  # slot 2 turuncu
}

STATUS_GOOD = "#0ca30c"
"""dataviz skill'in durum paleti — "başarılı/eklendi" gibi durum göstergeleri
için, kategorik renklerden (ör. Modrinth yeşili) AYRI tutulur; aksi halde bir
durum rengi yanlışlıkla bir kategoriyle karıştırılabilir."""

DARK_PALETTE = {
    "accent": "#5b8def",
    "accent_dim": "#3d6bb3",
    "bg": "#191a1d",
    "panel_bg": "#232428",
    "field_bg": "#2b2d31",
    "border": "#34363b",
    "text": "#e3e3e6",
    "text_muted": "#8a8d93",
    "hover_bg": "#2f333a",
    "alt_row_bg": "#26282c",
    "scrollbar_handle": "#3a3d41",
    "scrollbar_handle_hover": "#4a4d54",
    "selected_bg": "#3d6bb3",
    "selected_text": "#ffffff",
    "on_accent_text": "#ffffff",
    "danger_text": "#d03b3b",  # dataviz skill durum paleti: critical (temalar arası sabit)
    "chip_bg": "#2f333a",
    "chip_text": "#cfd2d6",
    "icon_placeholder_bg": "#2b2d31",
}

# Kullanıcının referans aldığı tasarımdan (yumuşak büyük köşeler, dolgun
# koyu seçim yerine hafif mavi tonlu seçim, panellerde gerçek yükselti/
# gölge hissi) ilham alınarak Tailwind Slate tonlarıyla yeniden kuruldu.
LIGHT_PALETTE = {
    "accent": "#2563eb",
    "accent_dim": "#1d4ed8",
    "bg": "#eef1f5",
    "panel_bg": "#ffffff",
    "field_bg": "#ffffff",
    "border": "#e1e5eb",
    "text": "#1e2430",
    "text_muted": "#6b7280",
    "hover_bg": "#f4f6f9",
    "alt_row_bg": "#f8f9fb",
    "scrollbar_handle": "#cbd2d9",
    "scrollbar_handle_hover": "#a8b0ba",
    "selected_bg": "#e8f0fe",
    "selected_text": "#1d4ed8",
    "on_accent_text": "#ffffff",
    "danger_text": "#d03b3b",  # dataviz skill durum paleti: critical (temalar arası sabit)
    "chip_bg": "#eef1f5",
    "chip_text": "#374151",
    "icon_placeholder_bg": "#eef1f5",
}


def _build_stylesheet(p: dict[str, str]) -> str:
    return f"""
QWidget {{
    background-color: {p['bg']};
    color: {p['text']};
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background-color: {p['bg']};
}}

QGroupBox {{
    background-color: {p['panel_bg']};
    border: 1px solid {p['border']};
    border-radius: 12px;
    margin-top: 14px;
    padding: 12px 10px 10px 10px;
    font-weight: 600;
}}
QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    top: -2px;
    padding: 0 4px;
    color: {p['accent']};
}}

QListWidget, QTableWidget, QTreeWidget, QLineEdit, QTextEdit, QComboBox {{
    background-color: {p['field_bg']};
    border: 1px solid {p['border']};
    border-radius: 10px;
    padding: 4px;
    selection-background-color: {p['selected_bg']};
}}
QLineEdit, QComboBox {{
    padding: 6px 8px;
}}
QLineEdit:focus, QComboBox:focus, QTextEdit:focus {{
    border: 1px solid {p['accent']};
}}
QListWidget::item, QTableWidget::item {{
    padding: 3px;
    border: none;
    border-radius: 6px;
}}
QListWidget::item:selected, QTableWidget::item:selected {{
    background-color: {p['selected_bg']};
    color: {p['selected_text']};
}}
QListWidget::item:hover, QTableWidget::item:hover {{
    background-color: {p['hover_bg']};
}}
QTableWidget {{
    gridline-color: {p['border']};
    alternate-background-color: {p['alt_row_bg']};
}}
QTableWidget::item {{
    border-bottom: 1px solid {p['border']};
    border-radius: 0px;
}}

QPushButton {{
    background-color: {p['field_bg']};
    border: 1px solid {p['border']};
    border-radius: 9px;
    padding: 7px 16px;
}}
QPushButton:hover {{
    background-color: {p['hover_bg']};
    border: 1px solid {p['accent_dim']};
}}
QPushButton:pressed {{
    background-color: {p['accent_dim']};
    color: {p['on_accent_text']};
}}
QPushButton:disabled {{
    color: {p['text_muted']};
    background-color: {p['field_bg']};
}}

QPushButton#primary {{
    background-color: {p['accent']};
    border: 1px solid {p['accent']};
    color: {p['on_accent_text']};
    font-weight: 600;
}}
QPushButton#primary:hover {{
    background-color: {p['accent_dim']};
    border: 1px solid {p['accent_dim']};
}}
QPushButton#danger {{
    color: {p['danger_text']};
}}

QHeaderView::section {{
    background-color: {p['panel_bg']};
    color: {p['text_muted']};
    border: none;
    border-bottom: 1px solid {p['border']};
    border-right: 1px solid {p['border']};
    padding: 5px;
    font-weight: 600;
}}
QTableCornerButton::section {{
    background-color: {p['panel_bg']};
    border: none;
}}

QSplitter::handle {{
    background-color: {p['bg']};
    width: 4px;
}}

QProgressBar {{
    border: 1px solid {p['border']};
    border-radius: 8px;
    text-align: center;
    background-color: {p['field_bg']};
}}
QProgressBar::chunk {{
    background-color: {p['accent']};
    border-radius: 7px;
}}

QLabel[role="heading"] {{
    font-weight: 700;
    font-size: 14px;
    padding: 2px 0;
    color: {p['text']};
}}
QLabel[role="muted"] {{
    color: {p['text_muted']};
    font-size: 12px;
}}

QMenuBar, QToolBar {{
    background-color: {p['panel_bg']};
    border-bottom: 1px solid {p['border']};
    spacing: 6px;
}}
QMenuBar::item:selected {{
    background-color: {p['hover_bg']};
}}
QMenu {{
    background-color: {p['panel_bg']};
    border: 1px solid {p['border']};
    border-radius: 10px;
}}
QMenu::item:selected {{
    background-color: {p['accent_dim']};
    color: {p['on_accent_text']};
    border-radius: 6px;
}}

QStatusBar {{
    background-color: {p['panel_bg']};
    border-top: 1px solid {p['border']};
}}

QScrollBar:vertical {{
    background-color: {p['bg']};
    width: 10px;
    margin: 0;
}}
QScrollBar::handle:vertical {{
    background-color: {p['scrollbar_handle']};
    border-radius: 5px;
    min-height: 24px;
}}
QScrollBar::handle:vertical:hover {{
    background-color: {p['scrollbar_handle_hover']};
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
"""


DARK_STYLESHEET = _build_stylesheet(DARK_PALETTE)
LIGHT_STYLESHEET = _build_stylesheet(LIGHT_PALETTE)

THEMES = {"dark": DARK_STYLESHEET, "light": LIGHT_STYLESHEET}
PALETTES = {"dark": DARK_PALETTE, "light": LIGHT_PALETTE}

_active_theme = "dark"
"""Global QSS ile stillendirilemeyen, Python tarafında elle çizilen rozet/
placeholder renkleri (bkz. chip_colors, icon_placeholder_bg) bu aktif
temayı okur — aksi halde açık temada koyu renkli rozetler kalıp göze
batardı (kullanıcı geri bildirimi: "beyaz tema çok kötü ürkünç olmuş")."""


def set_active_theme(theme_name: str) -> None:
    global _active_theme
    _active_theme = theme_name if theme_name in PALETTES else "dark"


def stylesheet_for(theme_name: str) -> str:
    return THEMES.get(theme_name, DARK_STYLESHEET)


def chip_colors() -> tuple[str, str]:
    """(arka_plan, metin) — mod tablosundaki 'Ortam' rozeti için."""
    p = PALETTES[_active_theme]
    return p["chip_bg"], p["chip_text"]


def icon_placeholder_bg() -> str:
    return PALETTES[_active_theme]["icon_placeholder_bg"]


def apply_card_shadow(widget) -> None:
    """Panellere (QGroupBox'lar) referans tasarımdaki gibi hafif bir
    yükselti/gölge verir — QSS'in box-shadow'u olmadığı için
    QGraphicsDropShadowEffect ile emüle ediyoruz."""
    from PySide6.QtGui import QColor
    from PySide6.QtWidgets import QGraphicsDropShadowEffect

    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(22)
    effect.setXOffset(0)
    effect.setYOffset(3)
    effect.setColor(QColor(0, 0, 0, 45))
    widget.setGraphicsEffect(effect)


def _category_color(key: str) -> str:
    step = _CATEGORY_COLORS.get(key)
    if step is None:
        return PALETTES[_active_theme]["text_muted"]
    return step[_active_theme]


def source_color(value: str) -> str:
    return _category_color(value)


def loader_color(value: str) -> str:
    return _category_color(value)
