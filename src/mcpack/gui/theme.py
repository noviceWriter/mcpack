"""MC Pack Manager için renk paletleri (açık ve koyu tema).

color.md'de tanımlı renk paleti: tema seçimi için _CATEGORY_COLORS haricinde
her şey burada. Kullanıcı geri bildirimi: düzeltme1.md.
"""

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
_CATEGORY_COLORS: dict[str, str] = {
    "modrinth": "#199e70",
    "curseforge": "#d95926",
    "vanilla": "#6b7280",
    "fabric": "#c98500",
    "quilt": "#d55181",
    "forge": "#9085e9",
    "neoforge": "#d95926",
}

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
    "selected_bg": "#28344a",  # yumuşak koyu lacivert ton (solid canlı mavi dolgu DEĞİL — düzeltme2.md)
    "selected_text": "#cfe0ff",  # açık mavi-beyaz, okunaklı ama göz yormayan
    "selected_stripe": "#5b8def",
    "on_accent_text": "#ffffff",
    "disabled_text": "#6b6f76",
    "danger_text": "#d03b3b",  # dataviz skill durum paleti: critical (temalar arası sabit)
    "status_good": "#0ca30c",  # dataviz skill durum paleti: good
    "status_warning": "#f97316",
    "warning_box_bg": "#3f2d0a",
    "warning_box_text": "#fbbf24",
    "accent_purple": "#9085e9",
    "accent_cyan": "#22b8cf",
    "accent_pink": "#e87ba4",
    "button_border": "#34363b",
    "button_hover_border": "#4a4d54",
    "chip_bg": "#2f333a",
    "chip_text": "#cfd2d6",
    "icon_placeholder_bg": "#2b2d31",
}

# Açık tema paleti - color.md'ye ve düzeltme1.md'ye göre
LIGHT_PALETTE = {
    "accent": "#3b82f6",  # Canlı Mavi — birincil buton arka planı
    "accent_dim": "#2563eb",  # birincil buton hover'ı / seçili öğe sol şeridi
    "bg": "#f8f9fa",  # Ana arka plan (Body) — saf beyaz göz yorar
    "panel_bg": "#ffffff",  # Kart/Panel arka planı
    "field_bg": "#ffffff",
    "border": "#e5e7eb",
    "text": "#1f2937",  # Koyu Antrasit — saf siyah yerine
    "text_muted": "#6b7280",  # İkincil metin
    "hover_bg": "#f3f4f6",
    "alt_row_bg": "#f9fafb",
    "scrollbar_handle": "#d1d5db",
    "scrollbar_handle_hover": "#9ca3af",
    "selected_bg": "#eff6ff",  # Seçili öğe — çok açık, yumuşak mavi
    "selected_text": "#1d4ed8",  # Koyu mavi, okunaklı
    "selected_stripe": "#3b82f6",  # Seçili öğenin sol kenarındaki 4px şerit
    "on_accent_text": "#ffffff",
    "disabled_text": "#9ca3af",
    "danger_text": "#ef4444",  # Tehlike/İptal metni
    "status_good": "#16a34a",  # dataviz skill durum paleti: good
    "status_warning": "#f97316",
    "warning_box_bg": "#fef3c7",  # Uyarı/bilgi kutusu
    "warning_box_text": "#92400e",
    "accent_purple": "#7c3aed",  # öne çıkan/kategori
    "accent_cyan": "#0891b2",  # info/tooltip
    "accent_pink": "#db2777",  # favori/popüler
    "button_border": "#d1d5db",  # ikincil buton kenarlığı
    "button_hover_border": "#9ca3af",
    "chip_bg": "#f3f4f6",
    "chip_text": "#374151",
    "icon_placeholder_bg": "#f3f4f6",
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
QListWidget::item {{
    border-left: 4px solid transparent;
}}
QListWidget::item:selected {{
    background-color: {p['selected_bg']};
    color: {p['selected_text']};
    border-left: 4px solid {p['selected_stripe']};
    border-top-left-radius: 0px;
    border-bottom-left-radius: 0px;
}}
QTableWidget::item:selected {{
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
    border: 1px solid {p['button_border']};
    border-radius: 9px;
    padding: 7px 16px;
}}
QPushButton:hover {{
    background-color: {p['hover_bg']};
    border: 1px solid {p['button_hover_border']};
}}
QPushButton:pressed {{
    background-color: {p['accent_dim']};
    color: {p['on_accent_text']};
    border: 1px solid {p['accent_dim']};
}}
QPushButton:disabled {{
    color: {p['disabled_text']};
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
QLabel#warningBox {{
    background-color: {p['warning_box_bg']};
    color: {p['warning_box_text']};
    border-radius: 8px;
    padding: 10px 12px;
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


def status_good_color() -> str:
    """"Başarılı/eklendi" gibi durum göstergeleri için — kategorik renklerden
    (ör. Modrinth yeşili) AYRI tutulur, aksi halde bir durum rengi yanlışlıkla
    bir kategoriyle karıştırılabilir."""
    return PALETTES[_active_theme]["status_good"]


def danger_color() -> str:
    return DARK_PALETTE["danger_text"]


def pack_text_colors(selected: bool) -> tuple[str, str]:
    palette = PALETTES[_active_theme]
    if selected:
        return palette["selected_text"], palette["selected_text"]
    return palette["text"], palette["text_muted"]


def pack_card_background(selected: bool) -> str:
    palette = PALETTES[_active_theme]
    return palette["selected_bg"] if selected else palette["panel_bg"]


def pack_card_stripe(selected: bool) -> str:
    """Seçili pack kartının sol kenarındaki ince şerit — QListWidget'ın kendi
    ::item:selected border-left'i _PackCard'ın opak arka planının ALTINDA
    kalıp görünmediği için kart burada kendi şeridini çiziyor (bkz.
    düzeltme2.md: solid dolgu yerine ton+şerit)."""
    return PALETTES[_active_theme]["selected_stripe"] if selected else "transparent"


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
    color = _CATEGORY_COLORS.get(key)
    if color is None:
        return PALETTES[_active_theme]["text_muted"]
    return color


def source_color(value: str) -> str:
    return _category_color(value)


def loader_color(value: str) -> str:
    return _category_color(value)
