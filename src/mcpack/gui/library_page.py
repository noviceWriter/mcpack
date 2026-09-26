"""Kütüphane sayfası: tüm pack'lerin listelendiği ana giriş ekranı.

CurseForge App'in "My Modpacks" listesinden ilham alındı — sabit, dar bir
kenar çubuğu yerine geniş, taranabilir bir liste; her satır kendi başına bir
"instance kartı" (ikon + ad + loader/versiyon + mod sayısı + eylemler).
Bir pack'e tıklamak MainWindow'u InstancePage'e geçirir (bkz. main_window.py).
"""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from mcpack.gui.theme import DARK_PALETTE, chip_colors, loader_color
from mcpack.gui.widgets import _badge_label
from mcpack.models import Pack

_LOADER_ICONS = {
    "vanilla": "🌱",
    "fabric": "🧵",
    "quilt": "🧶",
    "forge": "🔨",
    "neoforge": "🔥",
}


class _InstanceRow(QFrame):
    """Tek bir pack'i temsil eden, tıklanabilir geniş satır."""

    opened = Signal()
    delete_requested = Signal()

    def __init__(self, pack: Pack) -> None:
        super().__init__()
        self.setObjectName("instanceRow")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setStyleSheet(
            f"QFrame#instanceRow {{ background-color: {DARK_PALETTE['panel_bg']}; "
            f"border: 1px solid {DARK_PALETTE['border']}; border-radius: 10px; }} "
            f"QFrame#instanceRow:hover {{ background-color: {DARK_PALETTE['hover_bg']}; "
            f"border: 1px solid {DARK_PALETTE['button_hover_border']}; }}"
        )

        layout = QHBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(14)

        loader_label = "Vanilla" if pack.loader.value == "vanilla" else pack.loader.value.capitalize()
        icon = _LOADER_ICONS.get(pack.loader.value, "❓")
        badge = _badge_label(icon, loader_color(pack.loader.value), size=44)
        layout.addWidget(badge)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_label = QLabel(pack.name)
        name_label.setStyleSheet("font-weight: 700; font-size: 15px; background: transparent;")
        text_col.addWidget(name_label)

        loader_version = f" {pack.loader_version}" if pack.loader_version else ""
        subtitle = QLabel(f"{loader_label}{loader_version}  ·  MC {pack.minecraft}")
        subtitle.setProperty("role", "muted")
        subtitle.setStyleSheet("background: transparent;")
        text_col.addWidget(subtitle)
        layout.addLayout(text_col, 1)

        content_count = len(pack.content_downloads) + len(pack.content)
        if content_count:
            content_chip = self._chip(f"{content_count} içerik")
            layout.addWidget(content_chip)

        mod_chip = self._chip(f"{len(pack.mods)} mod")
        layout.addWidget(mod_chip)

        open_button = QPushButton("Aç")
        open_button.setObjectName("primary")
        open_button.clicked.connect(self.opened.emit)
        layout.addWidget(open_button)

        delete_button = QPushButton("Sil")
        delete_button.setObjectName("danger")
        delete_button.clicked.connect(self.delete_requested.emit)
        layout.addWidget(delete_button)

    def _chip(self, text: str) -> QLabel:
        chip_bg, chip_text = chip_colors()
        chip = QLabel(text)
        chip.setStyleSheet(
            f"background-color: {chip_bg}; color: {chip_text}; border-radius: 4px; "
            "padding: 2px 8px; font-size: 11px;"
        )
        return chip

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        if event.button() == Qt.MouseButton.LeftButton:
            self.opened.emit()
        super().mousePressEvent(event)


class LibraryPage(QWidget):
    """Ana kütüphane sayfası: arama + pack listesi + "Yeni Pack"."""

    pack_opened = Signal(str)  # pack id
    new_pack_requested = Signal()
    delete_pack_requested = Signal(str)  # pack id

    def __init__(self) -> None:
        super().__init__()
        self._packs: list[Pack] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        header = QHBoxLayout()
        title = QLabel("Pack'lerim")
        title.setStyleSheet("font-size: 20px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Pack ara...")
        self.search_input.setFixedWidth(240)
        self.search_input.textChanged.connect(self._refresh_rows)
        header.addWidget(self.search_input)

        new_button = QPushButton("+ Yeni Pack")
        new_button.setObjectName("primary")
        new_button.clicked.connect(self.new_pack_requested.emit)
        header.addWidget(new_button)
        outer.addLayout(header)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        outer.addWidget(self.scroll_area, 1)

        self._list_container = QWidget()
        self._list_layout = QVBoxLayout(self._list_container)
        self._list_layout.setContentsMargins(0, 0, 4, 0)
        self._list_layout.setSpacing(8)
        self._list_layout.addStretch()
        self.scroll_area.setWidget(self._list_container)

        self.empty_state = QWidget()
        empty_layout = QVBoxLayout(self.empty_state)
        empty_layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.setSpacing(6)
        empty_icon = QLabel("📦")
        empty_icon.setStyleSheet("font-size: 40px;")
        empty_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_icon)
        empty_title = QLabel("Henüz hiç pack yok")
        empty_title.setStyleSheet("font-size: 16px; font-weight: 600;")
        empty_title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_title)
        empty_sub = QLabel('"+ Yeni Pack" ile ilk pack\'ini oluştur.')
        empty_sub.setProperty("role", "muted")
        empty_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_layout.addWidget(empty_sub)
        self.empty_state.hide()
        outer.addWidget(self.empty_state, 1)

    def set_packs(self, packs: list[Pack]) -> None:
        self._packs = packs
        self._refresh_rows()

    def _refresh_rows(self) -> None:
        while self._list_layout.count() > 1:
            item = self._list_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        query = self.search_input.text().strip().lower()
        visible_packs = [p for p in self._packs if query in p.name.lower()] if query else self._packs

        self.scroll_area.setVisible(bool(self._packs))
        self.empty_state.setVisible(not self._packs)

        for pack in visible_packs:
            row = _InstanceRow(pack)
            row.opened.connect(lambda p=pack: self.pack_opened.emit(p.id))
            row.delete_requested.connect(lambda p=pack: self.delete_pack_requested.emit(p.id))
            self._list_layout.insertWidget(self._list_layout.count() - 1, row)
