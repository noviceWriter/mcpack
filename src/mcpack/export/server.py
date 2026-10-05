"""Server pack üretimi: client pack'ten server-only paket türetme.

proje-amacı.md §2.4: client-only modları ele (Sodium, Iris, ModMenu, REI vb.),
server-side/both modları tut, config/script klasörlerini kopyala, isteğe
bağlı start.bat/start.sh ekle.

Eleme mantığı iki katmanlı:
1. Modrinth API'sinden gelen gerçek env bilgisi (ModEntry.env) — güvenilir.
2. CurseForge gibi env bilgisi vermeyen kaynaklar için data/client_only_mods.json
   içindeki bilinen slug listesiyle sezgisel eşleştirme (fallback).
"""

from __future__ import annotations

from pathlib import Path

import httpx

from mcpack.downloader import (
    DownloadCancelledError,
    DownloadError,
    HashMismatchError,
    download_file,
    verify_hashes,
)
from mcpack.export.base import (
    EXCLUDED_OVERRIDE_DIR_NAMES,
    Exporter,
    ProgressCallback,
    collect_content_download_files,
    collect_override_files,
    collect_world_files,
    ensure_mods_downloaded,
    write_zip,
)
from mcpack.known_mods import load_known_client_only_slugs
from mcpack.models import ContentKind, ModEntry, ModSourceType, Pack
from mcpack.server_jar import ServerDownload, ServerDownloadError, get_server_download


def is_server_compatible(entry: ModEntry, known_client_only_slugs: set[str] | None = None) -> bool:
    """Bir modun server pack'te kalıp kalmayacağına karar verir."""
    if entry.env.server.value == "unsupported":
        return False

    # Modrinth API'si zaten gerçek env bilgisi veriyor — bilinen sezgisel
    # listeyle bunun üzerine yazmıyoruz. Aksi halde örn. JEI (gerçekte
    # server: optional) sırf bizim listemizde "client-only" varsayımıyla
    # yer aldığı için yanlışlıkla server pack'ten elenirdi.
    if entry.source == ModSourceType.MODRINTH:
        return True

    known = known_client_only_slugs if known_client_only_slugs is not None else load_known_client_only_slugs()
    if entry.slug and entry.slug.lower() in known:
        return False
    if any(slug in entry.file_name.lower() for slug in known):
        return False

    return True


def filter_server_mods(pack: Pack, known_client_only_slugs: set[str] | None = None) -> list[ModEntry]:
    known = known_client_only_slugs if known_client_only_slugs is not None else load_known_client_only_slugs()
    return [m for m in pack.mods if is_server_compatible(m, known)]


async def ensure_server_file_downloaded(
    download: ServerDownload,
    cache_dir: Path,
    client: httpx.AsyncClient,
    *,
    cancel_event=None,
) -> Path:
    """ensure_mods_downloaded'daki aynı önbellekleme deseni: dosya zaten
    cache_dir'de ve (varsa) hash'i tutuyorsa tekrar indirilmez. Fabric/Quilt/
    Forge/NeoForge'ta resmi API hash vermediği için (sha1=None) bu durumlarda
    sadece "dosya zaten var mı" kontrol edilir — export'u her çalıştırışta
    aynı sunucu dosyasını tekrar tekrar indirmemek için.

    Public (alt çizgisiz): server_runtime.py'deki prepare_server de aynı
    indirme+cache mantığını kullanır (export'un zip'e gömdüğü dosyayla
    yerel sunucu kurulumunun kullandığı dosya aynı kod yolundan geçer)."""
    cache_dir.mkdir(parents=True, exist_ok=True)
    dest = cache_dir / download.file_name
    if dest.exists():
        if not download.sha1:
            return dest
        try:
            verify_hashes(dest, sha1=download.sha1)
            return dest
        except HashMismatchError:
            dest.unlink(missing_ok=True)

    await download_file(client, download.url, dest, sha1=download.sha1, cancel_event=cancel_event)
    return dest


_START_SH_READY = """#!/usr/bin/env bash
# Basit sunucu başlatma script'i - Java yolunu/argümanlarını ihtiyaca göre düzenleyin.
java -Xmx4G -Xms2G -jar server.jar nogui
"""

_START_BAT_READY = """@echo off
REM Basit sunucu baslatma script'i - Java yolunu/argumanlarini ihtiyaca gore duzenleyin.
java -Xmx4G -Xms2G -jar server.jar nogui
pause
"""

_START_SH_INSTALLER = """#!/usr/bin/env bash
# Bu loader (Forge/NeoForge) hazır bir server.jar değil, bir KURULUM
# PROGRAMI sunuyor. İlk çalıştırmada önce kurulumu yapın:
#   java -jar {installer_name} --installServer
# Kurulum bitince oluşan run.sh (ya da üretilen sunucu jar'ı) ile başlatın:
#   ./run.sh nogui
echo "Once calistirin: java -jar {installer_name} --installServer"
echo "Sonra olusan run.sh ile baslatin: ./run.sh nogui"
"""

_START_BAT_INSTALLER = """@echo off
REM Bu loader (Forge/NeoForge) hazir bir server.jar degil, bir KURULUM
REM PROGRAMI sunuyor. Once kurulumu yapin:
REM   java -jar {installer_name} --installServer
REM Kurulum bitince olusan run.bat ile baslatin.
echo Once calistirin: java -jar {installer_name} --installServer
echo Sonra olusan run.bat ile baslatin.
pause
"""

SERVER_FILE_MISSING_NOTICE_NAME = "SUNUCU_DOSYASI_INDIRILEMEDI.txt"
"""Export sonrası GUI'nin (bkz. gui/main_window.py:do_server_pack) zip'i
tekrar açıp bu dosyanın var olup olmadığına bakarak kullanıcıyı anında
uyarabilmesi için adı burada sabit — iki yerde aynı literal string'i
tekrarlamamak için."""

_SERVER_FILE_MISSING_NOTICE = """Sunucu dosyasi otomatik indirilemedi: {reason}

Elle indirmeniz gerekiyor:
- Pack: Minecraft {minecraft} / {loader} {loader_version}
- Resmi kaynaktan uygun sunucu dosyasini (ya da Forge/NeoForge icin
  installer'i) bulup bu klasore "server.jar" olarak koyun, sonra start.sh/
  start.bat'i calistirin.
"""


class ServerPackExporter(Exporter):
    format_name = "Server Pack"
    file_extension = ".zip"

    def __init__(self, *, include_start_scripts: bool = True, download_server_file: bool = True) -> None:
        self.include_start_scripts = include_start_scripts
        self.download_server_file = download_server_file
        """Kullanıcı isteği: "server dosyasını kullanıcı indirsin mi yoksa
        biz indirtebilir miyiz?" — açıksa (varsayılan) resmi API'lerden
        pack.minecraft/loader'a uygun GERÇEK sunucu dosyası bulunup pakete
        gömülür (bkz. mcpack.server_jar). Testler, bu davranışı ayrıca test
        eden tests/test_server_jar.py dışında ağ çağrısı yapmamak için
        False geçebilir."""

    async def export(
        self,
        pack: Pack,
        *,
        source_dir: Path,
        output_path: Path,
        cache_dir: Path,
        content_root: Path,
        client: httpx.AsyncClient,
        exclude_dirs: set[str] | None = None,
        progress_cb: ProgressCallback | None = None,
        cancel_event=None,
        selected_world: str | None = None,
    ) -> Path:
        """selected_world: pack.content'teki (ContentKind.WORLD, ad) eşleşen
        dünya arşivde "world/" adıyla dahil edilir — sunucular tek bir dünya
        klasörü bekler (bkz. gui/main_window.py'deki seçim akışı). None ise
        hiç dünya dahil edilmez (kullanıcı istemedi ya da yüklü dünya yok)."""
        server_mods = filter_server_mods(pack)
        mod_files = await ensure_mods_downloaded(
            server_mods, cache_dir, client, progress_cb=progress_cb, cancel_event=cancel_event
        )

        override_files = collect_override_files(
            source_dir,
            pack.overrides.include,
            exclude_dirs=exclude_dirs if exclude_dirs is not None else EXCLUDED_OVERRIDE_DIR_NAMES,
        )
        # Shaderpack/resourcepack tamamen client-side'dır, sunucu için anlamsız
        # — server pack'e sadece datapack ve (seçildiyse) dünya dahil edilir.
        datapacks = pack.content_downloads_of(ContentKind.DATAPACK)
        downloaded_datapacks = await ensure_mods_downloaded(datapacks, cache_dir, client, cancel_event=cancel_event)
        override_files += collect_content_download_files(
            datapacks, downloaded_datapacks,
            datapack_world_roots=["world"] if selected_world is not None else None,
        )
        if selected_world is not None:
            override_files += collect_world_files(pack, content_root, selected_world=selected_world)

        server_download: ServerDownload | None = None
        server_download_error: str | None = None
        if self.download_server_file:
            try:
                server_download = await get_server_download(
                    client, pack.loader, pack.minecraft, pack.loader_version
                )
                dest = await ensure_server_file_downloaded(
                    server_download, cache_dir, client, cancel_event=cancel_event
                )
                override_files.append((dest, server_download.file_name))
            except DownloadCancelledError:
                raise  # kullanıcı export'u iptal etti, normal akış devam etsin
            except (ServerDownloadError, DownloadError, httpx.HTTPError) as exc:
                # Ağ hatası/bu MC-loader kombinasyonu için resmi dosya yok —
                # export'u BOZMA, sadece kullanıcıyı not dosyasıyla bilgilendir.
                server_download_error = str(exc)
                server_download = None

        manifest_entries: list[tuple[str, str | bytes]] = []
        if self.include_start_scripts:
            if server_download is not None and server_download.is_installer:
                manifest_entries.append(
                    ("start.sh", _START_SH_INSTALLER.format(installer_name=server_download.file_name))
                )
                manifest_entries.append(
                    ("start.bat", _START_BAT_INSTALLER.format(installer_name=server_download.file_name))
                )
            else:
                manifest_entries.append(("start.sh", _START_SH_READY))
                manifest_entries.append(("start.bat", _START_BAT_READY))
                if self.download_server_file and server_download is None:
                    manifest_entries.append((
                        SERVER_FILE_MISSING_NOTICE_NAME,
                        _SERVER_FILE_MISSING_NOTICE.format(
                            reason=server_download_error or "bilinmeyen hata",
                            minecraft=pack.minecraft,
                            loader=pack.loader.value,
                            loader_version=pack.loader_version,
                        ),
                    ))

        return write_zip(
            output_path,
            manifest_entries=manifest_entries,
            mod_files=mod_files,
            mod_arc_prefix="mods/",
            override_files=override_files,
            override_arc_prefix="",
        )
