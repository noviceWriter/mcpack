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
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from mcpack.gui.icon_loader import load_icon
from mcpack.gui.theme import env_color, loader_color, source_color
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


_ENV_LABELS = {"required": "Gerekli", "optional": "Opsiyonel", "unsupported": "Yok"}
_SOURCE_LABELS = {"modrinth": "Modrinth", "curseforge": "CurseForge"}


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
# Orta panel: seçili pack'in içeriği
# ---------------------------------------------------------------------------


class PackDetailPanel(QWidget):
    remove_mod_requested = Signal(str)
    edit_env_requested = Signal(str)
    """CurseForge gibi kaynaklarda client/server bilgisi güvenilir olmayabilir;
    kullanıcı bu sinyalle seçili modun env'ini elle düzeltebilir (proje-amacı.md §6)."""

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        group, layout = _panel_group("Pack Detayı")
        outer.addWidget(group)

        self.summary_label = QLabel("Pack seçilmedi")
        self.summary_label.setProperty("role", "muted")
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Mod", "Kaynak", "Client", "Server"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        remove_button = QPushButton("Seçili Modu Çıkar")
        remove_button.setObjectName("danger")
        remove_button.clicked.connect(self._on_remove_clicked)
        button_row.addWidget(remove_button)

        env_button = QPushButton("Client/Server Düzelt")
        env_button.clicked.connect(self._on_edit_env_clicked)
        button_row.addWidget(env_button)
        layout.addLayout(button_row)

    def show_pack(self, pack: Pack | None) -> None:
        if pack is None:
            self.summary_label.setText("Pack seçilmedi")
            self.table.setRowCount(0)
            return

        loader_label = "Vanilla" if pack.loader.value == "vanilla" else pack.loader.value.capitalize()
        loader_version = f" {pack.loader_version}" if pack.loader_version else ""
        self.summary_label.setText(
            f"{pack.name}  ·  {loader_label}{loader_version}  ·  MC {pack.minecraft}  ·  {len(pack.mods)} mod"
        )
        self.table.setRowCount(len(pack.mods))
        for row, mod in enumerate(pack.mods):
            name_item = QTableWidgetItem(mod.file_name)
            name_item.setData(Qt.ItemDataRole.UserRole, mod.project_id)
            self.table.setItem(row, 0, name_item)

            source_label = _SOURCE_LABELS.get(mod.source.value, mod.source.value)
            self.table.setItem(row, 1, _colored_item(source_label, source_color(mod.source.value)))

            client_label = _ENV_LABELS.get(mod.env.client.value, mod.env.client.value)
            self.table.setItem(
                row, 2, _colored_item(client_label, env_color(mod.env.client.value), background=True)
            )

            server_label = _ENV_LABELS.get(mod.env.server.value, mod.env.server.value)
            self.table.setItem(
                row, 3, _colored_item(server_label, env_color(mod.env.server.value), background=True)
            )

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


# ---------------------------------------------------------------------------
# Sağ alt panel: export / server pack / SKLauncher aksiyonları
# ---------------------------------------------------------------------------


class ExportPanel(QWidget):
    export_requested = Signal(str)  # format key: mrpack/curseforge/prism
    server_pack_requested = Signal()
    run_sklauncher_requested = Signal()
    cancel_requested = Signal()
    """Büyük pack'lerde devam eden indirmeyi iptal etmek için (proje-amacı.md §6)."""

    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        group, layout = _panel_group("Export / Aksiyonlar")
        outer.addWidget(group)

        row = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItem("Modrinth (.mrpack)", "mrpack")
        self.format_combo.addItem("CurseForge (.zip)", "curseforge")
        self.format_combo.addItem("Prism / MultiMC (.zip)", "prism")
        row.addWidget(self.format_combo)

        export_button = QPushButton("Export Et")
        export_button.setObjectName("primary")
        export_button.clicked.connect(
            lambda: self.export_requested.emit(self.format_combo.currentData())
        )
        row.addWidget(export_button)
        layout.addLayout(row)

        server_button = QPushButton("Server Pack Oluştur")
        server_button.clicked.connect(self.server_pack_requested.emit)
        layout.addWidget(server_button)

        run_button = QPushButton("SKLauncher ile Çalıştır")
        run_button.clicked.connect(self.run_sklauncher_requested.emit)
        layout.addWidget(run_button)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setFixedHeight(20)
        layout.addWidget(self.progress)

        self.cancel_button = QPushButton("İptal")
        self.cancel_button.setObjectName("danger")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self.cancel_button)

        self.status_label = QLabel("")
        self.status_label.setProperty("role", "muted")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        layout.addStretch()

    def set_busy(self, busy: bool) -> None:
        self.cancel_button.setEnabled(busy)

    def set_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
