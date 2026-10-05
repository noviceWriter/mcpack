"""Ana pencere.

Prism Launcher / CurseForge App'ten ilham alınan iki sayfalı düzen: bir
"Kütüphane" sayfası (bkz. library_page.py — tüm pack'lerin listesi) ve bir
pack'e tıklandığında açılan "Instance" sayfası (bkz. instance_page.py — o
pack'in modları/shader'ları/dünyaları + export/server/launcher eylemleri).
Önceden her ikisi de aynı anda, sol/sağ bölünmüş tek bir ekranda dururdu;
kullanıcı isteğiyle (MultiMC/Prism/CurseForge App'teki gibi) ayrı sayfalara
ayrıldı. Mod ekleme hâlâ ayrı bir pencerede (gui/mod_search_dialog.py) —
kalıcı bir yan panel olarak her zaman görünmüyor. İndirme ilerlemesi ve
durum mesajları alt durum çubuğunda (QStatusBar), ayrı bir panel değil.
"""

from __future__ import annotations

import re
import threading
import zipfile
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import Qt, QTimer, QUrl
from PySide6.QtGui import QCloseEvent, QDesktopServices
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
    QStackedWidget,
    QToolBar,
    QWidget,
)

from mcpack.config import Settings
from mcpack.downloader import make_client
from mcpack.export import CurseForgeExporter, MrpackExporter, PrismExporter, ServerPackExporter
from mcpack.export.server import SERVER_FILE_MISSING_NOTICE_NAME
from mcpack.gui.fork_pack_dialog import ForkPackDialog
from mcpack.gui.instance_page import InstancePage
from mcpack.gui.library_page import LibraryPage
from mcpack.gui.mod_search_dialog import ModSearchDialog
from mcpack.gui.new_pack_dialog import NewPackDialog
from mcpack.gui.recommended_mods_dialog import RecommendedModsDialog
from mcpack.gui.settings_dialog import SettingsDialog
from mcpack.gui.theme import set_active_theme, stylesheet_for
from mcpack.gui.widgets import run_async
from mcpack.launcher import instances_dir_for, launch, prepare_instance
from mcpack.models import ContentKind, EnvRequirement, ModSourceType, Pack
from mcpack.packs import PackManager
from mcpack.server_properties import merged_with_defaults, read_properties, write_properties
from mcpack.server_runtime import (
    ServerProcess,
    ServerProcessRegistry,
    ServerRuntimeError,
    build_launch_command,
    damage_command,
    ender_chest_query_command,
    feed_command,
    find_installer_jar,
    find_java,
    get_java_major_version,
    heal_command,
    hunger_command,
    inventory_query_command,
    kill_command,
    list_players_command,
    parse_item_list_response,
    parse_list_response,
    prepare_server,
    required_java_major,
    run_installer,
    server_state,
)
from mcpack.sources import CurseForgeClient, ModrinthClient, search_all
from mcpack.sources.base import ModDetail, ModVersion, SearchResult
from mcpack.sources.cheat_mods import find_meteor_download, find_wurst_download

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
        self._registry = ServerProcessRegistry()
        """pack.id -> ServerProcess eşlemesi — sayfa Kütüphane↔Instance
        arası geçince de süreç canlı kalsın diye burada tutulur (bkz.
        _refresh_server_section, closeEvent). Thread-safe: web paneli
        (bkz. do_toggle_web_panel) başlatılırsa AYNI nesneyi paylaşır,
        böylece Qt'den başlatılan bir sunucu web panelinde de "çalışıyor"
        görünür ve tam tersi."""
        self._web_panel_handle = None
        """webpanel.app.WebPanelHandle | None — çalışan embedded web
        sunucusu (varsa). Sadece kullanıcı "🌐 Web Paneli" butonuna
        basarsa oluşturulur (proje isteği: kullanıcı isterse kapatabilsin,
        varsayılan olarak bir ağ portu AÇILMAZ)."""
        self._player_poll_timer = QTimer(self)
        """Oyuncu paneli için periyodik /list sorgusu — SADECE şu an açık
        pack'in sunucusu çalışıyorken tetiklenir (bkz. _poll_players),
        gereksiz arkaplan iş olmasın diye (proje isteği: "programımız
        optimize olmalı")."""
        self._player_poll_timer.setInterval(4000)
        self._player_poll_timer.timeout.connect(self._poll_players)
        self._player_poll_timer.start()
        self._polling_players = False

        self.library_page = LibraryPage()
        self.instance_page = InstancePage()

        self.pages = QStackedWidget()
        self.pages.addWidget(self.library_page)
        self.pages.addWidget(self.instance_page)
        self.setCentralWidget(self.pages)

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
        # güncellenmez — sayfalar henüz kurulmadıysa (ilk açılış) atla.
        instance_page = getattr(self, "instance_page", None)
        if instance_page is not None:
            instance_page.show_pack(self.current_pack)
        library_page = getattr(self, "library_page", None)
        if library_page is not None:
            library_page.set_packs(self.manager.list_packs())

    def _build_toolbar(self) -> None:
        """Ayarlar eskiden sadece menü çubuğunda tek satırlık bir menüydü —
        kullanıcı isteğiyle her zaman görünen, belirgin bir araç çubuğu
        butonuna taşındı (Prism Launcher'daki gibi)."""
        toolbar = QToolBar("Ana")
        toolbar.setMovable(False)
        toolbar.setContentsMargins(6, 4, 10, 4)
        self.addToolBar(toolbar)

        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        toolbar.addWidget(spacer)

        self.web_panel_button = QPushButton("🌐 Web Paneli")
        self.web_panel_button.setToolTip(
            "Sunucu yönetimi için yerel bir web paneli başlatır (kullanıcı isterse kapatabilir)."
        )
        self.web_panel_button.clicked.connect(self.do_toggle_web_panel)
        toolbar.addWidget(self.web_panel_button)

        settings_button = QPushButton("⚙ Ayarlar")
        settings_button.clicked.connect(self.open_settings_dialog)
        toolbar.addWidget(settings_button)

        data_button = QPushButton("Veri Klasörünü Aç")
        data_button.clicked.connect(self.open_data_folder)
        toolbar.addWidget(data_button)

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
        self.library_page.new_pack_requested.connect(self.create_pack_dialog)
        self.library_page.delete_pack_requested.connect(self.delete_pack)
        self.library_page.pack_opened.connect(self.open_pack)

        self.instance_page.back_requested.connect(self.show_library)
        self.instance_page.export_requested.connect(self.do_export)
        self.instance_page.server_pack_requested.connect(self.do_server_pack)
        self.instance_page.run_sklauncher_requested.connect(self.do_run_sklauncher)
        self.instance_page.fork_requested.connect(self.do_fork_pack)

        mods = self.instance_page.mods_section
        mods.remove_mod_requested.connect(self.remove_mod)
        mods.edit_env_requested.connect(self.edit_mod_env)
        mods.add_mod_clicked.connect(lambda: self.open_mod_search_dialog(None))
        mods.check_dependencies_clicked.connect(self.check_dependencies)

        for kind, section in self.instance_page.content_sections.items():
            section.add_requested.connect(lambda k=kind: self.open_mod_search_dialog(k))
            section.remove_requested.connect(lambda pid, k=kind: self.remove_content_download(k, pid))

        world = self.instance_page.world_section
        world.add_local_requested.connect(self.browse_and_add_world)
        world.add_online_requested.connect(lambda: self.open_mod_search_dialog(ContentKind.WORLD))
        world.remove_requested.connect(self.remove_world)

        cheat_mods = self.instance_page.cheat_mods_section
        cheat_mods.add_requested.connect(self.add_cheat_mod)
        cheat_mods.remove_requested.connect(self.remove_cheat_mod)

        server = self.instance_page.server_section
        server.prepare_requested.connect(self.do_server_prepare)
        server.install_requested.connect(self.do_server_install)
        server.start_requested.connect(self.do_server_start)
        server.stop_requested.connect(self.do_server_stop)
        server.command_requested.connect(self.do_server_send_command)
        server.eula_accepted_requested.connect(self.do_server_eula_accept)
        server.settings_changed.connect(self.do_server_settings_changed)
        server.properties_saved.connect(self.do_server_properties_saved)

        players = server.player_panel
        players.refresh_requested.connect(self._poll_players)
        players.heal_requested.connect(self.do_player_heal)
        players.kill_requested.connect(self.do_player_kill)
        players.damage_requested.connect(self.do_player_damage)
        players.feed_requested.connect(self.do_player_feed)
        players.hunger_requested.connect(self.do_player_hunger)
        players.inventory_requested.connect(self.do_player_inventory)
        players.ender_chest_requested.connect(self.do_player_ender_chest)

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

    def do_toggle_web_panel(self) -> None:
        """"🌐 Web Paneli" butonu: kapalıysa başlatır + tarayıcıda açar,
        açıksa durdurur — kullanıcı isteği: "kullanıcı isterse web kısmını
        da kapatabilir". Embedded sunucu AYRI bir thread'de çalışır (bkz.
        webpanel.start_web_panel), Qt'nin kendi event loop'uyla çakışmaz;
        Qt ve web paneli AYNI self._registry'yi paylaşır (bkz. __init__)."""
        if self._web_panel_handle is not None:
            self._web_panel_handle.stop()
            self._web_panel_handle = None
            self.web_panel_button.setText("🌐 Web Paneli")
            self.set_status("Web paneli kapatıldı.")
            return

        from mcpack.webpanel import start_web_panel

        handle = start_web_panel(manager=self.manager, registry=self._registry, settings=self.settings)
        self._web_panel_handle = handle
        self.web_panel_button.setText("🌐 Web Panelini Kapat")
        if handle.network_exposed:
            self.set_status(
                f"Web paneli AĞA AÇIK: {handle.url} (aynı ağdaki cihazlar şifreyle erişebilir)"
            )
        else:
            self.set_status(f"Web paneli başlatıldı (sadece bu bilgisayar): {handle.url}")
        QDesktopServices.openUrl(QUrl(handle.url))

    # -- kütüphane / instance sayfaları arası gezinme -------------------------

    def reload_packs(self) -> None:
        self.library_page.set_packs(self.manager.list_packs())

    def open_data_folder(self) -> None:
        data_dir = self.settings.resolved_packs_dir()
        data_dir.mkdir(parents=True, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(data_dir)))

    def open_pack(self, pack_id: str) -> None:
        self.current_pack = self.manager.load(pack_id)
        self.instance_page.show_pack(self.current_pack)
        self._refresh_server_section()
        self.pages.setCurrentWidget(self.instance_page)

    def show_library(self) -> None:
        # Açık mod arama penceresi (varsa) artık görünmeyen bir instance'a
        # ait olur — kapat, aksi halde arka planda asılı kalır.
        if self._mod_search_dialog is not None:
            self._mod_search_dialog.close()
            self._mod_search_dialog = None
        self.current_pack = None
        self.reload_packs()  # ad/mod sayısı değişmiş olabilir
        self.pages.setCurrentWidget(self.library_page)

    def delete_pack(self, pack_id: str) -> None:
        pack = self.manager.load(pack_id)
        answer = QMessageBox.question(
            self,
            "Pack'i Sil",
            f"'{pack.name}' pack'i kalıcı olarak silinsin mi?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.manager.delete(pack_id)
        if self.current_pack is not None and self.current_pack.id == pack_id:
            self.show_library()
        else:
            self.reload_packs()

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

    def do_fork_pack(self) -> None:
        """Mevcut pack'i farklı bir Minecraft versiyonu için kopyalar ("fork"
        — kullanıcı isteği: "modun uygun sürümü yoksa kullanıcıya bilgi
        verir, modu eklemez"). Asıl çözümleme (her mod için ağdan yeni
        versiyon arama) PackManager.fork_pack'te; burada sadece diyalog +
        arka plan görevi + sonuç özeti var (add_mod'daki aynı iki aşamalı
        desen: diyalogdaki alanlar GUI thread'inde, ağ işi arka planda)."""
        if not self.current_pack:
            return
        pack = self.current_pack
        dialog = ForkPackDialog(pack, self)
        if dialog.exec() != ForkPackDialog.DialogCode.Accepted:
            return
        values = dialog.result_values()

        async def task() -> tuple[Pack, list[str]]:
            modrinth = ModrinthClient()
            curseforge = (
                CurseForgeClient(self.settings.curseforge_api_key)
                if self.settings.curseforge_api_key
                else None
            )
            try:
                async with make_client() as http_client:
                    return await self.manager.fork_pack(
                        pack,
                        name=values["name"],
                        minecraft=values["minecraft"],
                        loader_version=values["loader_version"],
                        modrinth=modrinth,
                        curseforge=curseforge,
                        http_client=http_client,
                    )
            finally:
                await modrinth.aclose()
                if curseforge:
                    await curseforge.aclose()

        def on_success(result: tuple[Pack, list[str]]) -> None:
            new_pack, failed = result
            self.reload_packs()
            self.set_status(f"'{new_pack.name}' oluşturuldu.")
            if failed:
                QMessageBox.warning(
                    self,
                    "Bazı Modlar Atlandı",
                    f"'{new_pack.name}' pack'i oluşturuldu, ama Minecraft {new_pack.minecraft} "
                    "için uyumlu bir versiyonu bulunamadığından şu modlar YENİ pack'e "
                    "EKLENMEDİ:\n\n"
                    + "\n".join(f"• {name}" for name in failed)
                    + "\n\nBunları elle eklemeyi veya alternatif bir mod aramayı deneyin.",
                )

        self.set_status(f"'{pack.name}' Minecraft {values['minecraft']}'e uyarlanıyor...")
        run_async(task, on_success=on_success, on_error=self._on_error)

    # -- sunucu yönetimi (başlat/durdur/konsol) ------------------------------

    def _refresh_server_section(self) -> None:
        """ServerSection'ın Pack'ten gelmeyen (dosya sistemi + canlı süreç)
        durumunu günceller — show_pack sadece pack.server'daki (bellek/dünya/
        EULA) ayarları yansıtır, burası "hazır mı/çalışıyor mu/konsolda ne
        var" kısmını tamamlar."""
        if self.current_pack is None:
            return
        pack = self.current_pack
        section = self.instance_page.server_section
        root = self.manager.server_root(pack)
        section.set_state(server_state(root))

        process = self._registry.get(pack.id)
        running = process is not None and process.is_running
        section.set_running(running)
        if process is not None:
            section.set_console_lines(list(process.buffer))
        else:
            section.clear_console()

        values = merged_with_defaults(read_properties(root / "server.properties"))
        section.set_properties(values)

    def do_server_prepare(self) -> None:
        if not self.current_pack:
            return
        pack = self.current_pack
        server_root = self.manager.server_root(pack)

        async def task() -> None:
            async with make_client() as client:
                await prepare_server(
                    pack,
                    server_root=server_root,
                    cache_dir=self.settings.resolved_packs_dir() / ".cache" / pack.id,
                    content_root=self.manager.content_root(pack),
                    client=client,
                    progress_cb=self.set_progress,
                )

        def on_success(_result: None) -> None:
            self.set_status("Sunucu hazırlandı.")
            self._refresh_server_section()

        def on_error(message: str) -> None:
            self._on_error(message)
            self._refresh_server_section()

        self.set_status("Sunucu hazırlanıyor (mod + sunucu dosyası indiriliyor)...")
        run_async(task, on_success=on_success, on_error=on_error)

    def do_server_install(self) -> None:
        """Forge/NeoForge: sadece bir installer var, önce bunu çalıştırmak
        gerekiyor (bkz. server_jar.py — kullanıcı isteği "sadece indirme"
        ile sınırlıydı, şimdi tam sunucu yönetimiyle birlikte bu adım da
        otomatikleşti)."""
        if not self.current_pack:
            return
        pack = self.current_pack
        server_root = self.manager.server_root(pack)
        installer = find_installer_jar(server_root)
        if installer is None:
            self._on_error("Kurulum dosyası bulunamadı — önce 'Hazırla'yı çalıştırın.")
            return
        java_path = find_java(self.settings.java_path)
        if java_path is None:
            self._on_error("Java bulunamadı. Ayarlar'dan Java yolunu belirtin ya da PATH'e (java) ekleyin.")
            return

        async def task() -> list[str]:
            return await run_installer(installer, server_root, java_path)

        def on_success(lines: list[str]) -> None:
            self.instance_page.server_section.set_console_lines(lines)
            self.set_status("Kurulum tamamlandı.")
            self._refresh_server_section()

        def on_error(message: str) -> None:
            self._on_error(message)
            self._refresh_server_section()

        self.set_status("Kuruluyor (java -jar ... --installServer)... bu biraz sürebilir.")
        run_async(task, on_success=on_success, on_error=on_error)

    def do_server_eula_accept(self) -> None:
        if not self.current_pack:
            return
        self.manager.update_server_config(self.current_pack, eula_accepted=True)

    def do_server_settings_changed(
        self, memory_mb: int, selected_world: object, use_optimized_flags: bool
    ) -> None:
        if not self.current_pack:
            return
        self.manager.update_server_config(
            self.current_pack,
            memory_mb=memory_mb,
            selected_world=selected_world,
            use_optimized_flags=use_optimized_flags,
        )

    def do_server_properties_saved(self, values: dict) -> None:
        if not self.current_pack:
            return
        properties_path = self.manager.server_root(self.current_pack) / "server.properties"
        # Var olan (sunucunun kendi ilk açılışta ürettiği, burada hiç
        # gösterilmeyen onlarca) anahtarı KORUYARAK sadece bilinen alanları
        # günceller — tam dosyayı sadece bu ~10 alanla EZMEK diğer tüm
        # ayarları (spawn-protection, resource-pack vb.) silerdi.
        current = read_properties(properties_path)
        current.update(values)
        write_properties(properties_path, current)
        self.set_status("server.properties kaydedildi.")

    def do_server_start(self) -> None:
        if not self.current_pack:
            return
        pack = self.current_pack
        if not pack.server.eula_accepted:
            # ServerSection zaten Başlat'tan önce onay penceresi gösterip
            # eula_accepted_requested'ı emit ediyor — bu sadece bir ek
            # güvence (proje genelindeki "UI'den bağımsız sert kontrol"
            # deseni, bkz. find_missing_dependencies).
            self._on_error("EULA kabul edilmeden sunucu başlatılamaz.")
            return

        server_root = self.manager.server_root(pack)
        if server_state(server_root) != "ready":
            self._on_error("Sunucu çalıştırmaya hazır değil — önce 'Hazırla' (ve gerekiyorsa 'Kur') yapın.")
            return

        java_path = find_java(self.settings.java_path)
        if java_path is None:
            self._on_error("Java bulunamadı. Ayarlar'dan Java yolunu belirtin ya da PATH'e (java) ekleyin.")
            return

        try:
            cmd = build_launch_command(
                server_root, pack.server.memory_mb, optimized=pack.server.use_optimized_flags
            )
        except ServerRuntimeError as exc:
            self._on_error(str(exc))
            return
        if cmd[0] == "java":
            cmd[0] = java_path

        # eula.txt SADECE burada, kullanıcı gerçekten kabul ettiği için yazılır.
        (server_root / "eula.txt").write_text("eula=true\n", encoding="utf-8")

        process = ServerProcess()
        # QueuedConnection AÇIKÇA belirtilir: output_line/process_exited arka
        # plan okuyucu thread'inden emit ediliyor, GUI widget'larına (konsol,
        # durum rozeti) sadece GUI thread'inde dokunulmalı.
        process.output_line.connect(
            self.instance_page.server_section.append_console_line, Qt.ConnectionType.QueuedConnection
        )
        process.process_exited.connect(
            lambda code, pid=pack.id: self._on_server_process_exited(pid, code),
            Qt.ConnectionType.QueuedConnection,
        )
        self._registry.set(pack.id, process)
        self.instance_page.server_section.clear_console()
        try:
            process.start(cmd, cwd=server_root)
        except ServerRuntimeError as exc:
            self._on_error(str(exc))
            self._registry.pop(pack.id)
            return

        self._refresh_server_section()
        self.set_status(f"'{pack.name}' sunucusu başlatılıyor...")

        # Java sürümü kontrolü SALT bilgilendirici (proje-amacı.md §6 ruhu:
        # engelleyici olması gerekmeyen kontroller sunucuyu başlatmayı
        # geciktirmemeli) — sunucu zaten başladı, bu paralel bir uyarı.
        required = required_java_major(pack.minecraft)

        async def check_java() -> int | None:
            return await get_java_major_version(java_path)

        def on_java_checked(major: int | None) -> None:
            if major is not None and major < required:
                QMessageBox.warning(
                    self, "Java Sürümü Uyarısı",
                    f"Tespit edilen Java sürümü: {major}. Minecraft {pack.minecraft} için "
                    f"Java {required}+ önerilir — sunucu açılışta hata verebilir.",
                )

        run_async(check_java, on_success=on_java_checked, on_error=lambda _m: None)

    def do_server_stop(self) -> None:
        if not self.current_pack:
            return
        process = self._registry.get(self.current_pack.id)
        if process is None or not process.is_running:
            return

        async def task() -> None:
            process.stop(timeout=30)

        def on_success(_result: None) -> None:
            self._refresh_server_section()

        self.set_status("Sunucu durduruluyor (stop komutu gönderildi)...")
        run_async(task, on_success=on_success, on_error=self._on_error)

    def do_server_send_command(self, text: str) -> None:
        if not self.current_pack:
            return
        process = self._registry.get(self.current_pack.id)
        if process is None:
            return
        try:
            process.send_command(text)
        except ServerRuntimeError as exc:
            self._on_error(str(exc))

    # -- oyuncu paneli (Aternos benzeri — tamamen vanilla komutlarla) --------

    def _get_running_process(self) -> ServerProcess | None:
        if not self.current_pack:
            return None
        process = self._registry.get(self.current_pack.id)
        return process if process is not None and process.is_running else None

    def _send_player_command(self, command: str) -> None:
        process = self._get_running_process()
        if process is None:
            return
        try:
            process.send_command(command)
        except ServerRuntimeError as exc:
            self._on_error(str(exc))

    def do_player_heal(self, player: str) -> None:
        self._send_player_command(heal_command(player))

    def do_player_kill(self, player: str) -> None:
        self._send_player_command(kill_command(player))

    def do_player_damage(self, player: str, amount: int) -> None:
        if not self.current_pack:
            return
        self._send_player_command(damage_command(player, amount, self.current_pack.minecraft))

    def do_player_feed(self, player: str) -> None:
        self._send_player_command(feed_command(player))

    def do_player_hunger(self, player: str, duration_s: int) -> None:
        self._send_player_command(hunger_command(player, duration_s))

    def do_player_inventory(self, player: str) -> None:
        process = self._get_running_process()
        if process is None:
            return

        async def task() -> str | None:
            return process.send_command_and_wait(
                inventory_query_command(player),
                match=re.compile(r"has the following entity data:"),
                timeout=5,
            )

        def on_success(line: str | None) -> None:
            if line is None:
                self._on_error(f"{player} için envanter yanıtı alınamadı (zaman aşımı).")
                return
            self.instance_page.server_section.player_panel.set_inventory(parse_item_list_response(line) or [])

        run_async(task, on_success=on_success, on_error=self._on_error)

    def do_player_ender_chest(self, player: str) -> None:
        process = self._get_running_process()
        if process is None:
            return

        async def task() -> str | None:
            return process.send_command_and_wait(
                ender_chest_query_command(player),
                match=re.compile(r"has the following entity data:"),
                timeout=5,
            )

        def on_success(line: str | None) -> None:
            if line is None:
                self._on_error(f"{player} için ender sandığı yanıtı alınamadı (zaman aşımı).")
                return
            self.instance_page.server_section.player_panel.set_ender_chest(parse_item_list_response(line) or [])

        run_async(task, on_success=on_success, on_error=self._on_error)

    def _poll_players(self) -> None:
        """Her 4 saniyede bir (bkz. __init__) — SADECE şu an açık pack'in
        sunucusu çalışıyorsa gerçekten bir şey yapar, aksi halde hemen
        çıkar (gereksiz arkaplan iş yok)."""
        if self._polling_players:
            return
        process = self._get_running_process()
        if process is None:
            return
        self._polling_players = True

        async def task() -> str | None:
            return process.send_command_and_wait(
                list_players_command(), match=re.compile(r"players online:"), timeout=3
            )

        def on_success(line: str | None) -> None:
            self._polling_players = False
            if line is None:
                return
            names = parse_list_response(line)
            if names is not None:
                self.instance_page.server_section.player_panel.set_players(names)

        def on_error(_message: str) -> None:
            self._polling_players = False

        run_async(task, on_success=on_success, on_error=on_error)

    def _on_server_process_exited(self, pack_id: str, returncode: int) -> None:
        self._registry.pop(pack_id)
        if self.current_pack is None or self.current_pack.id != pack_id:
            return
        self._refresh_server_section()
        if returncode == 0:
            self.set_status("Sunucu durdu.")
        else:
            self.set_status(f"Sunucu beklenmedik şekilde kapandı (çıkış kodu {returncode}).")

    def closeEvent(self, event: QCloseEvent) -> None:
        """Hiç kapatma engeli yoktu — çalışan bir sunucu varken pencere
        kapatılırsa süreç sessizce öksüz kalırdı (RAM/port tutmaya devam
        eder). Şimdi kullanıcıya SORUYOR, sessizce ne kill ediyor ne de
        öksüz bırakıyor."""
        running_ids = self._registry.all_running_ids()
        if not running_ids:
            if self._web_panel_handle is not None:
                self._web_panel_handle.stop()
            event.accept()
            return

        answer = QMessageBox.question(
            self, "Sunucular Çalışıyor",
            f"{len(running_ids)} sunucu hâlâ çalışıyor. Kapatmadan önce düzgünce durdurulsun mu?\n\n"
            "Hayır derseniz süreçler mcpack kapandıktan sonra da ÇALIŞMAYA DEVAM EDER "
            "(öksüz kalır) — kendiniz durdurmanız gerekir.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Cancel:
            event.ignore()
            return
        if answer == QMessageBox.StandardButton.Yes:
            for pid in running_ids:
                process = self._registry.get(pid)
                if process is not None:
                    process.stop(timeout=15)
        if self._web_panel_handle is not None:
            self._web_panel_handle.stop()
        event.accept()

    def remove_mod(self, project_id: str) -> None:
        if not self.current_pack:
            return
        self.manager.remove_mod(self.current_pack, project_id)
        self.instance_page.show_pack(self.current_pack)

    def browse_and_add_world(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Dünya Klasörü Seç")
        if not path:
            return
        self.add_world(path)

    def add_world(self, path: str) -> None:
        if self.current_pack is None:
            return
        try:
            entry = self.manager.add_content(self.current_pack, ContentKind.WORLD, Path(path))
        except ValueError as exc:
            self._on_error(str(exc))
            return
        self.instance_page.show_pack(self.current_pack)
        if self._mod_search_dialog is not None:
            self._mod_search_dialog.refresh_content(self.current_pack)
        self.set_status(f"{entry.name} eklendi.")

    def remove_world(self, name: str) -> None:
        if self.current_pack is None:
            return
        self.manager.remove_content(self.current_pack, ContentKind.WORLD, name)
        self.instance_page.show_pack(self.current_pack)
        if self._mod_search_dialog is not None:
            self._mod_search_dialog.refresh_content(self.current_pack)
        self.set_status(f"{name} kaldırıldı.")

    def remove_content_download(self, kind: ContentKind, project_id: str) -> None:
        if self.current_pack is None:
            return
        self.manager.remove_content_download(self.current_pack, kind, project_id)
        self.instance_page.show_pack(self.current_pack)
        if self._mod_search_dialog is not None:
            self._mod_search_dialog.refresh_content(self.current_pack)
        self.set_status("Kaldırıldı.")

    def add_cheat_mod(self, kind: str) -> None:
        """CheatModsSection'ın onay penceresinden ("Sorumluluk Reddi ve
        Onay") sonra çağrılır — kullanıcı zaten kabul etti, burada sadece
        pack'in Minecraft versiyonuna uygun build'i bulup (bkz.
        sources/cheat_mods.py) ekler. Uygun build yoksa (CheatModUnavailableError)
        normal hata popup'ıyla (self._on_error) gösterilir."""
        if not self.current_pack:
            return
        pack = self.current_pack
        source = ModSourceType.WURST if kind == "wurst" else ModSourceType.METEOR
        label = "Wurst Client" if kind == "wurst" else "Meteor Client"

        async def task() -> tuple[str, str]:
            async with make_client() as client:
                if kind == "wurst":
                    return await find_wurst_download(client, pack.minecraft)
                return await find_meteor_download(client, pack.minecraft)

        def on_success(result: tuple[str, str]) -> None:
            file_name, download_url = result
            self.manager.add_cheat_mod(pack, source, file_name, download_url)
            self.instance_page.show_pack(pack)
            self.set_status(f"{label} eklendi.")

        self.set_status(f"{label} için Minecraft {pack.minecraft} build'i aranıyor...")
        run_async(task, on_success=on_success, on_error=self._on_error)

    def remove_cheat_mod(self, project_id: str) -> None:
        if not self.current_pack:
            return
        self.manager.remove_mod(self.current_pack, project_id)
        self.instance_page.show_pack(self.current_pack)
        self.set_status("Kaldırıldı.")

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
            self, "İstemci Durumu", entry.file_name, env_values,
            current=env_values.index(entry.env.client.value), editable=False,
        )
        if not ok:
            return
        server, ok = QInputDialog.getItem(
            self, "Sunucu Durumu", entry.file_name, env_values,
            current=env_values.index(entry.env.server.value), editable=False,
        )
        if not ok:
            return

        self.manager.set_mod_env(
            pack, project_id, client=EnvRequirement(client), server=EnvRequirement(server)
        )
        self.instance_page.show_pack(pack)

    # -- mod arama / ekleme --------------------------------------------------

    def _make_source(self, source_name: str) -> ModrinthClient | CurseForgeClient:
        if source_name == ModSourceType.CURSEFORGE.value:
            return CurseForgeClient(self.settings.curseforge_api_key)
        return ModrinthClient()

    def open_mod_search_dialog(self, initial_kind: ContentKind | None) -> None:
        """Mod arama + shader/dünya/datapack/görüntü paketi ekleme penceresi.

        initial_kind: instance sayfasındaki hangi bölümün "+ Ekle" butonuna
        basıldıysa pencere doğrudan o sekmede açılır (None -> Modlar, ya da
        vanilla'da ilk içerik türü). Vanilla pack'lerde mod arama sekmesi
        olmaz (loader gerektirir) ama shader/dünya/datapack/görüntü paketi
        bir loader gerektirmediği için vanilla pack'ler de bu pencereyi
        açabilir (bkz. ModSearchDialog.is_vanilla)."""
        if not self.current_pack:
            QMessageBox.warning(self, "Uyarı", "Önce bir pack seçin.")
            return

        if self._mod_search_dialog is not None:
            self._mod_search_dialog.raise_()
            self._mod_search_dialog.activateWindow()
            return

        dialog = ModSearchDialog(self.current_pack, self, initial_kind=initial_kind)
        dialog.world_removed.connect(self.remove_world)
        dialog.content_removed.connect(self.remove_content_download)
        dialog.finished.connect(self._on_mod_search_dialog_closed)
        self._mod_search_dialog = dialog

        if dialog.search_panel is not None:
            dialog.search_panel.search_requested.connect(self.do_search)
            dialog.search_panel.add_mod_requested.connect(self.add_mod)
            dialog.search_panel.set_added_project_ids({m.project_id for m in self.current_pack.mods})

        for kind, panel in dialog.content_search_panels.items():
            panel.search_requested.connect(
                lambda q, s, o, k=kind: self.do_content_search(k, q, s, o)
            )
            panel.add_mod_requested.connect(
                lambda result, k=kind: self.add_content_download_result(k, result)
            )
            panel.set_added_project_ids({c.project_id for c in self.current_pack.content_downloads_of(kind)})

        dialog.world_search_panel.search_requested.connect(
            lambda q, s, o: self.do_content_search(ContentKind.WORLD, q, s, o)
        )
        dialog.world_search_panel.add_mod_requested.connect(self.add_world_download_result)

        dialog.show()

        if dialog.search_panel is not None:
            # CurseForge/Modrinth App gibi: pencere açılır açılmaz, arama
            # yazılmasını beklemeden popüler modları listele (indirme sayısına
            # göre sıralı gelir — boş sorgu Modrinth/CurseForge'ta geçerlidir).
            self.do_search("", dialog.search_panel.source_combo.currentData(), 0)
        for kind, panel in dialog.content_search_panels.items():
            self.do_content_search(kind, "", panel.source_combo.currentData(), 0)
        if self.settings.curseforge_api_key:
            # Dünya sadece CurseForge'ta aranabiliyor (bkz. SearchPanel
            # curseforge_only) — key yoksa açılışta otomatik arama tetiklenmez,
            # aksi halde pencere her açıldığında hata popup'ı çıkardı.
            self.do_content_search(
                ContentKind.WORLD, "", dialog.world_search_panel.source_combo.currentData(), 0
            )

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
        if self._mod_search_dialog is not None and self._mod_search_dialog.search_panel is not None:
            self._mod_search_dialog.search_panel.set_results(results, append=append)
        self.set_status("Hazır")

    def do_content_search(self, kind: ContentKind, query: str, source_name: str, offset: int = 0) -> None:
        """do_search'ün shader/datapack/görüntü paketi karşılığı — aynı akış,
        sadece content_kind ile Modrinth/CurseForge'a farklı bir proje türü
        (shader/resourcepack/datapack) sorgulanır, loader facet'i kullanılmaz."""
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
                        content_kind=kind,
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
                    query, game_version=pack.minecraft, content_kind=kind, offset=offset
                )
            finally:
                await source.aclose()

        self.set_status("Aranıyor..." if offset == 0 else "Daha fazla yükleniyor...")
        run_async(
            task,
            on_success=lambda results: self._on_content_search_done(kind, results, append=offset > 0),
            on_error=self._on_error,
        )

    def _on_content_search_done(self, kind: ContentKind, results: list[SearchResult], *, append: bool) -> None:
        if self._mod_search_dialog is not None:
            # Dünya'nın arama paneli content_search_panels'ta DEĞİL (o sözlük
            # sadece shader/resourcepack/datapack için) — ayrı bir attribute
            # (world_search_panel). Bu ayrımı unutup her zaman
            # content_search_panels'a bakmak dünya sonuçlarının sessizce
            # hiçbir yere yazılmamasına yol açıyordu (kullanıcı geri bildirimi:
            # "dünya oto listelenmiyor, arama da çalışmıyor" — istek gerçekten
            # ağa gidip başarıyla dönüyordu, sonuç sadece hiç gösterilmiyordu).
            panel = (
                self._mod_search_dialog.world_search_panel
                if kind == ContentKind.WORLD
                else self._mod_search_dialog.content_search_panels.get(kind)
            )
            if panel is not None:
                panel.set_results(results, append=append)
        self.set_status("Hazır")

    def add_mod(self, result: SearchResult) -> None:
        """Mod ekleme iki aşamalı: önce uyumlu sürümler ağdan çekilir (arka
        plan thread'i), sonra kullanıcı GUI thread'inde bir sürüm seçer
        (bkz. _pick_mod_version — kullanıcı isteği: "kullanıcı modun eski
        sürümlerini veya istenen sürümünü seçebilmeli", önceden hep en
        yenisi (versions[0]) sessizce seçiliyordu). Seçimden sonra asıl
        ekleme (+ bağımlılık çözümleme) ikinci bir arka plan görevinde olur."""
        if not self.current_pack:
            return
        pack = self.current_pack

        if pack.find_mod(result.project_id) is not None:
            # Aynı mod tekrar kurulmasın — kullanıcı zaten eklenmiş olanı
            # işaretli görüyor (bkz. SearchPanel.set_added_project_ids),
            # yine de tıklarsa burada sessizce engelleniyor.
            self.set_status(f"{result.title} zaten pack'te.")
            return

        async def fetch_task() -> tuple[ModDetail, list[ModVersion]]:
            source = self._make_source(result.source.value)
            try:
                detail = await source.get_project(result.project_id)
                versions = await source.get_versions(
                    result.project_id, game_version=pack.minecraft, loader=pack.loader
                )
                return detail, versions
            finally:
                await source.aclose()

        def on_fetched(data: tuple[ModDetail, list[ModVersion]]) -> None:
            detail, versions = data
            if not versions:
                self._on_error(f"{result.title}: {pack.minecraft}/{pack.loader.value} için uyumlu versiyon yok")
                return
            chosen = self._pick_mod_version(result.title, versions)
            if chosen is None:
                self.set_status("Vazgeçildi.")
                return
            self._add_mod_version(pack, chosen, detail, result.title)

        self.set_status(f"{result.title} için sürümler alınıyor...")
        run_async(fetch_task, on_success=on_fetched, on_error=self._on_error)

    def _pick_mod_version(self, title: str, versions: list[ModVersion]) -> ModVersion | None:
        """Tek uyumlu sürüm varsa sormadan onu kullanır (gereksiz tıklama
        istemez); birden fazla varsa kullanıcıya bir liste sunar — API zaten
        en yeniden eskiye sıralı döndürüyor, ilk seçenek "en yeni" olarak
        işaretlenir ama varsayılan seçili değildir kalır, kullanıcı bilerek
        seçer."""
        if len(versions) == 1:
            return versions[0]

        labels = []
        for i, v in enumerate(versions):
            mc_versions = ", ".join(v.game_versions) if v.game_versions else "?"
            suffix = " — en yeni" if i == 0 else ""
            labels.append(f"{v.name}  (MC {mc_versions}){suffix}")

        label, ok = QInputDialog.getItem(
            self, "Sürüm Seç", f"'{title}' için bir sürüm seçin:", labels, 0, False,
        )
        if not ok:
            return None
        return versions[labels.index(label)]

    def _add_mod_version(self, pack: Pack, version: ModVersion, detail: ModDetail, title: str) -> None:
        async def task() -> tuple[list[tuple], list[str]]:
            source = self._make_source(version.source.value)
            try:
                self.manager.add_mod(pack, version, detail)

                deps, failed_deps = await self.manager.resolve_dependencies(pack, source, version)
                for dep_version in deps:
                    dep_detail = await source.get_project(dep_version.project_id)
                    self.manager.add_mod(pack, dep_version, dep_detail)

                # Zorunlu olmayan (optional) bağımlılıklar otomatik eklenmez —
                # kullanıcıya "Önerilen Modlar" penceresinde seçtiriyoruz.
                optional_versions = await self.manager.resolve_optional_dependencies(
                    pack, source, version
                )
                suggestions = []
                for opt_version in optional_versions:
                    opt_detail = await source.get_project(opt_version.project_id)
                    suggestions.append((opt_version, opt_detail))
                return suggestions, failed_deps
            finally:
                await source.aclose()

        self.set_status(f"{title} ekleniyor...")
        run_async(task, on_success=self._on_mod_added, on_error=self._on_error)

    def _on_mod_added(self, result: tuple[list[tuple[ModVersion, ModDetail]], list[str]]) -> None:
        suggestions, failed_deps = result
        self.instance_page.show_pack(self.current_pack)
        self.set_status("Mod eklendi")
        self._refresh_added_markers()

        if failed_deps:
            # Sessizce atlamak yerine kullanıcıyı HEMEN uyar — bu tam olarak
            # "Prism'de açılışta hata verdi, zorunlu mod eksikmiş" senaryosunun
            # kök nedeniydi (bkz. resolve_dependencies).
            QMessageBox.warning(
                self,
                "Eksik Zorunlu Bağımlılık",
                "Bu mod için gerekli olan bazı bağımlılıklar otomatik eklenemedi "
                f"(pack'in {self.current_pack.minecraft}/{self.current_pack.loader.value} "
                "kombinasyonu için uyumlu bir versiyonları bulunamadı):\n\n"
                + "\n".join(f"• {name}" for name in failed_deps)
                + "\n\nBu mod muhtemelen bu bağımlılıklar olmadan çalışmayacaktır — "
                "elle eklemeyi deneyin ya da uyumlu bir Minecraft/loader versiyonu seçin.",
            )

        if not suggestions or not self.current_pack:
            return
        dialog = RecommendedModsDialog(suggestions, self)
        if dialog.exec() == RecommendedModsDialog.DialogCode.Accepted:
            for version, detail in dialog.selected():
                self.manager.add_mod(self.current_pack, version, detail)
            self.instance_page.show_pack(self.current_pack)
            self._refresh_added_markers()

    def add_content_download_result(self, kind: ContentKind, result: SearchResult) -> None:
        """add_mod'un shader/datapack/görüntü paketi karşılığı — bağımlılık
        çözümlemesi/env yok, sadece seçilen versiyon pack.content_downloads'a eklenir
        (gerçek dosya export sırasında indirilir, bkz. export/base.py)."""
        if not self.current_pack:
            return
        pack = self.current_pack

        if pack.find_content_download(kind, result.project_id) is not None:
            self.set_status(f"{result.title} zaten pack'te.")
            return

        async def task() -> None:
            source = self._make_source(result.source.value)
            try:
                detail = await source.get_project(result.project_id)
                versions = await source.get_versions(result.project_id, game_version=pack.minecraft)
                if not versions:
                    raise RuntimeError(f"{result.title}: {pack.minecraft} için uyumlu versiyon yok")
                self.manager.add_content_download(pack, kind, versions[0], detail)
            finally:
                await source.aclose()

        self.set_status(f"{result.title} ekleniyor...")
        run_async(task, on_success=lambda _: self._on_content_download_added(kind), on_error=self._on_error)

    def add_world_download_result(self, result: SearchResult) -> None:
        if not self.current_pack:
            return
        pack = self.current_pack

        async def task() -> None:
            source = self._make_source(result.source.value)
            try:
                detail = await source.get_project(result.project_id)
                versions = await source.get_versions(result.project_id, game_version=pack.minecraft)
                if not versions:
                    raise RuntimeError(f"{result.title}: {pack.minecraft} için uyumlu versiyon yok")
                async with make_client() as client:
                    await self.manager.add_world_from_download(
                        pack, versions[0], client, detail=detail
                    )
            finally:
                await source.aclose()

        self.set_status(f"{result.title} indiriliyor...")
        run_async(task, on_success=self._on_world_download_added, on_error=self._on_error)

    def _on_world_download_added(self) -> None:
        self.instance_page.show_pack(self.current_pack)
        if self._mod_search_dialog is not None and self.current_pack is not None:
            self._mod_search_dialog.refresh_content(self.current_pack)
        self.set_status("Dünya eklendi")

    def _on_content_download_added(self, kind: ContentKind) -> None:
        self.instance_page.show_pack(self.current_pack)
        self.set_status("Eklendi")
        self._refresh_added_markers()

    def _refresh_added_markers(self) -> None:
        """Mod Ekle penceresi açıksa, az önce eklenen mod/shader/datapack/
        görüntü paketi oradaki listede de anında "Eklendi" olarak işaretlensin
        ve "Eklenmiş X'ler" listesine düşsün (bkz. ModSearchDialog.refresh_content)."""
        if self._mod_search_dialog is None or self.current_pack is None:
            return
        if self._mod_search_dialog.search_panel is not None:
            self._mod_search_dialog.search_panel.set_added_project_ids(
                {m.project_id for m in self.current_pack.mods}
            )
        self._mod_search_dialog.refresh_content(self.current_pack)

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

    async def _describe_missing_dependencies(self, pack: Pack, missing: list[tuple[str, str]]) -> list[str]:
        """Ham project_id yerine gerçek mod adını göstermek için (ör. "Prism",
        "Architectury API" — "eXts2L7r" gibi bir ID değil) eksik
        bağımlılıkların adlarını ağdan çözer. Kullanıcı geri bildirimi:
        "Zorunlu mod listelerinde mod ID değil mod adı görünmeli" — bu artık
        hem mod ekleme anında (bkz. resolve_dependencies) hem de burada
        (elle kontrol VE export/server pack/SKLauncher öncesi sert kapı)
        tutarlı şekilde uygulanıyor."""
        by_mod: dict[str, list[str]] = {}
        for mod_name, dep_id in missing:
            by_mod.setdefault(mod_name, []).append(dep_id)

        lines = []
        for mod_name, dep_ids in by_mod.items():
            parent = next((m for m in pack.mods if (m.name or m.file_name) == mod_name), None)
            source_name = parent.source.value if parent else ModSourceType.MODRINTH.value
            source = self._make_source(source_name)
            try:
                dep_labels = []
                for dep_id in dep_ids:
                    try:
                        detail = await source.get_project(dep_id)
                        dep_labels.append(detail.title)
                    except Exception:  # noqa: BLE001 - isim alınamazsa id ile devam
                        dep_labels.append(dep_id)
                lines.append(f"• {mod_name}: {', '.join(dep_labels)}")
            finally:
                await source.aclose()
        return lines

    def _run_if_dependencies_ok(self, pack: Pack, on_proceed: Callable[[], None]) -> None:
        """Kullanıcı isteği: "mod kontrol kısmını sert bir şekilde kontrol
        sistemi ekleyelim" — bir pack'i Prism/CurseForge/SKLauncher'a
        aktarmadan önce, pack'teki modların kayıtlı zorunlu bağımlılıklarının
        (bkz. ModEntry.dependencies, mod eklenirken kaydedilir) hâlâ pack'te
        olup olmadığını kontrol eder. Eksik bir zorunlu bağımlılıkla export
        edilen pack genelde oyunun açılışta çökmesiyle sonuçlanır (kullanıcı
        geri bildirimi: "Prism'de açılışta hata verdi, zorunlu modlar
        yüklenmemiş" — kök neden: resolve_dependencies bir bağımlılığın
        uyumlu versiyonunu bulamayınca sessizce atlıyordu, bkz. o fonksiyonun
        güncellenmiş docstring'i). Sorun yoksa on_proceed() hemen çağrılır
        (gecikme yok); varsa isimler ağdan çözülüp durdurulur, kullanıcı
        bilerek "Yine de Devam Et" derse on_proceed() çağrılır."""
        missing = self.manager.find_missing_dependencies(pack)
        if not missing:
            on_proceed()
            return

        async def task() -> list[str]:
            return await self._describe_missing_dependencies(pack, missing)

        def on_success(lines: list[str]) -> None:
            self.set_status("Hazır")
            answer = QMessageBox.warning(
                self,
                "Eksik Zorunlu Bağımlılıklar",
                "Bu pack'teki bazı modların gerektirdiği zorunlu bağımlılıklar "
                "pack'te yok. Bu haliyle export edilirse oyun büyük ihtimalle "
                "açılışta çökecektir:\n\n"
                + "\n".join(lines)
                + "\n\nYine de devam etmek istiyor musunuz?",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer == QMessageBox.StandardButton.Yes:
                on_proceed()

        self.set_status("Bağımlılıklar kontrol ediliyor...")
        run_async(task, on_success=on_success, on_error=self._on_error)

    def check_dependencies(self) -> None:
        """Modlar bölümündeki "Bağımlılıkları Kontrol Et" butonu — export
        beklemeden, istediği zaman elle kontrol edebilsin diye."""
        if not self.current_pack:
            QMessageBox.warning(self, "Uyarı", "Önce bir pack seçin.")
            return
        pack = self.current_pack

        missing = self.manager.find_missing_dependencies(pack)
        if not missing:
            QMessageBox.information(
                self, "Bağımlılık Kontrolü",
                "Sorun yok — pack'teki hiçbir modun bilinen, eksik bir zorunlu bağımlılığı yok.",
            )
            return

        async def task() -> list[str]:
            return await self._describe_missing_dependencies(pack, missing)

        def on_success(lines: list[str]) -> None:
            self.set_status("Hazır")
            QMessageBox.warning(
                self, "Eksik Zorunlu Bağımlılıklar",
                "Şu modların gerektirdiği zorunlu bağımlılıklar pack'te yok — "
                "bu haliyle export edilirse oyun büyük ihtimalle açılışta çökecektir:\n\n"
                + "\n".join(lines),
            )

        self.set_status("Bağımlılıklar kontrol ediliyor...")
        run_async(task, on_success=on_success, on_error=self._on_error)

    def do_export(self, format_key: str) -> None:
        if not self.current_pack:
            QMessageBox.warning(self, "Uyarı", "Önce bir pack seçin.")
            return
        pack = self.current_pack

        def proceed() -> None:
            exporter_cls = _FORMAT_EXPORTERS[format_key]

            output_path, _ = QFileDialog.getSaveFileName(
                self, "Dışa Aktar", f"{pack.name}{exporter_cls.file_extension}", f"*{exporter_cls.file_extension}"
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
                        content_root=self.manager.content_root(pack),
                        client=client,
                        exclude_dirs=self.settings.excluded_override_dirs(),
                        progress_cb=self.set_progress,
                        cancel_event=cancel_event,
                    )

            def on_success(p: Path) -> None:
                self._end_cancellable_task()
                self.set_status(f"Tamamlandı: {p}")

            def on_error(message: str) -> None:
                self._end_cancellable_task()
                self._on_error(message)

            self.set_status("Dışa aktarılıyor...")
            run_async(task, on_success=on_success, on_error=on_error)

        self._run_if_dependencies_ok(pack, proceed)

    def _ask_server_pack_world(self, pack: Pack) -> str | None:
        """Pack'e yüklenmiş dünya varsa kullanıcıya sorar; evet derse yüklü
        dünyalardan TEK birini seçtirir ve onaylatır. Seçilen dünya export'ta
        "world/" adıyla (orijinal adı değil) pakete eklenir — sunucular tek
        bir dünya klasörü bekler. Dünya yoksa ya da kullanıcı istemezse None
        döner (dünya dahil edilmez)."""
        worlds = pack.content_of(ContentKind.WORLD)
        if not worlds:
            return None

        answer = QMessageBox.question(
            self,
            "Dünya Ekle",
            "Bu pack'e yüklenmiş dünya var. Sunucu paketine bir dünya eklemek ister misiniz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return None

        names = [w.name for w in worlds]
        if len(names) == 1:
            name = names[0]
        else:
            name, ok = QInputDialog.getItem(
                self, "Dünya Seç", "Sunucu paketine eklenecek dünyayı seçin:", names, 0, False
            )
            if not ok or not name:
                return None

        confirm = QMessageBox.question(
            self,
            "Dünyayı Onayla",
            f"'{name}' dünyası pakette \"world\" adıyla dışa aktarılacak. Onaylıyor musunuz?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        return name if confirm == QMessageBox.StandardButton.Yes else None

    def do_server_pack(self) -> None:
        if not self.current_pack:
            QMessageBox.warning(self, "Uyarı", "Önce bir pack seçin.")
            return
        pack = self.current_pack

        def proceed() -> None:
            selected_world = self._ask_server_pack_world(pack)

            output_path, _ = QFileDialog.getSaveFileName(self, "Sunucu Paketi Oluştur", f"{pack.name}-server.zip", "*.zip")
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
                        content_root=self.manager.content_root(pack),
                        client=client,
                        exclude_dirs=self.settings.excluded_override_dirs(),
                        progress_cb=self.set_progress,
                        cancel_event=cancel_event,
                        selected_world=selected_world,
                    )

            def on_success(p: Path) -> None:
                self._end_cancellable_task()
                self.set_status(f"Sunucu paketi hazır: {p}")
                self._warn_if_server_file_missing(p)

            def on_error(message: str) -> None:
                self._end_cancellable_task()
                self._on_error(message)

            self.set_status("Sunucu paketi oluşturuluyor...")
            run_async(task, on_success=on_success, on_error=on_error)

        self._run_if_dependencies_ok(pack, proceed)

    def _warn_if_server_file_missing(self, server_pack_path: Path) -> None:
        """Kullanıcı isteği: "server dosyasını biz indirtebilir miyiz" —
        ServerPackExporter artık bunu otomatik yapıyor, ama bu MC/loader
        kombinasyonu için resmi bir dosya bulunamadıysa (ağ hatası ya da
        gerçekten yayınlanmamışsa) ServerPackExporter export'u BOZMADAN bir
        not dosyası ekliyor (bkz. export/server.py). Burada export BİTTİKTEN
        sonra zip'e tekrar bakıp bu durumu kullanıcıya HEMEN göstererek
        "neden sunucu çalışmıyor" sorusunu önceden yanıtlıyoruz."""
        try:
            with zipfile.ZipFile(server_pack_path) as zf:
                has_notice = SERVER_FILE_MISSING_NOTICE_NAME in zf.namelist()
        except OSError:
            return
        if not has_notice:
            return
        QMessageBox.warning(
            self,
            "Sunucu Dosyası Otomatik İndirilemedi",
            "Sunucu paketi oluşturuldu, ama bu Minecraft/loader kombinasyonu için "
            "resmi sunucu dosyası otomatik bulunup indirilemedi (ağ hatası ya da "
            "bu versiyon için resmi bir dosya yayınlanmamış olabilir).\n\n"
            f"Zip içindeki '{SERVER_FILE_MISSING_NOTICE_NAME}' dosyasında detay ve "
            "elle indirme talimatı var.",
        )

    def do_run_sklauncher(self) -> None:
        if not self.current_pack:
            QMessageBox.warning(self, "Uyarı", "Önce bir pack seçin.")
            return
        if not self.settings.sklauncher_path:
            QMessageBox.warning(self, "Uyarı", "Önce Ayarlar'dan SKLauncher yolunu belirleyin.")
            return
        pack = self.current_pack

        def proceed() -> None:
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
                        content_root=self.manager.content_root(pack),
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

        self._run_if_dependencies_ok(pack, proceed)

    # -- ortak ---------------------------------------------------------------

    def _on_error(self, message: str) -> None:
        QMessageBox.critical(self, "Hata", message)
        self.set_status("Hata")
