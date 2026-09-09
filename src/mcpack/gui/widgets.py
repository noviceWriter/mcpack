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
from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
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
# Sol panel: pack listesi
# ---------------------------------------------------------------------------


class PackListPanel(QWidget):
    pack_selected = Signal(str)
    new_pack_requested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self._packs: list[Pack] = []

        layout = QVBoxLayout(self)
        heading = QLabel("Pack'ler")
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        self.list_widget = QListWidget()
        self.list_widget.currentRowChanged.connect(self._on_row_changed)
        layout.addWidget(self.list_widget)

        new_button = QPushButton("+ Yeni Pack")
        new_button.clicked.connect(self.new_pack_requested.emit)
        layout.addWidget(new_button)

    def set_packs(self, packs: list[Pack]) -> None:
        self._packs = packs
        self.list_widget.clear()
        for pack in packs:
            item = QListWidgetItem(f"{pack.name}  ({pack.loader.value} {pack.minecraft})")
            self.list_widget.addItem(item)

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
        layout = QVBoxLayout(self)

        self.heading = QLabel("Pack seçilmedi")
        self.heading.setProperty("role", "heading")
        layout.addWidget(self.heading)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Mod", "Kaynak", "Client", "Server"])
        self.table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        remove_button = QPushButton("Seçili Modu Çıkar")
        remove_button.clicked.connect(self._on_remove_clicked)
        button_row.addWidget(remove_button)

        env_button = QPushButton("Client/Server Düzelt")
        env_button.clicked.connect(self._on_edit_env_clicked)
        button_row.addWidget(env_button)
        layout.addLayout(button_row)

    def show_pack(self, pack: Pack | None) -> None:
        if pack is None:
            self.heading.setText("Pack seçilmedi")
            self.table.setRowCount(0)
            return

        self.heading.setText(
            f"{pack.name} — {pack.loader.value} {pack.loader_version} / MC {pack.minecraft}  ({len(pack.mods)} mod)"
        )
        self.table.setRowCount(len(pack.mods))
        for row, mod in enumerate(pack.mods):
            self.table.setItem(row, 0, QTableWidgetItem(mod.file_name))
            self.table.setItem(row, 1, QTableWidgetItem(mod.source.value))
            self.table.setItem(row, 2, QTableWidgetItem(mod.env.client.value))
            self.table.setItem(row, 3, QTableWidgetItem(mod.env.server.value))
            self.table.item(row, 0).setData(Qt.ItemDataRole.UserRole, mod.project_id)

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
# Sağ üst panel: mod arama
# ---------------------------------------------------------------------------


class SearchPanel(QWidget):
    search_requested = Signal(str, str)  # query, source
    add_mod_requested = Signal(object)  # SearchResult

    def __init__(self) -> None:
        super().__init__()
        self._results: list[SearchResult] = []

        layout = QVBoxLayout(self)
        heading = QLabel("Mod Ara")
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        row = QHBoxLayout()
        self.query_input = QLineEdit()
        self.query_input.setPlaceholderText("Mod adı...")
        self.query_input.returnPressed.connect(self._on_search_clicked)
        row.addWidget(self.query_input)

        self.source_combo = QComboBox()
        self.source_combo.addItem("Tümü (Modrinth + CurseForge)", "both")
        for s in ModSourceType:
            self.source_combo.addItem(s.value, s.value)
        row.addWidget(self.source_combo)

        search_button = QPushButton("Ara")
        search_button.clicked.connect(self._on_search_clicked)
        row.addWidget(search_button)
        layout.addLayout(row)

        self.results_list = QListWidget()
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
            self.results_list.addItem(f"[{r.source.value}] {r.title}  ({r.downloads} indirme)")

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

    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        heading = QLabel("Export / Aksiyonlar")
        heading.setProperty("role", "heading")
        layout.addWidget(heading)

        row = QHBoxLayout()
        self.format_combo = QComboBox()
        self.format_combo.addItem("Modrinth (.mrpack)", "mrpack")
        self.format_combo.addItem("CurseForge (.zip)", "curseforge")
        self.format_combo.addItem("Prism / MultiMC (.zip)", "prism")
        row.addWidget(self.format_combo)

        export_button = QPushButton("Export Et")
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
        layout.addWidget(self.progress)

        self.status_label = QLabel("")
        layout.addWidget(self.status_label)

    def set_progress(self, done: int, total: int) -> None:
        self.progress.setRange(0, max(total, 1))
        self.progress.setValue(done)

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)
