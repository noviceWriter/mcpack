"""Uygulama denetleyicisi: arayüzün TÜM iş mantığı burada.

Eski main_window.py 1585 satırlık tek bir sınıftı — widget kurulumu, ağ
işleri, sunucu süreci yönetimi ve QMessageBox'lar iç içeydi. Artık:

- `AppController` (bu dosya): ayarlar, PackManager, sunucu süreç kaydı,
  görev yöneticisi, web paneli; her işlem bir `TaskManager` görevi olarak
  çalışır (izlenebilir, loglanır, iptal edilebilir) ve sonuçlar sinyallerle
  ya da GUI thread'inde çağrılan callback'lerle döner.
- Sayfalar (gui/pages/*): sadece görünüm + kullanıcı etkileşimi (diyalog,
  onay). Hiçbiri doğrudan ağa/dosya sistemine/sürece dokunmaz.

Bu dosyada hiçbir widget/QMessageBox YOKTUR.
"""

from __future__ import annotations

import re
import shutil
import time
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import QObject, Qt, Signal, Slot

from mcpack.config import Settings
from mcpack.downloader import make_client
from mcpack.export import CurseForgeExporter, MrpackExporter, PrismExporter, ServerPackExporter
from mcpack.export.server import SERVER_FILE_MISSING_NOTICE_NAME
from mcpack.gui.tasks import Task, TaskContext, TaskManager
from mcpack.i18n import t
from mcpack.launcher import instances_dir_for, launch, prepare_instance
from mcpack.logging_setup import get_logger, record_exception
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
from mcpack.sources.cheat_mods import CheatModFile, download_cheat_mod

log = get_logger(__name__)

EXPORTERS = {
    "mrpack": MrpackExporter,
    "curseforge": CurseForgeExporter,
    "prism": PrismExporter,
}
EXPORT_LABELS = {
    "mrpack": "Modrinth (.mrpack)",
    "curseforge": "CurseForge (.zip)",
    "prism": "Prism / MultiMC (.zip)",
}
CHEAT_SOURCES = (ModSourceType.WURST, ModSourceType.METEOR)
PLAYER_NAME_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")

Callback = Callable[[Any], None] | None
ErrorCallback = Callable[[str], None] | None


class AppController(QObject):
    packs_changed = Signal()
    pack_updated = Signal(str)
    """pack_id — o pack'in JSON'u değişti (mod eklendi/kaldırıldı/ayar...)."""
    server_changed = Signal(str)
    """pack_id — sunucunun durumu (hazır/çalışıyor) değişti."""
    console_line = Signal(str, str)
    console_reset = Signal(str, list)
    players_updated = Signal(str, list)
    notify = Signal(str, str)
    """(level, message) — level: info/success/warning/error. Ana pencere toast gösterir."""
    status = Signal(str)
    web_panel_changed = Signal(bool, str)
    settings_changed = Signal()
    navigate = Signal(str, str)
    """(sayfa, pack_id) — komut paleti vb. yerlerden gezinme isteği."""

    _line_from_thread = Signal(str, str)
    _exit_from_thread = Signal(str, int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.settings = Settings.load()
        self.manager = PackManager(self.settings.resolved_packs_dir())
        self.tasks = TaskManager(self)
        self.registry = ServerProcessRegistry()
        self.server_started_at: dict[str, float] = {}
        self._web_panel = None
        self._polling: set[str] = set()
        self._pack_cache: dict[str, Pack] = {}
        """Kimlik haritası: her pack id için TEK bir canlı Pack nesnesi.
        Arka plan görevi (ör. mod ekleme) eski bir kopyayı kaydedip
        kullanıcının bu arada yaptığı değişikliği ezmesin diye tüm sayfalar
        ve görevler aynı nesne üzerinde çalışır."""
        q = Qt.ConnectionType.QueuedConnection
        self._line_from_thread.connect(self._on_line_from_thread, q)
        self._exit_from_thread.connect(self._on_exit_from_thread, q)

    # ------------------------------------------------------------------ yardımcı

    def _error(self, message: str) -> None:
        self.notify.emit("error", message)

    def _run(
        self,
        title: str,
        factory: Callable[[TaskContext], Any],
        *,
        on_success: Callback = None,
        on_error: ErrorCallback = None,
        on_finally: Callable[[], None] | None = None,
        cancellable: bool = False,
        silent: bool = False,
        category: str = "general",
        notify_error: bool = True,
        owner: QObject | None = None,
    ) -> Task:
        def _on_error(message: str) -> None:
            if notify_error:
                self._error(message)
            if on_error is not None:
                on_error(message)

        return self.tasks.run(
            title, factory, on_success=on_success, on_error=_on_error, on_finally=on_finally,
            cancellable=cancellable, silent=silent, category=category, owner=owner,
        )

    def cache_dir(self, pack: Pack) -> Path:
        return self.settings.resolved_packs_dir() / ".cache" / pack.id

    def make_source(self, source_name: str) -> ModrinthClient | CurseForgeClient:
        if source_name == ModSourceType.CURSEFORGE.value:
            return CurseForgeClient(self.settings.curseforge_api_key)
        return ModrinthClient()

    def has_curseforge(self) -> bool:
        return bool(self.settings.curseforge_api_key)

    # ------------------------------------------------------------------ ayarlar

    def apply_settings(self, new: Settings) -> list[str]:
        """Yeni ayarları kaydeder; yeniden başlatma gerektiren değişikliklerin
        adlarını döner (dil)."""
        old = self.settings
        needs_restart = []
        if new.language != old.language:
            needs_restart.append("language")
        packs_dir_changed = new.resolved_packs_dir() != old.resolved_packs_dir()
        self.settings = new
        new.save()
        log.info("Ayarlar kaydedildi%s", " (pack klasörü değişti)" if packs_dir_changed else "")
        if packs_dir_changed:
            self.manager = PackManager(new.resolved_packs_dir())
            self._pack_cache.clear()
            self.packs_changed.emit()
        from mcpack.logging_setup import set_debug

        if new.debug_mode != old.debug_mode:
            set_debug(new.debug_mode)
        self.settings_changed.emit()
        return needs_restart

    # ------------------------------------------------------------------ pack'ler

    def list_packs(self) -> list[Pack]:
        fresh = self.manager.list_packs()
        result = []
        for pack in fresh:
            cached = self._pack_cache.setdefault(pack.id, pack)
            result.append(cached)
        ids = {p.id for p in fresh}
        for stale in [k for k in self._pack_cache if k not in ids]:
            del self._pack_cache[stale]
        return result

    def load_pack(self, pack_id: str) -> Pack | None:
        cached = self._pack_cache.get(pack_id)
        if cached is not None:
            return cached
        try:
            pack = self.manager.load(pack_id)
        except Exception as exc:  # noqa: BLE001
            record_exception(exc, origin=f"load_pack:{pack_id}", logger=log)
            self._error(t("ctl.pack_load_failed", error=exc))
            return None
        self._pack_cache[pack_id] = pack
        return pack

    def reload_pack_from_disk(self, pack_id: str) -> Pack | None:
        self._pack_cache.pop(pack_id, None)
        pack = self.load_pack(pack_id)
        if pack is not None:
            self.pack_updated.emit(pack_id)
        return pack

    def create_pack(self, values: dict) -> Pack:
        pack = self.manager.create_pack(**values)
        self._pack_cache[pack.id] = pack
        self.packs_changed.emit()
        self.notify.emit("success", t("ctl.pack_created", name=pack.name))
        return pack

    def update_pack_meta(self, pack: Pack, *, name: str, version: str, author: str, summary: str) -> None:
        pack.name, pack.version, pack.author, pack.summary = name, version, author, summary
        self.manager.save(pack)
        log.info("Pack bilgileri güncellendi: %s", pack.name)
        self.pack_updated.emit(pack.id)
        self.packs_changed.emit()

    def duplicate_pack(self, pack: Pack) -> Pack:
        copy = pack.model_copy(deep=True)
        import uuid

        copy.id = str(uuid.uuid4())
        copy.name = t("ctl.copy_name", name=pack.name)
        copy.server = type(pack.server)(memory_mb=pack.server.memory_mb, use_optimized_flags=pack.server.use_optimized_flags)
        src_content = self.manager.content_root(pack)
        if src_content.exists():
            shutil.copytree(src_content, self.manager.content_root(copy), dirs_exist_ok=True)
        self.manager.save(copy)
        self._pack_cache[copy.id] = copy
        log.info("Pack kopyalandı: %s -> %s", pack.name, copy.name)
        self.packs_changed.emit()
        self.notify.emit("success", t("ctl.pack_created", name=copy.name))
        return copy

    def delete_pack(self, pack_id: str) -> bool:
        if self.registry.is_running(pack_id):
            self._error(t("ctl.delete_running_server"))
            return False
        self.manager.delete(pack_id)
        self.registry.pop(pack_id)
        self._pack_cache.pop(pack_id, None)
        self.packs_changed.emit()
        self.notify.emit("info", t("ctl.pack_deleted"))
        return True

    def fork_pack(self, pack: Pack, values: dict, on_done: Callable[[Pack, list[str]], None]) -> None:
        async def task(ctx: TaskContext) -> tuple[Pack, list[str]]:
            modrinth = ModrinthClient()
            curseforge = CurseForgeClient(self.settings.curseforge_api_key) if self.has_curseforge() else None
            try:
                async with make_client() as http_client:
                    return await self.manager.fork_pack(
                        pack, name=values["name"], minecraft=values["minecraft"],
                        loader_version=values["loader_version"], modrinth=modrinth,
                        curseforge=curseforge, http_client=http_client,
                    )
            finally:
                await modrinth.aclose()
                if curseforge:
                    await curseforge.aclose()

        def success(result: tuple[Pack, list[str]]) -> None:
            new_pack, failed = result
            self._pack_cache[new_pack.id] = new_pack
            self.packs_changed.emit()
            self.notify.emit("success", t("ctl.pack_created", name=new_pack.name))
            on_done(new_pack, failed)

        self._run(t("ctl.task.fork", name=pack.name, minecraft=values["minecraft"]), task, on_success=success, category="pack")

    # ------------------------------------------------------------------ arama / ekleme

    def search(
        self,
        pack: Pack,
        kind: ContentKind | None,
        query: str,
        source_name: str,
        offset: int,
        on_done: Callable[[list[SearchResult]], None],
        on_error: ErrorCallback = None,
    ) -> Task:
        loader = pack.loader if kind is None else None

        async def task(ctx: TaskContext) -> list[SearchResult]:
            if source_name == "both":
                modrinth = ModrinthClient()
                curseforge = CurseForgeClient(self.settings.curseforge_api_key) if self.has_curseforge() else None
                try:
                    return await search_all(
                        query, modrinth=modrinth, curseforge=curseforge, game_version=pack.minecraft,
                        loader=loader, content_kind=kind, offset=offset,
                        prefer_modrinth=self.settings.prefer_modrinth,
                    )
                finally:
                    await modrinth.aclose()
                    if curseforge:
                        await curseforge.aclose()
            source = self.make_source(source_name)
            try:
                return await source.search(
                    query, game_version=pack.minecraft, loader=loader, content_kind=kind, offset=offset
                )
            finally:
                await source.aclose()

        title = t("ctl.task.search", query=query or "★", source=source_name)
        return self._run(title, task, on_success=on_done, on_error=on_error, silent=True, category="search")

    def fetch_versions(
        self,
        pack: Pack,
        result: SearchResult,
        kind: ContentKind | None,
        on_done: Callable[[ModDetail, list[ModVersion]], None],
    ) -> None:
        async def task(ctx: TaskContext) -> tuple[ModDetail, list[ModVersion]]:
            source = self.make_source(result.source.value)
            try:
                detail = await source.get_project(result.project_id)
                versions = await source.get_versions(
                    result.project_id, game_version=pack.minecraft, loader=pack.loader if kind is None else None
                )
                return detail, versions
            finally:
                await source.aclose()

        self._run(
            t("ctl.task.fetch_versions", title=result.title), task,
            on_success=lambda data: on_done(*data), category="mods",
        )

    def add_mod_version(
        self,
        pack: Pack,
        version: ModVersion,
        detail: ModDetail,
        on_done: Callable[[list[tuple[ModVersion, ModDetail]], list[str]], None] | None = None,
    ) -> None:
        """Modu ekler + zorunlu bağımlılıkları çözer/ekler + opsiyonel
        önerileri toplar (önceki akışla birebir aynı)."""
        async def task(ctx: TaskContext):
            source = self.make_source(version.source.value)
            try:
                ctx.message(detail.title)
                self.manager.add_mod(pack, version, detail)
                deps, failed = await self.manager.resolve_dependencies(pack, source, version)
                for i, dep_version in enumerate(deps, start=1):
                    ctx.progress(i, len(deps) + 1)
                    dep_detail = await source.get_project(dep_version.project_id)
                    self.manager.add_mod(pack, dep_version, dep_detail)
                ctx.progress(len(deps) + 1, len(deps) + 1)
                optional = await self.manager.resolve_optional_dependencies(pack, source, version)
                suggestions = []
                for opt_version in optional:
                    suggestions.append((opt_version, await source.get_project(opt_version.project_id)))
                return suggestions, failed, len(deps)
            finally:
                await source.aclose()

        def success(result) -> None:
            suggestions, failed, dep_count = result
            self.pack_updated.emit(pack.id)
            msg = t("ctl.mod_added", title=detail.title)
            if dep_count:
                msg += " " + t("ctl.mod_added_deps", count=dep_count)
            self.notify.emit("success", msg)
            if on_done is not None:
                on_done(suggestions, failed)

        self._run(t("ctl.task.add_mod", title=detail.title), task, on_success=success, category="mods")

    def add_mod_versions(self, pack: Pack, items: list[tuple[ModVersion, ModDetail]]) -> None:
        for version, detail in items:
            self.manager.add_mod(pack, version, detail)
        if items:
            self.pack_updated.emit(pack.id)
            self.notify.emit("success", t("ctl.mods_added", count=len(items)))

    def add_content_download(self, pack: Pack, kind: ContentKind, version: ModVersion, detail: ModDetail) -> None:
        self.manager.add_content_download(pack, kind, version, detail)
        self.pack_updated.emit(pack.id)
        self.notify.emit("success", t("ctl.item_added", title=detail.title))

    def add_world_download(self, pack: Pack, version: ModVersion, detail: ModDetail) -> None:
        async def task(ctx: TaskContext) -> None:
            async with make_client() as client:
                await self.manager.add_world_from_download(pack, version, client, detail=detail)

        def success(_r) -> None:
            self.pack_updated.emit(pack.id)
            self.notify.emit("success", t("ctl.world_added", name=detail.title))

        self._run(t("ctl.task.download_world", title=detail.title), task, on_success=success, category="content")

    def add_local_world(self, pack: Pack, path: Path) -> None:
        try:
            entry = self.manager.add_content(pack, ContentKind.WORLD, path)
        except (ValueError, OSError) as exc:
            record_exception(exc, origin="add_local_world", logger=log)
            self._error(str(exc))
            return
        self.pack_updated.emit(pack.id)
        self.notify.emit("success", t("ctl.world_added", name=entry.name))

    def remove_mods(self, pack: Pack, project_ids: list[str]) -> None:
        for pid in project_ids:
            self.manager.remove_mod(pack, pid)
        self.pack_updated.emit(pack.id)
        self.notify.emit("info", t("ctl.mods_removed", count=len(project_ids)))

    def remove_content_download(self, pack: Pack, kind: ContentKind, project_ids: list[str]) -> None:
        for pid in project_ids:
            self.manager.remove_content_download(pack, kind, pid)
        self.pack_updated.emit(pack.id)
        self.notify.emit("info", t("ctl.items_removed", count=len(project_ids)))

    def remove_worlds(self, pack: Pack, names: list[str]) -> None:
        for name in names:
            self.manager.remove_content(pack, ContentKind.WORLD, name)
            if pack.server.selected_world == name:
                self.manager.update_server_config(pack, selected_world=None)
        self.pack_updated.emit(pack.id)
        self.notify.emit("info", t("ctl.items_removed", count=len(names)))

    def set_mod_env(self, pack: Pack, project_ids: list[str], client: EnvRequirement, server: EnvRequirement) -> None:
        for pid in project_ids:
            self.manager.set_mod_env(pack, pid, client=client, server=server)
        self.pack_updated.emit(pack.id)
        self.notify.emit("success", t("ctl.env_updated", count=len(project_ids)))

    def add_cheat_mod(self, pack: Pack, kind: str) -> None:
        source = ModSourceType.WURST if kind == "wurst" else ModSourceType.METEOR
        label = "Wurst Client" if kind == "wurst" else "Meteor Client"

        async def task(ctx: TaskContext) -> CheatModFile:
            async with make_client() as client:
                return await download_cheat_mod(client, source, pack.minecraft, cache_dir=self.cache_dir(pack))

        def success(result: CheatModFile) -> None:
            self.manager.add_cheat_mod_file(pack, source, result)
            self.pack_updated.emit(pack.id)
            self.notify.emit("success", t("ctl.item_added", title=label))

        self._run(t("ctl.task.cheat_mod", label=label, minecraft=pack.minecraft), task, on_success=success, category="mods")

    # ------------------------------------------------------------------ güncellemeler

    def _clients(self):
        modrinth = ModrinthClient()
        curseforge = CurseForgeClient(self.settings.curseforge_api_key) if self.has_curseforge() else None
        return modrinth, curseforge

    def check_updates(
        self, pack: Pack, on_done: Callable[[list, list[str]], None], on_error: ErrorCallback = None
    ) -> None:
        from mcpack.packs.updates import check_updates

        async def task(ctx: TaskContext):
            modrinth, curseforge = self._clients()
            try:
                return await check_updates(pack, modrinth=modrinth, curseforge=curseforge, progress_cb=ctx.progress)
            finally:
                await modrinth.aclose()
                if curseforge:
                    await curseforge.aclose()

        self._run(
            t("ctl.task.check_updates", name=pack.name), task, on_success=lambda r: on_done(*r),
            on_error=on_error, category="mods",
        )

    def apply_updates(self, pack: Pack, updates: list, on_done: Callable[[object], None] | None = None) -> None:
        from mcpack.packs.updates import apply_updates

        async def task(ctx: TaskContext):
            modrinth, curseforge = self._clients()
            try:
                return await apply_updates(
                    self.manager, pack, updates, modrinth=modrinth, curseforge=curseforge, progress_cb=ctx.progress
                )
            finally:
                await modrinth.aclose()
                if curseforge:
                    await curseforge.aclose()

        def success(result) -> None:
            self.pack_updated.emit(pack.id)
            msg = t("ctl.updates_applied", count=len(result.applied))
            if result.added_dependencies:
                msg += " " + t("ctl.mod_added_deps", count=len(result.added_dependencies))
            self.notify.emit("warning" if result.failed or result.unresolved_dependencies else "success", msg)
            if on_done:
                on_done(result)

        self._run(t("ctl.task.apply_updates", name=pack.name, count=len(updates)), task, on_success=success, category="mods")

    # ------------------------------------------------------------------ bağımlılıklar

    def describe_missing_dependencies(self, pack: Pack, on_done: Callable[[list[str]], None]) -> None:
        """Pack'teki eksik zorunlu bağımlılıkları (çevrimdışı tespit) ağdan
        gerçek adlarıyla çözer. Eksik yoksa on_done([]) HEMEN çağrılır."""
        missing = self.manager.find_missing_dependencies(pack)
        if not missing:
            on_done([])
            return

        async def task(ctx: TaskContext) -> list[str]:
            by_mod: dict[str, list[str]] = {}
            for mod_name, dep_id in missing:
                by_mod.setdefault(mod_name, []).append(dep_id)
            lines = []
            for mod_name, dep_ids in by_mod.items():
                parent = next((m for m in pack.mods if (m.name or m.file_name) == mod_name), None)
                source = self.make_source(parent.source.value if parent else ModSourceType.MODRINTH.value)
                try:
                    labels = []
                    for dep_id in dep_ids:
                        try:
                            labels.append((await source.get_project(dep_id)).title)
                        except Exception:  # noqa: BLE001 - ad alınamazsa id ile devam
                            labels.append(dep_id)
                    lines.append(f"• {mod_name}: {', '.join(labels)}")
                finally:
                    await source.aclose()
            return lines

        self._run(t("ctl.task.check_deps", name=pack.name), task, on_success=on_done, category="mods")

    # ------------------------------------------------------------------ export

    def export(self, pack: Pack, fmt: str, output: Path, source_dir: Path, on_done: Callable[[Path], None] | None = None) -> None:
        exporter_cls = EXPORTERS[fmt]

        async def task(ctx: TaskContext) -> Path:
            async with make_client() as client:
                return await exporter_cls().export(
                    pack, source_dir=source_dir, output_path=output, cache_dir=self.cache_dir(pack),
                    content_root=self.manager.content_root(pack), client=client,
                    exclude_dirs=self.settings.excluded_override_dirs(), progress_cb=ctx.progress,
                    cancel_event=ctx.cancel_event,
                )

        def success(path: Path) -> None:
            self.notify.emit("success", t("ctl.export_done", path=path))
            if on_done:
                on_done(path)

        self._run(t("ctl.task.export", name=pack.name, fmt=EXPORT_LABELS[fmt]), task, on_success=success, cancellable=True, category="export")

    def server_pack(
        self, pack: Pack, output: Path, source_dir: Path, selected_world: str | None, on_done: Callable[[Path, bool], None] | None = None
    ) -> None:
        async def task(ctx: TaskContext) -> Path:
            async with make_client() as client:
                return await ServerPackExporter().export(
                    pack, source_dir=source_dir, output_path=output, cache_dir=self.cache_dir(pack),
                    content_root=self.manager.content_root(pack), client=client,
                    exclude_dirs=self.settings.excluded_override_dirs(), progress_cb=ctx.progress,
                    cancel_event=ctx.cancel_event, selected_world=selected_world,
                )

        def success(path: Path) -> None:
            missing_notice = False
            try:
                with zipfile.ZipFile(path) as zf:
                    missing_notice = SERVER_FILE_MISSING_NOTICE_NAME in zf.namelist()
            except OSError:
                pass
            self.notify.emit("warning" if missing_notice else "success", t("ctl.server_pack_done", path=path))
            if on_done:
                on_done(path, missing_notice)

        self._run(t("ctl.task.server_pack", name=pack.name), task, on_success=success, cancellable=True, category="export")

    def run_sklauncher(self, pack: Pack, source_dir: Path) -> None:
        if not self.settings.sklauncher_path:
            self._error(t("ctl.sklauncher_missing"))
            return

        async def task(ctx: TaskContext) -> Path:
            instances_dir = instances_dir_for(self.settings.sklauncher_path)
            async with make_client() as client:
                return await prepare_instance(
                    pack, source_dir=source_dir, instances_dir=instances_dir, cache_dir=self.cache_dir(pack),
                    content_root=self.manager.content_root(pack), client=client,
                    exclude_dirs=self.settings.excluded_override_dirs(), progress_cb=ctx.progress,
                    cancel_event=ctx.cancel_event,
                )

        def success(instance_dir: Path) -> None:
            self.notify.emit("success", t("ctl.instance_ready", path=instance_dir))
            try:
                launch(self.settings.sklauncher_path)
            except Exception as exc:  # noqa: BLE001
                record_exception(exc, origin="sklauncher.launch", logger=log)
                self._error(str(exc))

        self._run(t("ctl.task.sklauncher", name=pack.name), task, on_success=success, cancellable=True, category="export")

    # ------------------------------------------------------------------ yerel sunucu

    def server_info(self, pack: Pack) -> dict:
        root = self.manager.server_root(pack)
        process = self.registry.get(pack.id)
        return {
            "root": root,
            "state": server_state(root),
            "running": process is not None and process.is_running,
            "buffer": list(process.buffer) if process is not None else [],
            "started_at": self.server_started_at.get(pack.id),
        }

    def read_server_properties(self, pack: Pack) -> dict[str, str]:
        return merged_with_defaults(read_properties(self.manager.server_root(pack) / "server.properties"))

    def save_server_properties(self, pack: Pack, values: dict[str, str]) -> None:
        path = self.manager.server_root(pack) / "server.properties"
        current = read_properties(path)
        current.update(values)
        write_properties(path, current)
        log.info("server.properties kaydedildi: %s", pack.name)
        self.notify.emit("success", t("ctl.properties_saved"))

    def update_server_config(self, pack: Pack, **kwargs) -> None:
        self.manager.update_server_config(pack, **kwargs)
        self.pack_updated.emit(pack.id)

    def prepare_server(self, pack: Pack) -> None:
        async def task(ctx: TaskContext) -> None:
            async with make_client() as client:
                await prepare_server(
                    pack, server_root=self.manager.server_root(pack), cache_dir=self.cache_dir(pack),
                    content_root=self.manager.content_root(pack), client=client,
                    progress_cb=ctx.progress, cancel_event=ctx.cancel_event,
                )

        self._run(
            t("ctl.task.prepare_server", name=pack.name), task,
            on_success=lambda _r: self.notify.emit("success", t("ctl.server_prepared")),
            on_finally=lambda: self.server_changed.emit(pack.id), cancellable=True, category="server",
        )

    def install_server(self, pack: Pack) -> None:
        root = self.manager.server_root(pack)
        installer = find_installer_jar(root)
        if installer is None:
            self._error(t("ctl.installer_not_found"))
            return
        java = find_java(self.settings.java_path)
        if java is None:
            self._error(t("ctl.java_not_found"))
            return

        async def task(ctx: TaskContext) -> list[str]:
            return await run_installer(installer, root, java)

        def success(lines: list[str]) -> None:
            self.console_reset.emit(pack.id, lines[-500:])
            self.notify.emit("success", t("ctl.install_done"))

        self._run(
            t("ctl.task.install_server", name=pack.name), task, on_success=success,
            on_finally=lambda: self.server_changed.emit(pack.id), category="server",
        )

    def start_server(self, pack: Pack) -> None:
        if not pack.server.eula_accepted:
            self._error(t("ctl.eula_required"))
            return
        root = self.manager.server_root(pack)
        if server_state(root) != "ready":
            self._error(t("ctl.server_not_ready"))
            return
        if self.registry.is_running(pack.id):
            self._error(t("runtime.error.already_running"))
            return
        java = find_java(self.settings.java_path)
        if java is None:
            self._error(t("ctl.java_not_found"))
            return
        try:
            cmd = build_launch_command(root, pack.server.memory_mb, optimized=pack.server.use_optimized_flags)
        except ServerRuntimeError as exc:
            self._error(str(exc))
            return
        if cmd[0] == "java":
            cmd[0] = java
        (root / "eula.txt").write_text("eula=true\n", encoding="utf-8")

        process = ServerProcess()
        pack_id = pack.id
        # Okuyucu thread'inden gelen satırlar düz-Python dinleyicisiyle
        # alınıp kendi (QueuedConnection'lı) sinyalimizle GUI thread'ine
        # taşınır — bkz. _on_line_from_thread.
        process.add_listener(lambda line, pid=pack_id: self._line_from_thread.emit(pid, line) if line is not None else None)
        process.process_exited.connect(
            lambda code, pid=pack_id: self._exit_from_thread.emit(pid, code), Qt.ConnectionType.DirectConnection
        )
        self.registry.set(pack_id, process)
        try:
            process.start(cmd, cwd=root)
        except (ServerRuntimeError, OSError) as exc:
            self.registry.pop(pack_id)
            record_exception(exc, origin="server.start", logger=log)
            self._error(str(exc))
            return
        self.server_started_at[pack_id] = time.time()
        self.console_reset.emit(pack_id, [])
        self.server_changed.emit(pack_id)
        self.notify.emit("info", t("ctl.server_starting", name=pack.name))

        required = required_java_major(pack.minecraft)

        async def check_java(ctx: TaskContext) -> int | None:
            return await get_java_major_version(java)

        def checked(major: int | None) -> None:
            if major is not None and major < required:
                log.warning("Java %s algılandı, MC %s için %s+ gerekli", major, pack.minecraft, required)
                self.notify.emit("warning", t("ctl.java_version_warning", detected=major, minecraft=pack.minecraft, required=required))

        self._run(t("ctl.task.java_check"), check_java, on_success=checked, silent=True, notify_error=False, category="server")

    def stop_server(self, pack_id: str) -> None:
        process = self.registry.get(pack_id)
        if process is None or not process.is_running:
            return

        async def task(ctx: TaskContext) -> None:
            import asyncio

            await asyncio.to_thread(process.stop, 30)

        self._run(t("ctl.task.stop_server"), task, on_finally=lambda: self.server_changed.emit(pack_id), category="server")

    def kill_server(self, pack_id: str) -> None:
        process = self.registry.get(pack_id)
        if process is not None and process.is_running and process._process is not None:  # noqa: SLF001
            log.warning("Sunucu zorla sonlandırılıyor (kill): %s", pack_id)
            process._process.kill()  # noqa: SLF001

    def send_command(self, pack_id: str, text: str) -> None:
        process = self.registry.get(pack_id)
        if process is None:
            return
        try:
            process.send_command(text)
        except ServerRuntimeError as exc:
            self._error(str(exc))

    @Slot(str, str)
    def _on_line_from_thread(self, pack_id: str, line: str) -> None:
        self.console_line.emit(pack_id, line)

    @Slot(str, int)
    def _on_exit_from_thread(self, pack_id: str, code: int) -> None:
        self.registry.pop(pack_id)
        self.server_started_at.pop(pack_id, None)
        self.server_changed.emit(pack_id)
        pack = self.load_pack(pack_id)
        name = pack.name if pack else pack_id
        if code == 0:
            self.notify.emit("info", t("ctl.server_stopped", name=name))
        else:
            self.notify.emit("error", t("ctl.server_crashed", name=name, code=code))

    def running_server_ids(self) -> list[str]:
        return self.registry.all_running_ids()

    # ------------------------------------------------------------------ oyuncular

    def _running(self, pack_id: str) -> ServerProcess | None:
        process = self.registry.get(pack_id)
        return process if process is not None and process.is_running else None

    def player_action(self, pack: Pack, action: str, player: str, value: int = 0) -> None:
        if not PLAYER_NAME_RE.match(player):
            self._error(t("webpanel.error.invalid_player"))
            return
        builders = {
            "heal": lambda: heal_command(player),
            "kill": lambda: kill_command(player),
            "feed": lambda: feed_command(player),
            "damage": lambda: damage_command(player, value, pack.minecraft),
            "hunger": lambda: hunger_command(player, value),
        }
        process = self._running(pack.id)
        if process is None:
            return
        try:
            process.send_command(builders[action]())
            self.notify.emit("success", t("ctl.player_action_sent", player=player, action=t(f"player.action.{action}")))
        except ServerRuntimeError as exc:
            self._error(str(exc))

    def poll_players(self, pack_id: str) -> None:
        process = self._running(pack_id)
        if process is None or pack_id in self._polling:
            return
        self._polling.add(pack_id)

        async def task(ctx: TaskContext) -> str | None:
            import asyncio

            return await asyncio.to_thread(
                process.send_command_and_wait, list_players_command(), match=re.compile(r"players online:"), timeout=3
            )

        def success(line: str | None) -> None:
            names = parse_list_response(line) if line else None
            if names is not None:
                self.players_updated.emit(pack_id, names)

        self._run(
            t("ctl.task.poll_players"), task, on_success=success, on_finally=lambda: self._polling.discard(pack_id),
            silent=True, notify_error=False, category="server",
        )

    def query_items(self, pack_id: str, player: str, which: str, on_done: Callable[[list], None]) -> None:
        if not PLAYER_NAME_RE.match(player):
            self._error(t("webpanel.error.invalid_player"))
            return
        process = self._running(pack_id)
        if process is None:
            return
        command = inventory_query_command(player) if which == "inventory" else ender_chest_query_command(player)

        async def task(ctx: TaskContext) -> str | None:
            import asyncio

            return await asyncio.to_thread(
                process.send_command_and_wait, command, match=re.compile(r"has the following entity data:"), timeout=5
            )

        def success(line: str | None) -> None:
            if line is None:
                self._error(t("ctl.inventory_timeout", player=player))
                return
            on_done(parse_item_list_response(line) or [])

        self._run(t("ctl.task.inventory", player=player), task, on_success=success, silent=True, category="server")

    # ------------------------------------------------------------------ web paneli

    @property
    def web_panel_running(self) -> bool:
        return self._web_panel is not None

    @property
    def web_panel_url(self) -> str:
        return self._web_panel.url if self._web_panel is not None else ""

    def toggle_web_panel(self) -> None:
        if self._web_panel is not None:
            self._web_panel.stop()
            self._web_panel = None
            self.web_panel_changed.emit(False, "")
            self.notify.emit("info", t("ctl.web_panel_stopped"))
            return
        from mcpack.webpanel import WebPanelStartError, start_web_panel

        try:
            handle = start_web_panel(manager=self.manager, registry=self.registry, settings=self.settings)
        except WebPanelStartError as exc:
            self._error(str(exc))
            return
        except Exception as exc:  # noqa: BLE001
            record_exception(exc, origin="webpanel.start", logger=log)
            self._error(str(exc))
            return
        self._web_panel = handle
        self.web_panel_changed.emit(True, handle.url)
        key = "ctl.web_panel_started_network" if handle.network_exposed else "ctl.web_panel_started_local"
        self.notify.emit("success", t(key, url=handle.url))
        if handle.port_changed:
            owner = handle.port_owner or t("ctl.port_owner_unknown")
            self.notify.emit(
                "warning",
                t("ctl.web_panel_port_changed", requested=handle.requested_port, port=handle.port, owner=owner),
            )

    # ------------------------------------------------------------------ kapanış

    def shutdown(self, *, stop_servers: bool) -> None:
        log.info("Uygulama kapanıyor (sunucuları durdur: %s)", stop_servers)
        if stop_servers:
            import threading

            threads = []
            for pid in self.registry.all_running_ids():
                process = self.registry.get(pid)
                if process is not None:
                    th = threading.Thread(target=process.stop, args=(20,), name=f"stop-{pid}")
                    th.start()
                    threads.append(th)
            # Paralel durdurma: önceden her sunucu sırayla 15 sn'ye kadar
            # GUI thread'ini kilitliyordu.
            for th in threads:
                th.join(timeout=25)
        if self._web_panel is not None:
            self._web_panel.stop()
            self._web_panel = None
        self.tasks.cancel_all()
        self.tasks.wait_all(3000)
