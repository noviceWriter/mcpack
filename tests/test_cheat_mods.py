"""Wurst Client / Meteor Client indirme + pack'e ekleme testleri.

Kullanıcı isteği: "Wurst/Meteor gibi hile modlarının kendi indirme API'leri
vardır, bunları programa entegre edip 2. bir programa/tarayıcıya gitmeden
indirebilmeliyiz" — bkz. sources/cheat_mods.py (gerçek API'ler, kimlik
doğrulama gerektirmiyor, kaynak kodlarına bakılarak teyit edildi)."""

from pathlib import Path

import httpx
import pytest
import respx

from mcpack.export.server import filter_server_mods
from mcpack.models import EnvRequirement, Loader, ModSourceType
from mcpack.packs.manager import PackManager
from mcpack.sources.cheat_mods import (
    METEOR_DOWNLOAD_API,
    WURST_RELEASES_API,
    CheatModUnavailableError,
    find_meteor_download,
    find_wurst_download,
)


# -- PackManager.add_cheat_mod ------------------------------------------------


def test_add_cheat_mod_creates_client_only_entry(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.20.1", loader=Loader.FABRIC, loader_version="0.16.5")

    entry = manager.add_cheat_mod(
        pack, ModSourceType.WURST, "Wurst-Client-v7.42-MC1.20.1.jar",
        "https://github.com/Wurst-Imperium/Wurst-MCX2/releases/download/v7.42/Wurst-Client-v7.42-MC1.20.1.jar",
    )

    assert entry.project_id == "wurst"
    assert entry.name == "Wurst Client"
    assert entry.env.client == EnvRequirement.REQUIRED
    assert entry.env.server == EnvRequirement.UNSUPPORTED
    assert pack.find_mod("wurst") is entry


def test_add_cheat_mod_replaces_existing_same_source(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.20.1", loader=Loader.FABRIC, loader_version="0.16.5")

    manager.add_cheat_mod(pack, ModSourceType.WURST, "old.jar", "https://x/old.jar")
    manager.add_cheat_mod(pack, ModSourceType.WURST, "new.jar", "https://x/new.jar")

    wurst_entries = [m for m in pack.mods if m.source == ModSourceType.WURST]
    assert len(wurst_entries) == 1
    assert wurst_entries[0].file_name == "new.jar"


def test_add_cheat_mod_excluded_from_server_pack(tmp_path: Path):
    """Hile modları istemci-only'dir — server pack filtrelemesi onları
    otomatik elemeli (env.server=unsupported, bkz. export/server.py)."""
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.20.1", loader=Loader.FABRIC, loader_version="0.16.5")
    manager.add_cheat_mod(pack, ModSourceType.METEOR, "meteor-client-1.20.1.jar", "https://x/meteor.jar")

    assert filter_server_mods(pack) == []


# -- sources/cheat_mods.py -----------------------------------------------------


@pytest.mark.asyncio
async def test_find_wurst_download_matches_mc_version_suffix():
    releases = [
        {
            "assets": [
                {"name": "Wurst-Client-v7.42-MC1.21.jar", "browser_download_url": "https://x/121.jar"},
                {"name": "Wurst-Client-v7.42-MC1.20.1.jar", "browser_download_url": "https://x/1201.jar"},
                {"name": "Wurst-Client-v7.42-MC1.20.1-sources.jar", "browser_download_url": "https://x/1201-src.jar"},
            ]
        }
    ]
    with respx.mock:
        respx.get(WURST_RELEASES_API).mock(return_value=httpx.Response(200, json=releases))
        async with httpx.AsyncClient() as client:
            name, url = await find_wurst_download(client, "1.20.1")

    assert name == "Wurst-Client-v7.42-MC1.20.1.jar"
    assert url == "https://x/1201.jar"


@pytest.mark.asyncio
async def test_find_wurst_download_raises_when_unsupported():
    with respx.mock:
        respx.get(WURST_RELEASES_API).mock(return_value=httpx.Response(200, json=[]))
        async with httpx.AsyncClient() as client:
            with pytest.raises(CheatModUnavailableError):
                await find_wurst_download(client, "1.0.0")


@pytest.mark.asyncio
async def test_find_meteor_download_returns_filename_from_disposition():
    with respx.mock:
        respx.get(METEOR_DOWNLOAD_API).mock(
            return_value=httpx.Response(
                200,
                content=b"fake-jar-bytes",
                headers={
                    "content-type": "application/java-archive",
                    "content-disposition": "attachment; filename=meteor-client-1.21-5.jar",
                },
            )
        )
        async with httpx.AsyncClient() as client:
            name, url = await find_meteor_download(client, "1.21")

    assert name == "meteor-client-1.21-5.jar"
    assert url == f"{METEOR_DOWNLOAD_API}?version=1.21"


@pytest.mark.asyncio
async def test_find_meteor_download_raises_on_json_error_body():
    """KRİTİK: desteklenmeyen versiyonda API HTTP 200 + küçük bir JSON hata
    gövdesi döner (asıl jar değil) — Content-Type kontrol edilmezse bu
    sessizce ".jar" gibi indirilip export'u bozar."""
    with respx.mock:
        respx.get(METEOR_DOWNLOAD_API).mock(
            return_value=httpx.Response(
                200,
                json={"error": "Failed to get maven version."},
            )
        )
        async with httpx.AsyncClient() as client:
            with pytest.raises(CheatModUnavailableError):
                await find_meteor_download(client, "1.7.10")



# -- download_cheat_mod: indir + doğrula + hash'le ----------------------------


@pytest.mark.asyncio
async def test_download_cheat_mod_verifies_github_sha256_and_records_hashes(tmp_path):
    import hashlib

    from mcpack.sources.cheat_mods import download_cheat_mod

    jar = b"real-wurst-jar"
    releases = [{"assets": [{
        "name": "Wurst-Client-v7.42-MC1.20.1.jar", "browser_download_url": "https://x/w.jar",
        "digest": "sha256:" + hashlib.sha256(jar).hexdigest(),
    }]}]
    with respx.mock:
        respx.get(WURST_RELEASES_API).mock(return_value=httpx.Response(200, json=releases))
        respx.get("https://x/w.jar").mock(return_value=httpx.Response(200, content=jar))
        async with httpx.AsyncClient() as client:
            result = await download_cheat_mod(client, ModSourceType.WURST, "1.20.1", cache_dir=tmp_path)
    assert result.sha1 == hashlib.sha1(jar).hexdigest()
    assert result.sha512 == hashlib.sha512(jar).hexdigest()
    assert result.size == len(jar)
    assert (tmp_path / result.file_name).read_bytes() == jar


@pytest.mark.asyncio
async def test_download_cheat_mod_rejects_tampered_github_asset(tmp_path, monkeypatch):
    import mcpack.downloader as downloader
    from mcpack.sources.cheat_mods import download_cheat_mod

    async def no_sleep(_s):
        return None

    monkeypatch.setattr(downloader.asyncio, "sleep", no_sleep)
    releases = [{"assets": [{
        "name": "Wurst-Client-v7.42-MC1.20.1.jar", "browser_download_url": "https://x/w.jar",
        "digest": "sha256:" + "0" * 64,
    }]}]
    with respx.mock:
        respx.get(WURST_RELEASES_API).mock(return_value=httpx.Response(200, json=releases))
        respx.get("https://x/w.jar").mock(return_value=httpx.Response(200, content=b"tampered"))
        async with httpx.AsyncClient() as client:
            with pytest.raises(CheatModUnavailableError):
                await download_cheat_mod(client, ModSourceType.WURST, "1.20.1", cache_dir=tmp_path)
    assert not (tmp_path / "Wurst-Client-v7.42-MC1.20.1.jar").exists()


@pytest.mark.asyncio
async def test_export_refuses_changed_meteor_build(tmp_path, monkeypatch):
    """Meteor'un URL'si sabit değil: kaydedilen hash'le uyuşmayan yeni bir
    build sessizce pakete gömülmemeli, anlaşılır bir hata vermeli."""
    import hashlib

    import mcpack.downloader as downloader
    from mcpack.downloader import DownloadError
    from mcpack.export.base import ensure_mods_downloaded
    from mcpack.models import ModHashes

    async def no_sleep(_s):
        return None

    monkeypatch.setattr(downloader.asyncio, "sleep", no_sleep)
    manager = PackManager(tmp_path / "packs")
    pack = manager.create_pack(name="T", minecraft="1.21.4", loader=Loader.FABRIC, loader_version="0.16.5")
    old = b"meteor-build-42"
    entry = manager.add_cheat_mod(
        pack, ModSourceType.METEOR, "meteor-client-1.21.4-42.jar", f"{METEOR_DOWNLOAD_API}?version=1.21.4",
        hashes=ModHashes(sha1=hashlib.sha1(old).hexdigest(), sha512=hashlib.sha512(old).hexdigest()),
    )
    with respx.mock:
        respx.get(METEOR_DOWNLOAD_API).mock(return_value=httpx.Response(200, content=b"meteor-build-43"))
        async with httpx.AsyncClient() as client:
            with pytest.raises(DownloadError, match="Meteor Client"):
                await ensure_mods_downloaded([entry], tmp_path / "cache", client)
