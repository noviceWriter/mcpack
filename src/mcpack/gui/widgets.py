"""GUI panelleri: pack listesi, pack detayı, mod arama, export/aksiyon paneli.

proje-amacı.md §2.6'daki 3 panelli düzen (sol: pack listesi, orta: pack
içeriği, sağ/alt: arama+export+server+launcher) burada uygulanır.
"""

from __future__ import annotations

import asyncio
import traceback
from collections.abc import Awaitable, Callable
from typing import Any

from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QColor, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mcpack.gui.icon_loader import load_icon
from mcpack.gui.theme import loader_color, source_color
from mcpack.models import ModSourceType, Pack
from mcpack.sources.base import SearchResult

# ---------------------------------------------------------------------------
# Async yardımcı: coroutine'leri ayrı QThread'de çalıştırıp GUI'yi dondurmaz.
# ---------------------------------------------------------------------------


class _WorkerSignals(QObject):
    result = Signal(object)
    error = Signal(str)


class _AsyncWorker(QThread):
    def __init__(self, coro_factory: Callable[[], Awaitable[Any]]) -> None:
        super().__init__()
        self._coro_factory = coro_factory
        self.signals = _WorkerSignals()

    def run(self) -> None:
        try:
            result = asyncio.run(self._coro_factory())
        except Exception as exc:  # GUI'de göstermek için genel yakalama
            self.signals.error.emit(f"{exc}\n{traceback.format_exc()}")
        else:
            self.signals.result.emit(result)


_active_workers: list[_AsyncWorker] = []


def run_async(
    coro_factory: Callable[[], Awaitable[Any]],
    *,
    on_success: Callable[[Any], None] | None = None,
    on_error: Callable[[str], None] | None = None,
) -> None:
    worker = _AsyncWorker(coro_factory)
    _active_workers.append(worker)

    def _cleanup() -> None:
        if worker in _active_workers:
            _active_workers.remove(worker)

    if on_success:
        worker.signals.result.connect(on_success)
    if on_error:
        worker.signals.error.connect(on_error)
    worker.finished.connect(_cleanup)
    worker.start()


# ---------------------------------------------------------------------------
# Ortak yardımcılar
# ---------------------------------------------------------------------------


def _panel_group(title: str) -> tuple[QGroupBox, QVBoxLayout]:
    """Her paneli çerçeveli/başlıklı bir kutuya alır — düz üst üste widget
    yığını yerine gerçek bir uygulama görünümü verir."""
    box = QGroupBox(title)
    layout = QVBoxLayout(box)
    layout.setSpacing(8)
    return box, layout


def format_downloads(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


_SOURCE_LABELS = {"modrinth": "Modrinth", "curseforge": "CurseForge"}


def _supported_environments(client: str, server: str) -> list[str]:
    """Modrinth'in mod sayfasındaki "Supported environments" rozetleriyle
    birebir aynı mantık: client/server'ın required/optional/unsupported
    kombinasyonundan hangi kurulum şekillerinin (sadece istemci, sadece
    sunucu, ikisi birden) geçerli olduğunu çıkarır."""
    labels = []
    if client != "unsupported" and server != "required":
        labels.append("İstemci")
    if server != "unsupported" and client != "required":
        labels.append("Sunucu")
    if client != "unsupported" and server != "unsupported":
        labels.append("İstemci + Sunucu")
    return labels


def _env_badges_widget(client: str, server: str) -> QWidget:
    container = QWidget()
    layout = QHBoxLayout(container)
    layout.setContentsMargins(4, 2, 4, 2)
    layout.setSpacing(4)

    labels = _supported_environments(client, server)
    if not labels:
        chip = QLabel("Bilinmiyor")
        chip.setProperty("role", "muted")
        layout.addWidget(chip)
    for text in labels:
        chip = QLabel(text)
        chip.setStyleSheet(
            "background-color: #2f333a; color: #cfd2d6; border-radius: 4px; "
            "padding: 2px 8px; font-size: 11px;"
        )
        layout.addWidget(chip)
    layout.addStretch()
    return container


def _colored_item(text: str, color_hex: str, *, background: bool = False) -> QTableWidgetItem:
    item = QTableWidgetItem(text)
    if background:
        item.setBackground(QColor(color_hex))
        item.setForeground(QColor("#f0f0f0"))
    else:
        item.setForeground(QColor(color_hex))
    return item


def _badge_label(text: str, color_hex: str, *, size: int = 36) -> QLabel:
    """Prism/CurseForge tarzı köşeli renkli rozet — gerçek bir ikon yerine
    (network'ten çekilemeyen pack'ler için) loader/harf bazlı görsel kimlik."""
    badge = QLabel(text)
    badge.setFixedSize(size, size)
    badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
    badge.setStyleSheet(
        f"background-color: {color_hex}; color: #10110f; font-weight: 700; "
        f"border-radius: 8px; font-size: {max(11, size // 3)}px;"
    )
    return badge


def _icon_label(size: int = 40) -> QLabel:
    """Uzak sunucudan async yüklenecek bir mod ikonu için placeholder etiket."""
    label = QLabel()
    label.setFixedSize(size, size)
    label.setAlignment(Qt.AlignmentFlag.AlignCenter)
    label.setStyleSheet("background-color: #2b2d31; border-radius: 8px;")
    return label


def _set_scaled_pixmap(label: QLabel, pixmap: QPixmap) -> None:
    size = label.width()
    scaled = pixmap.scaled(
        size, size, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
    )
    label.setPixmap(scaled)


# ---------------------------------------------------------------------------
# Sol panel: pack listesi (CurseForge/Prism'deki "instance kartı" ilhamı)
# ---------------------------------------------------------------------------


class _PackCard(QWidget):
    def __init__(self, pack: Pack) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        loader_label = "Vanilla" if pack.loader.value == "vanilla" else pack.loader.value.capitalize()
        badge = _badge_label(loader_label[0], loader_color(pack.loader.value))
        layout.addWidget(badge)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)
        name_label = QLabel(pack.name)
        name_label.setStyleSheet("font-weight: 600; font-size: 13px;")
        text_col.addWidget(name_label)

        subtitle = QLabel(f"{loader_label} · MC {pack.minecraft} · {len(pack.mods)} mod")
        subtitle.setProperty("role", "muted")
        text_col.addWidget(subtitle)

        layout.addLayout(text_col, 1)


class PackListPanel(QWidget):
    pack_selected = Signal(str)
    new_pack_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._packs: list[Pack] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        group, layout = _panel_group("Pack'ler")
        outer.addWidget(group)

        self.list_widget = QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setSpacing(2)
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.list_widget)

        new_button = QPushButton("+ Yeni Pack")
        new_button.setObjectName("primary")
        new_button.clicked.connect(self.new_pack_requested.emit)
        layout.addWidget(new_button)

    def set_packs(self, packs: list[Pack]) -> None:
        self._packs = packs
        self.list_widget.clear()
        for pack in packs:
            item = QListWidgetItem()
            card = _PackCard(pack)
            item.setSizeHint(card.sizeHint())
            self.list_widget.addItem(item)
            self.list_widget.setItemWidget(item, card)

    def _on_row_changed(self, row: int) -> None:
        if 0 <= row < len(self._packs):
            self.pack_selected.emit(self._packs[row].id)


# ---------------------------------------------------------------------------
# Ana içerik alanı: seçili pack'in başlığı + eylem araç çubuğu + mod tablosu.
#
# CurseForge App / Prism Launcher'da mod ekleme kalıcı bir yan panel değil,
# ayrı bir "gözat" akışıdır (bkz. gui/mod_search_dialog.py); export/server/
# SKLauncher gibi eylemler de başlığın yanında kompakt bir araç çubuğunda
# durur — bu yüzden burada artık tek bir kutuya sıkışmış 4 panel yok.
# ---------------------------------------------------------------------------


class PackDetailPanel(QWidget):
    remove_mod_requested = Signal(str)
    edit_env_requested = Signal(str)
    """CurseForge gibi kaynaklarda client/server bilgisi güvenilir olmayabilir;
    kullanıcı bu sinyalle seçili modun env'ini elle düzeltebilir (proje-amacı.md §6)."""
    add_mod_clicked = Signal()
    export_requested = Signal(str)  # format key: mrpack/curseforge/prism
    server_pack_requested = Signal()
    run_sklauncher_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(20, 16, 20, 16)
        outer.setSpacing(12)

        header = QHBoxLayout()
        title_col = QVBoxLayout()
        title_col.setSpacing(2)
        self.title_label = QLabel("Pack seçilmedi")
        self.title_label.setStyleSheet("font-size: 19px; font-weight: 700;")
        title_col.addWidget(self.title_label)
        self.subtitle_label = QLabel("Soldan bir pack seçin ya da yeni oluşturun.")
        self.subtitle_label.setProperty("role", "muted")
        title_col.addWidget(self.subtitle_label)
        header.addLayout(title_col)
        header.addStretch()

        self.format_combo = QComboBox()
        self.format_combo.addItem("Modrinth (.mrpack)", "mrpack")
        self.format_combo.addItem("CurseForge (.zip)", "curseforge")
        self.format_combo.addItem("Prism / MultiMC (.zip)", "prism")
        header.addWidget(self.format_combo)

        export_button = QPushButton("Export Et")
        export_button.setObjectName("primary")
        export_button.clicked.connect(
            lambda: self.export_requested.emit(self.format_combo.currentData())
        )
        header.addWidget(export_button)

        server_button = QPushButton("Server Pack")
        server_button.clicked.connect(self.server_pack_requested.emit)
        header.addWidget(server_button)

        sklauncher_button = QPushButton("SKLauncher")
        sklauncher_button.clicked.connect(self.run_sklauncher_requested.emit)
        header.addWidget(sklauncher_button)

        outer.addLayout(header)

        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["Mod", "Kaynak", "Ortam"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.setColumnWidth(1, 100)
        self.table.setColumnWidth(2, 220)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        outer.addWidget(self.table, 1)

        self.mod_actions_bar = QWidget()
        button_row = QHBoxLayout(self.mod_actions_bar)
        button_row.setContentsMargins(0, 0, 0, 0)
        add_button = QPushButton("+ Mod Ekle")
        add_button.setObjectName("primary")
        add_button.clicked.connect(self.add_mod_clicked.emit)
        button_row.addWidget(add_button)

        remove_button = QPushButton("Seçili Modu Çıkar")
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(self._on_remove_clicked)
        button_row.addWidget(remove_button)

        env_button = QPushButton("Client/Server Düzelt")
        env_button.clicked.connect(self._on_edit_env_clicked)
        button_row.addWidget(env_button)
        button_row.addStretch()
        outer.addWidget(self.mod_actions_bar)

        self.vanilla_notice = QLabel(
            "Vanilla pack'lerde mod eklenemez — mod eklemek için bir loader (Fabric/Quilt/Forge/NeoForge) seçin."
        )
        self.vanilla_notice.setProperty("role", "muted")
        self.vanilla_notice.setWordWrap(True)
        self.vanilla_notice.hide()
        outer.addWidget(self.vanilla_notice)

    def show_pack(self, pack: Pack | None) -> None:
        if pack is None:
            self.title_label.setText("Pack seçilmedi")
            self.subtitle_label.setText("Soldan bir pack seçin ya da yeni oluşturun.")
            self.table.setRowCount(0)
            self.table.hide()
            self.mod_actions_bar.hide()
            self.vanilla_notice.hide()
            return

        is_vanilla = pack.loader.value == "vanilla"
        loader_label = "Vanilla" if is_vanilla else pack.loader.value.capitalize()
        loader_version = f" {pack.loader_version}" if pack.loader_version else ""
        self.title_label.setText(pack.name)
        self.subtitle_label.setText(
            f"{loader_label}{loader_version}  ·  MC {pack.minecraft}  ·  {len(pack.mods)} mod"
        )

        # Vanilla pack'lere mod eklenemez (loader yok) — mod tablosu ve
        # ekleme/düzenleme araç çubuğu bu durumda tamamen gizlenir.
        self.table.setVisible(not is_vanilla)
        self.mod_actions_bar.setVisible(not is_vanilla)
        self.vanilla_notice.setVisible(is_vanilla)
        if is_vanilla:
            self.table.setRowCount(0)
            return

        self.table.setRowCount(len(pack.mods))
        for row, mod in enumerate(pack.mods):
            name_item = QTableWidgetItem(mod.file_name)
            name_item.setData(Qt.ItemDataRole.UserRole, mod.project_id)
            self.table.setItem(row, 0, name_item)

            source_label = _SOURCE_LABELS.get(mod.source.value, mod.source.value)
            self.table.setItem(row, 1, _colored_item(source_label, source_color(mod.source.value)))

            self.table.setCellWidget(row, 2, _env_badges_widget(mod.env.client.value, mod.env.server.value))

    def _on_remove_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is not None:
            self.remove_mod_requested.emit(item.data(Qt.ItemDataRole.UserRole))

    def _on_edit_env_clicked(self) -> None:
        row = self.table.currentRow()
        if row < 0:
            return
        item = self.table.item(row, 0)
        if item is not None:
            self.edit_env_requested.emit(item.data(Qt.ItemDataRole.UserRole))


# ---------------------------------------------------------------------------
# Sağ üst panel: mod arama (CurseForge/Modrinth uygulamalarındaki "mod kartı"
# görünümü ilham alındı: ikon + başlık + açıklama + kaynak rozeti + indirme)
# ---------------------------------------------------------------------------


class _ModResultCard(QWidget):
    def __init__(self, result: SearchResult) -> None:
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 6)
        layout.setSpacing(10)

        self.icon_label = _icon_label(40)
        layout.addWidget(self.icon_label)

        text_col = QVBoxLayout()
        text_col.setSpacing(2)

        title_row = QHBoxLayout()
        title_row.setSpacing(8)
        title = QLabel(result.title)
        title.setStyleSheet("font-weight: 600; font-size: 13px;")
        title_row.addWidget(title)

        source_badge = QLabel(_SOURCE_LABELS.get(result.source.value, result.source.value))
        source_badge.setStyleSheet(
            f"color: {source_color(result.source.value)}; font-weight: 600; font-size: 11px;"
        )
        title_row.addWidget(source_badge)
        title_row.addStretch()

        downloads = QLabel(f"⬇ {format_downloads(result.downloads)}")
        downloads.setProperty("role", "muted")
        title_row.addWidget(downloads)
        text_col.addLayout(title_row)

        if result.description:
            desc = QLabel(result.description)
            desc.setProperty("role", "muted")
            desc.setWordWrap(True)
            desc.setMaximumHeight(32)
            text_col.addWidget(desc)

        layout.addLayout(text_col, 1)

        if result.icon_url:
            load_icon(result.icon_url, lambda pixmap: _set_scaled_pixmap(self.icon_label, pixmap))


class SearchPanel(QWidget):
    search_requested = Signal(str, str)  # query, source
    add_mod_requested = Signal(object)  # SearchResult

    def __init__(self) -> None:
        super().__init__()
        self._results: list[SearchResult] = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        group, layout = _panel_group("Mod Ara")
        outer.addWidget(group)

        row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Mod adı...")
        self.query_input.returnPressed.connect(self._on_search_clicked)
        row.addWidget(self.query_input)

        self.source_combo = QComboBox()
        self.source_combo.addItem("Tümü (Modrinth + CurseForge)", "both")
        for s in ModSourceType:
            self.source_combo.addItem(_SOURCE_LABELS.get(s.value, s.value), s.value)
        row.addWidget(self.source_combo)

        search_button = QPushButton("Ara")
        search_button.setObjectName("primary")
        search_button.clicked.connect(self._on_search_clicked)
        row.addWidget(search_button)
        layout.addLayout(row)

        self.results_list = QListWidget()
        self.results_list.setSpacing(2)
        self.results_list.itemDoubleClicked.connect(self._on_add_clicked)
        layout.addWidget(self.results_list)

        add_button = QPushButton("Seçili Modu Pack'e Ekle")
        add_button.clicked.connect(self._on_add_clicked)
        layout.addWidget(add_button)

    def _on_search_clicked(self) -> None:
        query = self.query_input.text().strip()
        if query:
            self.search_requested.emit(query, self.source_combo.currentData())

    def set_results(self, results: list[SearchResult]) -> None:
        self._results = results
        self.results_list.clear()
        for r in results:
            item = QListWidgetItem()
            card = _ModResultCard(r)
            item.setSizeHint(card.sizeHint())
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, card)

    def _on_add_clicked(self) -> None:
        row = self.results_list.currentRow()
        if 0 <= row < len(self._results):
            self.add_mod_requested.emit(self._results[row])
