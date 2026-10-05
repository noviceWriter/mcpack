"""Pack yaşam döngüsü: oluşturma, açma, kaydetme, mod ekleme/çıkarma,
bağımlılık çözümleme (proje-amacı.md §2.2, Akış A/B).
"""

from __future__ import annotations

import shutil
import tempfile
import zipfile
from pathlib import Path

import httpx

from mcpack.downloader import download_file
from mcpack.known_mods import load_known_client_only_slugs
from mcpack.models import (
    ContentDownload,
    ContentEntry,
    ContentKind,
    EnvRequirement,
    Loader,
    ModEntry,
    ModEnv,
    ModHashes,
    ModSourceType,
    Pack,
)
from mcpack.packs import storage
from mcpack.sources.base import ModDetail, ModSource, ModVersion
from mcpack.sources.cheat_mods import CheatModUnavailableError, find_meteor_download, find_wurst_download

_CONTENT_SUBDIR: dict[ContentKind, str] = {
    ContentKind.SHADERPACK: "shaderpacks",
    ContentKind.RESOURCEPACK: "resourcepacks",
    ContentKind.DATAPACK: "datapacks",
    ContentKind.WORLD: "worlds",
}


def _downloadable_fields(version: ModVersion, detail: ModDetail | None) -> dict:
    """ModEntry ve ContentDownload'ın ortak (DownloadableFile) alanları."""
    file = version.primary_file
    if file is None:
        raise ValueError(f"{version.name}: indirilebilir dosya bulunamadı")

    return dict(
        source=version.source,
        project_id=version.project_id,
        slug=detail.slug if detail is not None else None,
        name=detail.title if detail is not None else None,
        version_id=version.version_id,
        file_name=file.file_name,
        file_size=file.size,
        hashes=ModHashes(sha1=file.sha1, sha512=file.sha512),
        download_url=file.url,
    )


def _version_to_entry(version: ModVersion, detail: ModDetail | None) -> ModEntry:
    env = ModEnv()
    if detail is not None and detail.source == ModSourceType.MODRINTH:
        # Sadece Modrinth API'si client/server bilgisini güvenilir verir.
        env = ModEnv(client=detail.client_side, server=detail.server_side)
    elif detail is not None:
        # CurseForge gibi kaynaklar bu bilgiyi vermez; bilinen client-only
        # listesiyle (data/client_only_mods.json) sezgisel eşleştir, yoksa
        # güvenli varsayılan olarak ikisinde de gerekli say (kullanıcı
        # "Client/Server Düzelt" ile elle düzeltebilir — proje-amacı.md §6).
        known = load_known_client_only_slugs()
        if detail.slug and detail.slug.lower() in known:
            env = ModEnv(client=EnvRequirement.REQUIRED, server=EnvRequirement.UNSUPPORTED)

    return ModEntry(
        **_downloadable_fields(version, detail),
        env=env,
        dependencies=[
            d.project_id for d in version.dependencies
            if d.dependency_type == "required" and d.project_id
        ],
    )


def _detect_world_root(extract_dir: Path) -> Path:
    """CurseForge'tan indirilen bir dünya ZIP'i genelde ya dünya dosyalarını
    (level.dat vb.) doğrudan köke ya da tek bir alt klasöre koyar — ikisini
    de dener, bulamazsa köşeye sıkışmamak için extract_dir'i olduğu gibi döner."""
    if (extract_dir / "level.dat").exists():
        return extract_dir
    subdirs = [p for p in extract_dir.iterdir() if p.is_dir()]
    if len(subdirs) == 1 and (subdirs[0] / "level.dat").exists():
        return subdirs[0]
    return extract_dir


class PackManager:
    def __init__(self, packs_dir: Path) -> None:
        self.packs_dir = packs_dir

    def create_pack(
        self,
        *,
        name: str,
        minecraft: str,
        loader: Loader,
        loader_version: str,
        author: str = "",
        summary: str = "",
    ) -> Pack:
        pack = Pack(
            name=name,
            minecraft=minecraft,
            loader=loader,
            loader_version=loader_version,
            author=author,
            summary=summary,
        )
        storage.save_pack(pack, self.packs_dir)
        return pack

    def list_packs(self) -> list[Pack]:
        packs = []
        for path in storage.list_pack_files(self.packs_dir):
            try:
                packs.append(storage.load_pack(path))
            except ValueError:
                continue  # bozuk/eksik JSON, listelemeyi durdurmasın
        return packs

    def load(self, pack_id: str) -> Pack:
        return storage.load_pack(storage.pack_file_path(self.packs_dir, pack_id))

    def save(self, pack: Pack) -> None:
        pack.touch()
        storage.save_pack(pack, self.packs_dir)

    def delete(self, pack_id: str) -> None:
        storage.delete_pack(pack_id, self.packs_dir)
        # pack.json silinince content/<pack_id>/'ye kopyalanmış dünya/shader/
        # resourcepack/datapack dosyaları yetim kalıp diskte sonsuza kadar
        # kalırdı — pack'le birlikte onları da temizliyoruz.
        shutil.rmtree(self.packs_dir / "content" / pack_id, ignore_errors=True)
        # Aynı mantık yerel sunucu klasörü için de geçerli (bkz. server_root)
        # — çağıran taraf (gui/main_window.py) silmeden önce sürecin
        # çalışmadığından emin olmalı, burası sadece disk temizliği yapar.
        shutil.rmtree(self.packs_dir / "servers" / pack_id, ignore_errors=True)

    def content_root(self, pack: Pack) -> Path:
        """Pack'e yüklenmiş shader/resourcepack/datapack/dünya dosyalarının
        gerçekten kopyalandığı klasör — mod jar'larının aksine bunlar bir
        download_url'e değil, kullanıcının diskten seçtiği bir dosyaya karşılık
        geldiği için export sırasında beklenen bir "source_dir" olmayabilir;
        bu yüzden pack'in kendi kalıcı deposunda tutulur."""
        return self.packs_dir / "content" / pack.id

    def server_root(self, pack: Pack) -> Path:
        """pack'in YEREL, çalıştırılabilir sunucu kurulumunun tutulduğu
        klasör (bkz. server_runtime.py) — export/server.py'nin ürettiği
        geçici zip'in aksine kalıcıdır, tekrar tekrar "Hazırla" ile
        güncellenir ve doğrudan buradan `java` ile başlatılır."""
        return self.packs_dir / "servers" / pack.id

    def update_server_config(
        self,
        pack: Pack,
        *,
        memory_mb: int | None = None,
        selected_world: str | None = ...,
        eula_accepted: bool | None = None,
        use_optimized_flags: bool | None = None,
    ) -> Pack:
        """set_mod_env'deki aynı "sadece verilenleri güncelle" deseni.

        selected_world için `...` (Ellipsis) varsayılanı kullanılır —
        None GEÇERLİ bir değer (dünya seçimini kaldır) olduğu için, "hiç
        verilmedi" ile "None'a ayarla" ayrımı başka türlü yapılamazdı."""
        if memory_mb is not None:
            pack.server.memory_mb = memory_mb
        if selected_world is not ...:
            pack.server.selected_world = selected_world
        if eula_accepted is not None:
            pack.server.eula_accepted = eula_accepted
        if use_optimized_flags is not None:
            pack.server.use_optimized_flags = use_optimized_flags
        self.save(pack)
        return pack

    def add_content(
        self, pack: Pack, kind: ContentKind, source_path: Path, *, display_name: str | None = None
    ) -> ContentEntry:
        """source_path'i (dosya ya da klasör) pack'in kendi içerik deposuna
        kopyalar ve pack.content'e ekler. Aynı kind+ad zaten varsa üzerine yazar
        (add_mod'daki project_id tekilleştirmesiyle aynı mantık).

        display_name: verilirse pack.content'teki ad (ve dolayısıyla export'taki
        klasör adı) source_path'in gerçek dosya adı yerine bunu kullanır — ör.
        CurseForge'tan indirilip geçici bir klasöre açılan bir dünyaya asıl
        proje adını vermek için (bkz. add_world_from_download).

        display_name CurseForge'tan gelen bir proje başlığı olabileceği için
        (güvenilmeyen girdi) Path(...).name ile SADECE son bileşenine indirgenir
        — aksi halde içinde ".." ya da "/" geçen bir başlık content_root'un
        dışına yazmaya çalışabilirdi (path traversal)."""
        name = Path(display_name or source_path.name).name
        if not name or name in {".", ".."}:
            raise ValueError("Geçersiz içerik adı.")
        dest_dir = self.content_root(pack) / _CONTENT_SUBDIR[kind]
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / name

        already_tracked = any(c.kind == kind and c.name == name for c in pack.content)
        if dest.exists() and not already_tracked:
            # Aynı ada sahip ama pack'in HENÜZ bilmediği bir klasör/dosya zaten
            # var — ör. iki farklı dünyanın ikisi de varsayılan "New World"
            # adını taşıyor. Sessizce üzerine yazıp birinin verisini silmek
            # yerine kullanıcıya haber veriyoruz (bilinen ad+kind'ı GÜNCELLEMEK
            # hâlâ serbest, bkz. already_tracked).
            raise ValueError(
                f"'{name}' adında farklı bir içerik zaten var — önce onu kaldırın ya da yeniden adlandırın."
            )

        is_dir = source_path.is_dir()
        if is_dir:
            if dest.exists():
                shutil.rmtree(dest)
            shutil.copytree(source_path, dest)
        else:
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, dest)

        pack.content = [c for c in pack.content if not (c.kind == kind and c.name == name)]
        entry = ContentEntry(
            kind=kind,
            name=name,
            stored_path=str(dest.relative_to(self.content_root(pack))),
            is_dir=is_dir,
        )
        pack.content.append(entry)
        self.save(pack)
        return entry

    def remove_content(self, pack: Pack, kind: ContentKind, name: str) -> None:
        entry = next((c for c in pack.content if c.kind == kind and c.name == name), None)
        if entry is None:
            return
        path = self.content_root(pack) / entry.stored_path
        if path.is_dir():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
        pack.content = [c for c in pack.content if not (c.kind == kind and c.name == name)]
        self.save(pack)

    async def add_world_from_download(
        self,
        pack: Pack,
        version: ModVersion,
        client: httpx.AsyncClient,
        *,
        detail: ModDetail | None = None,
    ) -> ContentEntry:
        """CurseForge'ta aranıp bulunan hazır bir dünyayı (harita) indirir,
        ZIP'ini açar ve normal bir yerel dünya gibi content_root'a kopyalar
        (bkz. add_content) — diğer indirilebilir içeriklerden (bkz.
        add_content_download) farkı: dünya export sırasında gömülecek tek bir
        dosya değil, saves/<ad>/ altına açılması gereken bir klasördür, bu
        yüzden indirme burada (ekleme anında) yapılır, export'ta değil."""
        file = version.primary_file
        if file is None:
            raise ValueError(f"{version.name}: indirilebilir dosya bulunamadı")

        with tempfile.TemporaryDirectory(prefix="mcpack-world-") as tmp:
            tmp_path = Path(tmp)
            zip_path = tmp_path / file.file_name
            await download_file(client, file.url, zip_path, sha1=file.sha1, sha512=file.sha512)
            extract_dir = tmp_path / "extracted"
            with zipfile.ZipFile(zip_path) as zf:
                zf.extractall(extract_dir)
            world_root = _detect_world_root(extract_dir)
            display_name = detail.title if detail is not None else version.name
            return self.add_content(pack, ContentKind.WORLD, world_root, display_name=display_name)

    def add_content_download(
        self, pack: Pack, kind: ContentKind, version: ModVersion, detail: ModDetail | None = None
    ) -> ContentDownload:
        """add_mod ile birebir aynı akış — shader/resourcepack/datapack da
        Modrinth/CurseForge'tan arayıp eklenir (kullanıcı isteği: "yine mod
        yükler gibi"). Dünyanın aksine (bkz. add_content) gerçek dosya export
        sırasında indirilir, burada sadece referans (ContentDownload) saklanır."""
        entry = ContentDownload(kind=kind, **_downloadable_fields(version, detail))
        existing = pack.find_content_download(kind, entry.project_id)
        if existing:
            pack.content_downloads.remove(existing)
        pack.content_downloads.append(entry)
        self.save(pack)
        return entry

    def remove_content_download(self, pack: Pack, kind: ContentKind, project_id: str) -> None:
        pack.content_downloads = [
            c for c in pack.content_downloads if not (c.kind == kind and c.project_id == project_id)
        ]
        self.save(pack)

    def add_mod(self, pack: Pack, version: ModVersion, detail: ModDetail | None = None) -> ModEntry:
        entry = _version_to_entry(version, detail)
        existing = pack.find_mod(entry.project_id)
        if existing:
            pack.mods.remove(existing)
        pack.mods.append(entry)
        self.save(pack)
        return entry

    def remove_mod(self, pack: Pack, project_id: str) -> None:
        pack.mods = [m for m in pack.mods if m.project_id != project_id]
        self.save(pack)

    _CHEAT_MOD_LABELS = {ModSourceType.WURST: "Wurst Client", ModSourceType.METEOR: "Meteor Client"}
    _CHEAT_MOD_PROJECT_IDS = {ModSourceType.WURST: "wurst", ModSourceType.METEOR: "meteor"}

    def add_cheat_mod(self, pack: Pack, source: ModSourceType, file_name: str, download_url: str) -> ModEntry:
        """Wurst/Meteor gibi CurseForge/Modrinth'te barındırılmayan hile
        modları için — normal add_mod'un aksine ModSource/ModVersion arama
        akışından geçmez, zaten çözülmüş (dosya_adı, indirme_url) çiftini
        (bkz. sources/cheat_mods.py) doğrudan ModEntry'ye çevirir.

        env sabit olarak istemci-zorunlu/sunucu-desteklenmez verilir — bunlar
        gerçek birer istemci hile aracıdır, sunucu tarafında hiçbir anlamları
        yok; mevcut server pack filtrelemesi (export/server.py:
        is_server_compatible) bu sayede onları otomatik dışlar, ayrıca bir
        özel durum kodu gerekmez."""
        project_id = self._CHEAT_MOD_PROJECT_IDS[source]
        existing = pack.find_mod(project_id)
        if existing:
            pack.mods.remove(existing)
        entry = ModEntry(
            source=source,
            project_id=project_id,
            name=self._CHEAT_MOD_LABELS[source],
            version_id=file_name,
            file_name=file_name,
            download_url=download_url,
            hashes=ModHashes(),
            env=ModEnv(client=EnvRequirement.REQUIRED, server=EnvRequirement.UNSUPPORTED),
        )
        pack.mods.append(entry)
        self.save(pack)
        return entry

    def set_mod_env(
        self,
        pack: Pack,
        project_id: str,
        *,
        client: EnvRequirement | None = None,
        server: EnvRequirement | None = None,
    ) -> ModEntry:
        """Bir modun client/server durumunu elle düzeltir.

        proje-amacı.md §6: "Client/Server ayrımında emin olunamayan modlar
        için kullanıcıya seçenek sun" — CurseForge gibi bu bilgiyi
        vermeyen kaynaklardan gelen modlarda kullanıcı burada düzeltir.
        """
        entry = pack.find_mod(project_id)
        if entry is None:
            raise ValueError(f"Pack'te bulunamadı: {project_id}")
        if client is not None:
            entry.env.client = client
        if server is not None:
            entry.env.server = server
        self.save(pack)
        return entry

    async def resolve_dependencies(
        self,
        pack: Pack,
        source: ModSource,
        version: ModVersion,
    ) -> tuple[list[ModVersion], list[str]]:
        """Bir versiyonun required bağımlılıklarını, pack'te henüz olmayanlar
        için yinelemeli olarak Modrinth/CurseForge'tan çeker.

        Döngüsel bağımlılıklara karşı ziyaret edilen project_id'leri takip eder.

        Döner: (otomatik eklenecek çözülmüş versiyonlar, ÇÖZÜLEMEYEN zorunlu
        bağımlılıkların adları). İkinci liste önceden yok sayılıp sessizce
        atlanıyordu — pack.minecraft/pack.loader için o bağımlılığın uyumlu
        bir versiyonu yoksa (ör. mod farklı bir MC/loader kombinasyonuna göre
        güncellenmiş), eklenen mod SESSİZCE eksik bir zorunlu bağımlılıkla
        kalıyor, bu da genelde oyunun açılışta çökmesiyle sonuçlanıyordu
        (kullanıcı geri bildirimi: "Prism'de açılışta hata verdi, zorunlu
        modlar yüklenmemiş"). Artık bu isim listesiyle çağıran taraf
        (gui/main_window.py) kullanıcıyı uyarabiliyor."""
        resolved: list[ModVersion] = []
        failed_names: list[str] = []
        visited: set[str] = {version.project_id, *(m.project_id for m in pack.mods)}
        queue = [
            d.project_id
            for d in version.dependencies
            if d.dependency_type == "required" and d.project_id
        ]

        while queue:
            project_id = queue.pop(0)
            if project_id in visited:
                continue
            visited.add(project_id)

            versions = await source.get_versions(
                project_id, game_version=pack.minecraft, loader=pack.loader
            )
            if not versions:
                label = project_id
                try:
                    dep_detail = await source.get_project(project_id)
                    label = dep_detail.title
                except Exception:  # noqa: BLE001 - isim alınamazsa id ile devam
                    pass
                failed_names.append(label)
                continue
            dep_version = versions[0]
            resolved.append(dep_version)

            queue.extend(
                d.project_id
                for d in dep_version.dependencies
                if d.dependency_type == "required" and d.project_id and d.project_id not in visited
            )

        return resolved, failed_names

    def find_missing_dependencies(self, pack: Pack) -> list[tuple[str, str]]:
        """Pack'teki her modun kayıtlı zorunlu bağımlılıklarının (bkz.
        ModEntry.dependencies — mod eklenirken kaydedilir) hâlâ pack'te olup
        olmadığını çevrimdışı, hızlıca kontrol eder ("sert kontrol" —
        export/server pack/SKLauncher öncesi engelleyici doğrulama için,
        bkz. main_window.py). Ağa gitmez; sadece pack'in kendi verisine bakar.

        Döner: (modun adı/dosya adı, eksik bağımlılığın project_id'si)
        çiftlerinin listesi — boşsa pack'in bilinen bir eksik bağımlılığı
        yok demektir (üçüncü taraf/gizli bağımlılıklar bu şekilde
        yakalanamaz, sadece API'nin bildirdiği açık bağımlılıklar)."""
        present_ids = {m.project_id for m in pack.mods}
        missing: list[tuple[str, str]] = []
        for mod in pack.mods:
            for dep_id in mod.dependencies:
                if dep_id not in present_ids:
                    missing.append((mod.name or mod.file_name, dep_id))
        return missing

    async def resolve_optional_dependencies(
        self,
        pack: Pack,
        source: ModSource,
        version: ModVersion,
    ) -> list[ModVersion]:
        """Bir versiyonun 'optional' (önerilen ama zorunlu olmayan)
        bağımlılıklarını getirir — required'ın aksine OTOMATİK EKLENMEZ,
        kullanıcının seçip seçmeyeceğine karar vermesi için döner.

        Sadece verilen versiyonun doğrudan opsiyonel bağımlılıklarına bakar
        (zorunlu bağımlılıkların kendi opsiyonelleri dahil edilmez —
        listenin patlamaması için).
        """
        existing_ids = {m.project_id for m in pack.mods} | {version.project_id}
        optional_ids = [
            d.project_id
            for d in version.dependencies
            if d.dependency_type == "optional" and d.project_id and d.project_id not in existing_ids
        ]

        resolved: list[ModVersion] = []
        for project_id in optional_ids:
            versions = await source.get_versions(
                project_id, game_version=pack.minecraft, loader=pack.loader
            )
            if versions:
                resolved.append(versions[0])

        return resolved

    async def fork_pack(
        self,
        pack: Pack,
        *,
        name: str,
        minecraft: str,
        loader_version: str,
        modrinth: ModSource,
        curseforge: ModSource | None,
        http_client: httpx.AsyncClient,
    ) -> tuple[Pack, list[str]]:
        """pack'i FARKLI bir Minecraft versiyonuna (üst ya da alt sürüm, fark
        etmez) uyarlayan yeni, bağımsız bir pack oluşturur ("fork" —
        kullanıcı isteği: "bir mod paketini üst/alt minecraft sürümlerine
        uyarlama; modun uygun sürümü yoksa kullanıcıya bilgi verir, modu
        eklemez").

        pack.mods'taki HER mod için kendi kaynağında (Modrinth/CurseForge/
        Wurst/Meteor) yeni minecraft versiyonuna uygun bir versiyon aranır;
        bulunamazsa (ya da CurseForge API anahtarı yoksa) mod YENİ pack'e
        SESSİZCE eklenmez — sadece adı döndürülen listeye eklenir, çağıran
        taraf (GUI/CLI) bunu kullanıcıya göstersin diye (bkz.
        resolve_dependencies'teki aynı prensip). content_downloads (shader/
        resourcepack/datapack) için de aynı mantık uygulanır; yerel içerik
        (content — ör. dünyalar) Minecraft versiyonundan bağımsız olduğu için
        doğrudan kopyalanır.

        Loader TÜRÜ değişmez, sadece MC versiyonu değişir — loader_version
        çağıran tarafça yeni MC versiyonu için ayrıca sorulur/çözülür (bkz.
        gameinfo.get_loader_versions, gui/fork_pack_dialog.py).

        Not: pack.mods'ta zaten düz bir liste olarak duran zorunlu
        bağımlılıklar da normal mod gibi tek tek yeniden çözülür — version
        bump'ın tamamen YENİ bir bağımlılık getirmesi burada yakalanmaz, ama
        export/server pack/SKLauncher öncesi sert kontrol
        (find_missing_dependencies) bunu zaten ayrıca yakalar."""
        new_pack = self.create_pack(
            name=name,
            minecraft=minecraft,
            loader=pack.loader,
            loader_version=loader_version,
            author=pack.author,
            summary=pack.summary,
        )

        failed: list[str] = []

        def _source_for(source_type: ModSourceType) -> ModSource | None:
            if source_type == ModSourceType.MODRINTH:
                return modrinth
            if source_type == ModSourceType.CURSEFORGE:
                return curseforge
            return None

        for mod in pack.mods:
            label = mod.name or mod.file_name
            if mod.source in (ModSourceType.WURST, ModSourceType.METEOR):
                try:
                    if mod.source == ModSourceType.WURST:
                        file_name, url = await find_wurst_download(http_client, minecraft)
                    else:
                        file_name, url = await find_meteor_download(http_client, minecraft)
                except CheatModUnavailableError:
                    failed.append(label)
                    continue
                self.add_cheat_mod(new_pack, mod.source, file_name, url)
                continue

            source = _source_for(mod.source)
            if source is None:
                failed.append(label)
                continue
            versions = await source.get_versions(
                mod.project_id, game_version=minecraft, loader=new_pack.loader
            )
            if not versions:
                failed.append(label)
                continue
            detail: ModDetail | None = None
            try:
                detail = await source.get_project(mod.project_id)
            except Exception:  # noqa: BLE001 - detay alınamazsa isimsiz eklenir
                pass
            self.add_mod(new_pack, versions[0], detail)

        for cd in pack.content_downloads:
            label = cd.name or cd.file_name
            source = _source_for(cd.source)
            if source is None:
                failed.append(label)
                continue
            versions = await source.get_versions(cd.project_id, game_version=minecraft)
            if not versions:
                failed.append(label)
                continue
            detail = None
            try:
                detail = await source.get_project(cd.project_id)
            except Exception:  # noqa: BLE001
                pass
            self.add_content_download(new_pack, cd.kind, versions[0], detail)

        for entry in pack.content:
            src_path = self.content_root(pack) / entry.stored_path
            if src_path.exists():
                self.add_content(new_pack, entry.kind, src_path, display_name=entry.name)

        return new_pack, failed
