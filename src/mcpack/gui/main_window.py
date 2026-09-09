"""Ana pencere: proje-amacı.md §2.6'daki 3 panelli düzeni birleştirir ve
tüm backend katmanlarını (sources, packs, export, launcher) GUI'ye bağlar.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QInputDialog,
    QMainWindow,
    QMessageBox,
    QSplitter,
)

from mcpack.config import Settings
from mcpack.downloader import make_client
from mcpack.export import CurseForgeExporter, MrpackExporter, PrismExporter, ServerPackExporter
from mcpack.gui.new_pack_dialog import NewPackDialog
from mcpack.gui.settings_dialog import SettingsDialog
from mcpack.gui.widgets import ExportPanel, PackDetailPanel, PackListPanel, SearchPanel, run_async
from mcpack.launcher import instances_dir_for, launch, prepare_instance
from mcpack.models import EnvRequirement, ModSourceType, Pack
from mcpack.packs import PackManager
from mcpack.sources import CurseForgeClient, ModrinthClient, search_all
from mcpack.sources.base import SearchResult

_FORMAT_EXPORTERS = {
    "mrpack": MrpackExporter,
    "curseforge": CurseForgeExporter,
    "prism": PrismExporter,
}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MC Pack Manager")
        self.resize(1150, 700)

        self.settings = Settings.load()
        self.manager = PackManager(self.settings.resolved_packs_dir())
        self.current_pack: Pack | None = None
        self._cancel_event: threading.Event | None = None

        self.pack_list = PackListPanel()
        self.pack_detail = PackDetailPanel()
        self.search_panel = SearchPanel()
        self.export_panel = ExportPanel()

        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.addWidget(self.search_panel)
        right_splitter.addWidget(self.export_panel)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(self.pack_list)
        main_splitter.addWidget(self.pack_detail)
        main_splitter.addWidget(right_splitter)
        main_splitter.setSizes([250, 550, 350])
        self.setCentralWidget(main_splitter)

        self._build_menu()
        self._wire_signals()
        self.reload_packs()

    # -- kurulum -----------------------------------------------------------

    def _build_menu(self) -> None:
        menu = self.menuBar().addMenu("Ayarlar")
        action = menu.addAction("CurseForge API Key / SKLauncher Yolu")
        action.triggered.connect(self.open_settings_dialog)

    def _wire_signals(self) -> None:
        self.pack_list.new_pack_requested.connect(self.create_pack_dialog)
        self.pack_list.pack_selected.connect(self.select_pack)
        self.pack_detail.remove_mod_requested.connect(self.remove_mod)
        self.pack_detail.edit_env_requested.connect(self.edit_mod_env)
        self.search_panel.search_requested.connect(self.do_search)
        self.search_panel.add_mod_requested.connect(self.add_mod)
        self.export_panel.export_requested.connect(self.do_export)
        self.export_panel.server_pack_requested.connect(self.do_server_pack)
        self.export_panel.run_sklauncher_requested.connect(self.do_run_sklauncher)
        self.export_panel.cancel_requested.connect(self.cancel_current_task)

    # -- ayarlar -------------------------------------------------------------

    def open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            dialog.apply_to(self.settings)
            self.settings.save()

    # -- pack listesi / detay ------------------------------------------------

    def reload_packs(self) -> None:
        self.pack_list.set_packs(self.manager.list_packs())

    def create_pack_dialog(self) -> None:
        dialog = NewPackDialog(self)
        if dialog.exec() != NewPackDialog.DialogCode.Accepted:
            return
        values = dialog.result_values()
        self.manager.create_pack(
            name=values["name"],
            minecraft=values["minecraft"],
            loader=values["loader"],
            loader_version=values["loader_version"],
            author=values["author"],
            summary=values["summary"],
        )
        self.reload_packs()

    def select_pack(self, pack_id: str) -> None:
        self.current_pack = self.manager.load(pack_id)
        self.pack_detail.show_pack(self.current_pack)

    def remove_mod(self, project_id: str) -> None:
        if not self.current_pack:
            return
        self.manager.remove_mod(self.current_pack, project_id)
        self.pack_detail.show_pack(self.current_pack)

    def edit_mod_env(self, project_id: str) -> None:
        """CurseForge gibi kaynaklar client/server bilgisini güvenilir vermeyebilir;
        kullanıcı burada elle düzeltir (proje-amacı.md §6)."""
        if not self.current_pack:
            return
        pack = self.current_pack
        entry = pack.find_mod(project_id)
        if entry is None:
            return

        env_values = [e.value for e in EnvRequirement]
        client, ok = QInputDialog.getItem(
            self, "Client Durumu", entry.file_name, env_values,
            current=env_values.index(entry.env.client.value), editable=False,
        )
        if not ok:
            return
        server, ok = QInputDialog.getItem(
            self, "Server Durumu", entry.file_name, env_values,
            current=env_values.index(entry.env.server.value), editable=False,
        )
        if not ok:
            return

        self.manager.set_mod_env(
            pack, project_id, client=EnvRequirement(client), server=EnvRequirement(server)
        )
        self.pack_detail.show_pack(pack)

    # -- mod arama / ekleme --------------------------------------------------

    def _make_source(self, source_name: str) -> ModrinthClient | CurseForgeClient:
        if source_name == ModSourceType.CURSEFORGE.value:
            return CurseForgeClient(self.settings.curseforge_api_key)
        return ModrinthClient()

    def do_search(self, query: str, source_name: str) -> None:
        if not self.current_pack:
            QMessageBox.warning(self, "Uyarı", "Önce bir pack seçin.")
            return
        pack = self.current_pack

        async def task() -> list[SearchResult]:
            if source_name == "both":
                modrinth = ModrinthClient()
                curseforge = (
                    CurseForgeClient(self.settings.curseforge_api_key)
                    if self.settings.curseforge_api_key
                    else None
                )
                try:
                    return await search_all(
                        query,
                        modrinth=modrinth,
                        curseforge=curseforge,
                        game_version=pack.minecraft,
                        loader=pack.loader,
                        prefer_modrinth=self.settings.prefer_modrinth,
                    )
                finally:
                    await modrinth.aclose()
                    if curseforge:
                        await curseforge.aclose()

            source = self._make_source(source_name)
            try:
                return await source.search(query, game_version=pack.minecraft, loader=pack.loader)
            finally:
                await source.aclose()

        self.export_panel.set_status("Aranıyor...")
        run_async(task, on_success=self._on_search_done, on_error=self._on_error)

    def _on_search_done(self, results: list[SearchResult]) -> None:
        self.search_panel.set_results(results)
        self.export_panel.set_status("Hazır")

    def add_mod(self, result: SearchResult) -> None:
        if not self.current_pack:
            return
        pack = self.current_pack

        async def task():
            source = self._make_source(result.source.value)
            try:
                detail = await source.get_project(result.project_id)
                versions = await source.get_versions(
                    result.project_id, game_version=pack.minecraft, loader=pack.loader
                )
                if not versions:
                    raise RuntimeError(f"{result.title}: {pack.minecraft}/{pack.loader.value} için uyumlu versiyon yok")
                self.manager.add_mod(pack, versions[0], detail)

                deps = await self.manager.resolve_dependencies(pack, source, versions[0])
                for dep_version in deps:
                    dep_detail = await source.get_project(dep_version.project_id)
                    self.manager.add_mod(pack, dep_version, dep_detail)
            finally:
                await source.aclose()

        self.export_panel.set_status(f"{result.title} ekleniyor...")
        run_async(task, on_success=lambda _: self._on_mod_added(), on_error=self._on_error)

    def _on_mod_added(self) -> None:
        self.pack_detail.show_pack(self.current_pack)
        self.export_panel.set_status("Mod eklendi")

    # -- export / server pack / sklauncher -----------------------------------

    def _pick_source_dir(self) -> Path:
        chosen = QFileDialog.getExistingDirectory(
            self, "Overrides kaynak klasörü (config, kubejs, defaultconfigs, ...)"
        )
        return Path(chosen) if chosen else Path.cwd()

    def _begin_cancellable_task(self) -> threading.Event:
        """Büyük pack'lerde iptal desteği (proje-amacı.md §6): her export/
        launcher görevi kendi cancel_event'iyle başlar, "İptal" butonu aktifleşir."""
        event = threading.Event()
        self._cancel_event = event
        self.export_panel.set_busy(True)
        return event

    def _end_cancellable_task(self) -> None:
        self._cancel_event = None
        self.export_panel.set_busy(False)

    def cancel_current_task(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
            self.export_panel.set_status("İptal ediliyor...")

    def do_export(self, format_key: str) -> None:
        if not self.current_pack:
            QMessageBox.warning(self, "Uyarı", "Önce bir pack seçin.")
            return
        pack = self.current_pack
        exporter_cls = _FORMAT_EXPORTERS[format_key]

        output_path, _ = QFileDialog.getSaveFileName(
            self, "Export Et", f"{pack.name}{exporter_cls.file_extension}", f"*{exporter_cls.file_extension}"
        )
        if not output_path:
            return
        source_dir = self._pick_source_dir()
        cancel_event = self._begin_cancellable_task()

        async def task() -> Path:
            async with make_client() as client:
                return await exporter_cls().export(
                    pack,
                    source_dir=source_dir,
                    output_path=Path(output_path),
                    cache_dir=self.settings.resolved_packs_dir() / ".cache" / pack.id,
                    client=client,
                    exclude_dirs=self.settings.excluded_override_dirs(),
                    progress_cb=self.export_panel.set_progress,
                    cancel_event=cancel_event,
                )

        self.export_panel.set_status("Export ediliyor...")

        def on_success(p: Path) -> None:
            self._end_cancellable_task()
            self.export_panel.set_status(f"Tamamlandı: {p}")

        def on_error(message: str) -> None:
            self._end_cancellable_task()
            self._on_error(message)

        run_async(task, on_success=on_success, on_error=on_error)

    def do_server_pack(self) -> None:
        if not self.current_pack:
            QMessageBox.warning(self, "Uyarı", "Önce bir pack seçin.")
            return
        pack = self.current_pack

        output_path, _ = QFileDialog.getSaveFileName(self, "Server Pack Oluştur", f"{pack.name}-server.zip", "*.zip")
        if not output_path:
            return
        source_dir = self._pick_source_dir()
        cancel_event = self._begin_cancellable_task()

        async def task() -> Path:
            async with make_client() as client:
                return await ServerPackExporter().export(
                    pack,
                    source_dir=source_dir,
                    output_path=Path(output_path),
                    cache_dir=self.settings.resolved_packs_dir() / ".cache" / pack.id,
                    client=client,
                    exclude_dirs=self.settings.excluded_override_dirs(),
                    progress_cb=self.export_panel.set_progress,
                    cancel_event=cancel_event,
                )

        self.export_panel.set_status("Server pack oluşturuluyor...")

        def on_success(p: Path) -> None:
            self._end_cancellable_task()
            self.export_panel.set_status(f"Server pack hazır: {p}")

        def on_error(message: str) -> None:
            self._end_cancellable_task()
            self._on_error(message)

        run_async(task, on_success=on_success, on_error=on_error)

    def do_run_sklauncher(self) -> None:
        if not self.current_pack:
            QMessageBox.warning(self, "Uyarı", "Önce bir pack seçin.")
            return
        if not self.settings.sklauncher_path:
            QMessageBox.warning(self, "Uyarı", "Önce Ayarlar'dan SKLauncher yolunu belirleyin.")
            return
        pack = self.current_pack
        source_dir = self._pick_source_dir()
        cancel_event = self._begin_cancellable_task()

        async def task() -> Path:
            instances_dir = instances_dir_for(self.settings.sklauncher_path)
            async with make_client() as client:
                return await prepare_instance(
                    pack,
                    source_dir=source_dir,
                    instances_dir=instances_dir,
                    cache_dir=self.settings.resolved_packs_dir() / ".cache" / pack.id,
                    client=client,
                    exclude_dirs=self.settings.excluded_override_dirs(),
                    progress_cb=self.export_panel.set_progress,
                    cancel_event=cancel_event,
                )

        def on_success(instance_dir: Path) -> None:
            self._end_cancellable_task()
            self.export_panel.set_status(f"Instance hazır: {instance_dir} — SKLauncher başlatılıyor")
            try:
                launch(self.settings.sklauncher_path)
            except Exception as exc:  # noqa: BLE001
                self._on_error(str(exc))

        def on_error(message: str) -> None:
            self._end_cancellable_task()
            self._on_error(message)

        self.export_panel.set_status("Instance hazırlanıyor...")
        run_async(task, on_success=on_success, on_error=on_error)

    # -- ortak ---------------------------------------------------------------

    def _on_error(self, message: str) -> None:
        QMessageBox.critical(self, "Hata", message)
        self.export_panel.set_status("Hata")
