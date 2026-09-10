"""Ana pencere.

Prism Launcher / CurseForge App'ten ilham alınan düzen: sol tarafta ince
bir pack listesi, sağda geniş bir "ana sahne" (pack detayı + eylem araç
çubuğu + mod tablosu). Mod ekleme ayrı bir pencerede (gui/mod_search_dialog.py)
— kalıcı bir yan panel olarak her zaman görünmüyor. İndirme ilerlemesi ve
durum mesajları alt durum çubuğunda (QStatusBar), ayrı bir panel değil.
"""

from __future__ import annotations

import threading
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QSplitter,
    QToolBar,
    QWidget,
)

from mcpack.config import Settings
from mcpack.downloader import make_client
from mcpack.export import CurseForgeExporter, MrpackExporter, PrismExporter, ServerPackExporter
from mcpack.gui.mod_search_dialog import ModSearchDialog
from mcpack.gui.new_pack_dialog import NewPackDialog
from mcpack.gui.recommended_mods_dialog import RecommendedModsDialog
from mcpack.gui.settings_dialog import SettingsDialog
from mcpack.gui.theme import set_active_theme, stylesheet_for
from mcpack.gui.widgets import PackDetailPanel, PackListPanel, run_async
from mcpack.launcher import instances_dir_for, launch, prepare_instance
from mcpack.models import EnvRequirement, Loader, ModSourceType, Pack
from mcpack.packs import PackManager
from mcpack.sources import CurseForgeClient, ModrinthClient, search_all
from mcpack.sources.base import ModDetail, ModVersion, SearchResult

_FORMAT_EXPORTERS = {
    "mrpack": MrpackExporter,
    "curseforge": CurseForgeExporter,
    "prism": PrismExporter,
}


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("MC Pack Manager")
        self.resize(1320, 820)

        self.settings = Settings.load()
        self._apply_theme()
        self.manager = PackManager(self.settings.resolved_packs_dir())
        self.current_pack: Pack | None = None
        self._cancel_event: threading.Event | None = None
        self._mod_search_dialog: ModSearchDialog | None = None

        self.pack_list = PackListPanel()
        self.pack_list.setMaximumWidth(320)
        self.pack_detail = PackDetailPanel()

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(self.pack_list)
        splitter.addWidget(self.pack_detail)
        splitter.setSizes([300, 1020])
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        self.setCentralWidget(splitter)

        self._build_toolbar()
        self._build_status_bar()
        self._wire_signals()
        self.reload_packs()

    # -- kurulum -----------------------------------------------------------

    def _apply_theme(self) -> None:
        set_active_theme(self.settings.theme)
        app = QApplication.instance()
        if app is not None:
            app.setStyleSheet(stylesheet_for(self.settings.theme))
        # Zaten çizilmiş rozet/ikon renkleri (QSS'in kapsamadığı, Python
        # tarafında elle stillenen widget'lar) yeniden render edilmeden
        # güncellenmez — pack_detail henüz kurulmadıysa (ilk açılış) atla.
        pack_detail = getattr(self, "pack_detail", None)
        if pack_detail is not None:
            pack_detail.show_pack(self.current_pack)
        pack_list = getattr(self, "pack_list", None)
        if pack_list is not None:
            pack_list.set_packs(self.manager.list_packs())

    def _build_toolbar(self) -> None:
        """Ayarlar eskiden sadece menü çubuğunda tek satırlık bir menüydü —
        kullanıcı isteğiyle her zaman görünen, belirgin bir araç çubuğu
        butonuna taşındı (Prism Launcher'daki gibi)."""
        toolbar = QToolBar("Ana")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        settings_button = QPushButton("⚙ Ayarlar")
        settings_button.clicked.connect(self.open_settings_dialog)
        toolbar.addWidget(settings_button)

    def _build_status_bar(self) -> None:
        """Export/server pack/SKLauncher ilerlemesi burada gösterilir — CurseForge/
        Prism'de de indirme ilerlemesi ayrı bir panel değil, alt durum çubuğundadır."""
        bar = self.statusBar()

        self.status_label = QLabel("Hazır")
        bar.addWidget(self.status_label, 1)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedWidth(180)
        self.progress_bar.setFixedHeight(16)
        self.progress_bar.setRange(0, 1)
        bar.addPermanentWidget(self.progress_bar)

        self.cancel_button = QPushButton("İptal")
        self.cancel_button.setObjectName("danger")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self.cancel_current_task)
        bar.addPermanentWidget(self.cancel_button)

    def _wire_signals(self) -> None:
        self.pack_list.new_pack_requested.connect(self.create_pack_dialog)
        self.pack_list.pack_selected.connect(self.select_pack)
        self.pack_detail.remove_mod_requested.connect(self.remove_mod)
        self.pack_detail.edit_env_requested.connect(self.edit_mod_env)
        self.pack_detail.add_mod_clicked.connect(self.open_mod_search_dialog)
        self.pack_detail.export_requested.connect(self.do_export)
        self.pack_detail.server_pack_requested.connect(self.do_server_pack)
        self.pack_detail.run_sklauncher_requested.connect(self.do_run_sklauncher)

    # -- durum çubuğu ---------------------------------------------------------

    def set_status(self, text: str) -> None:
        self.status_label.setText(text)

    def set_progress(self, done: int, total: int) -> None:
        self.progress_bar.setRange(0, max(total, 1))
        self.progress_bar.setValue(done)

    # -- ayarlar -------------------------------------------------------------

    def open_settings_dialog(self) -> None:
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() == SettingsDialog.DialogCode.Accepted:
            dialog.apply_to(self.settings)
            self.settings.save()
            self._apply_theme()  # tema değişmiş olabilir, yeniden başlatmadan uygula

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
        # Açık mod arama penceresi başka bir pack'e ait olabilir — kapat.
        if self._mod_search_dialog is not None:
            self._mod_search_dialog.close()
            self._mod_search_dialog = None

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

    def open_mod_search_dialog(self) -> None:
        if not self.current_pack:
            QMessageBox.warning(self, "Uyarı", "Önce bir pack seçin.")
            return
        if self.current_pack.loader == Loader.VANILLA:
            QMessageBox.information(self, "Bilgi", "Vanilla pack'lere mod eklenemez.")
            return

        if self._mod_search_dialog is not None:
            self._mod_search_dialog.raise_()
            self._mod_search_dialog.activateWindow()
            return

        dialog = ModSearchDialog(self.current_pack, self)
        dialog.search_panel.search_requested.connect(self.do_search)
        dialog.search_panel.add_mod_requested.connect(self.add_mod)
        dialog.finished.connect(self._on_mod_search_dialog_closed)
        dialog.search_panel.set_added_project_ids({m.project_id for m in self.current_pack.mods})
        self._mod_search_dialog = dialog
        dialog.show()

        # CurseForge/Modrinth App gibi: pencere açılır açılmaz, arama
        # yazılmasını beklemeden popüler modları listele (indirme sayısına
        # göre sıralı gelir — boş sorgu Modrinth/CurseForge'ta geçerlidir).
        self.do_search("", dialog.search_panel.source_combo.currentData(), 0)

    def _on_mod_search_dialog_closed(self) -> None:
        self._mod_search_dialog = None

    def do_search(self, query: str, source_name: str, offset: int = 0) -> None:
        if not self.current_pack:
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
                        offset=offset,
                        prefer_modrinth=self.settings.prefer_modrinth,
                    )
                finally:
                    await modrinth.aclose()
                    if curseforge:
                        await curseforge.aclose()

            source = self._make_source(source_name)
            try:
                return await source.search(
                    query, game_version=pack.minecraft, loader=pack.loader, offset=offset
                )
            finally:
                await source.aclose()

        self.set_status("Aranıyor..." if offset == 0 else "Daha fazla yükleniyor...")
        run_async(
            task,
            on_success=lambda results: self._on_search_done(results, append=offset > 0),
            on_error=self._on_error,
        )

    def _on_search_done(self, results: list[SearchResult], *, append: bool) -> None:
        if self._mod_search_dialog is not None:
            self._mod_search_dialog.search_panel.set_results(results, append=append)
        self.set_status("Hazır")

    def add_mod(self, result: SearchResult) -> None:
        if not self.current_pack:
            return
        pack = self.current_pack

        if pack.find_mod(result.project_id) is not None:
            # Aynı mod tekrar kurulmasın — kullanıcı zaten eklenmiş olanı
            # işaretli görüyor (bkz. SearchPanel.set_added_project_ids),
            # yine de tıklarsa burada sessizce engelleniyor.
            self.set_status(f"{result.title} zaten pack'te.")
            return

        async def task() -> list[tuple]:
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

                # Zorunlu olmayan (optional) bağımlılıklar otomatik eklenmez —
                # kullanıcıya "Önerilen Modlar" penceresinde seçtiriyoruz.
                optional_versions = await self.manager.resolve_optional_dependencies(
                    pack, source, versions[0]
                )
                suggestions = []
                for opt_version in optional_versions:
                    opt_detail = await source.get_project(opt_version.project_id)
                    suggestions.append((opt_version, opt_detail))
                return suggestions
            finally:
                await source.aclose()

        self.set_status(f"{result.title} ekleniyor...")
        run_async(task, on_success=self._on_mod_added, on_error=self._on_error)

    def _on_mod_added(self, suggestions: list[tuple[ModVersion, ModDetail]]) -> None:
        self.pack_detail.show_pack(self.current_pack)
        self.set_status("Mod eklendi")
        self._refresh_added_markers()

        if not suggestions or not self.current_pack:
            return
        dialog = RecommendedModsDialog(suggestions, self)
        if dialog.exec() == RecommendedModsDialog.DialogCode.Accepted:
            for version, detail in dialog.selected():
                self.manager.add_mod(self.current_pack, version, detail)
            self.pack_detail.show_pack(self.current_pack)
            self._refresh_added_markers()

    def _refresh_added_markers(self) -> None:
        """Mod Ekle penceresi açıksa, az önce eklenen mod(lar) oradaki
        listede de anında "Eklendi" olarak işaretlensin."""
        if self._mod_search_dialog is not None and self.current_pack is not None:
            self._mod_search_dialog.search_panel.set_added_project_ids(
                {m.project_id for m in self.current_pack.mods}
            )

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
        self.cancel_button.setEnabled(True)
        return event

    def _end_cancellable_task(self) -> None:
        self._cancel_event = None
        self.cancel_button.setEnabled(False)

    def cancel_current_task(self) -> None:
        if self._cancel_event is not None:
            self._cancel_event.set()
            self.set_status("İptal ediliyor...")

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
                    progress_cb=self.set_progress,
                    cancel_event=cancel_event,
                )

        self.set_status("Export ediliyor...")

        def on_success(p: Path) -> None:
            self._end_cancellable_task()
            self.set_status(f"Tamamlandı: {p}")

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
                    progress_cb=self.set_progress,
                    cancel_event=cancel_event,
                )

        self.set_status("Server pack oluşturuluyor...")

        def on_success(p: Path) -> None:
            self._end_cancellable_task()
            self.set_status(f"Server pack hazır: {p}")

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
                    progress_cb=self.set_progress,
                    cancel_event=cancel_event,
                )

        def on_success(instance_dir: Path) -> None:
            self._end_cancellable_task()
            self.set_status(f"Instance hazır: {instance_dir} — SKLauncher başlatılıyor")
            try:
                launch(self.settings.sklauncher_path)
            except Exception as exc:  # noqa: BLE001
                self._on_error(str(exc))

        def on_error(message: str) -> None:
            self._end_cancellable_task()
            self._on_error(message)

        self.set_status("Instance hazırlanıyor...")
        run_async(task, on_success=on_success, on_error=on_error)

    # -- ortak ---------------------------------------------------------------

    def _on_error(self, message: str) -> None:
        QMessageBox.critical(self, "Hata", message)
        self.set_status("Hata")
