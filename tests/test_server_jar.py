"""Sunucu dosyası otomatik indirme testleri.

Kullanıcı isteği: "server dosyasını kullanıcı indirsin mi yoksa biz
indirtebilir miyiz?" — bkz. mcpack/server_jar.py (resmi API'lerden doğru
indirme bilgisini bulma) ve export/server.py (ServerPackExporter'ın bunu
pakete gömmesi, bulunamazsa export'u bozmadan bir not dosyasına düşmesi)."""

import zipfile
from pathlib import Path

import httpx
import pytest
import respx

from mcpack.export.server import SERVER_FILE_MISSING_NOTICE_NAME, ServerPackExporter
from mcpack.models import Loader, Pack
from mcpack.server_jar import (
    FABRIC_INSTALLER_VERSIONS_URL,
    QUILT_INSTALLER_VERSIONS_URL,
    VERSION_MANIFEST_URL,
    ServerDownloadError,
    get_server_download,
)

# -- server_jar.py: her loader için doğru indirme bilgisi -------------------


@pytest.mark.asyncio
async def test_vanilla_server_download_uses_official_manifest():
    manifest = {"versions": [{"id": "1.20.1", "url": "https://x/1.20.1.json"}]}
    version_meta = {"downloads": {"server": {"url": "https://x/server-1.20.1.jar", "sha1": "abc123", "size": 100}}}

    with respx.mock:
        respx.get(VERSION_MANIFEST_URL).mock(return_value=httpx.Response(200, json=manifest))
        respx.get("https://x/1.20.1.json").mock(return_value=httpx.Response(200, json=version_meta))
        async with httpx.AsyncClient() as client:
            result = await get_server_download(client, Loader.VANILLA, "1.20.1", "")

    assert result.file_name == "server.jar"
    assert result.url == "https://x/server-1.20.1.jar"
    assert result.sha1 == "abc123"
    assert result.is_installer is False


@pytest.mark.asyncio
async def test_vanilla_server_download_raises_when_version_unknown():
    with respx.mock:
        respx.get(VERSION_MANIFEST_URL).mock(return_value=httpx.Response(200, json={"versions": []}))
        async with httpx.AsyncClient() as client:
            with pytest.raises(ServerDownloadError):
                await get_server_download(client, Loader.VANILLA, "99.99", "")


@pytest.mark.asyncio
async def test_vanilla_server_download_raises_when_no_server_download_published():
    """Çok eski versiyonlarda (1.2 öncesi) resmi olarak ayrı bir server.jar yok."""
    manifest = {"versions": [{"id": "inf-20100618", "url": "https://x/old.json"}]}
    with respx.mock:
        respx.get(VERSION_MANIFEST_URL).mock(return_value=httpx.Response(200, json=manifest))
        respx.get("https://x/old.json").mock(return_value=httpx.Response(200, json={"downloads": {}}))
        async with httpx.AsyncClient() as client:
            with pytest.raises(ServerDownloadError):
                await get_server_download(client, Loader.VANILLA, "inf-20100618", "")


@pytest.mark.asyncio
async def test_fabric_server_download_builds_ready_to_run_jar_url():
    installers = [{"version": "0.11.1", "stable": False}, {"version": "0.11.0", "stable": True}]
    with respx.mock:
        respx.get(FABRIC_INSTALLER_VERSIONS_URL).mock(return_value=httpx.Response(200, json=installers))
        async with httpx.AsyncClient() as client:
            result = await get_server_download(client, Loader.FABRIC, "1.21.1", "0.16.5")

    assert result.file_name == "server.jar"
    assert result.is_installer is False
    assert result.url == "https://meta.fabricmc.net/v2/versions/loader/1.21.1/0.16.5/0.11.0/server/jar"


@pytest.mark.asyncio
async def test_quilt_server_download_builds_ready_to_run_jar_url():
    installers = [{"version": "0.9.0", "stable": True}]
    with respx.mock:
        respx.get(QUILT_INSTALLER_VERSIONS_URL).mock(return_value=httpx.Response(200, json=installers))
        async with httpx.AsyncClient() as client:
            result = await get_server_download(client, Loader.QUILT, "1.21.1", "0.26.0")

    assert result.file_name == "server.jar"
    assert result.url == "https://meta.quiltmc.org/v3/versions/loader/1.21.1/0.26.0/0.9.0/server/jar"


@pytest.mark.asyncio
async def test_forge_server_download_builds_installer_url_without_network():
    async with httpx.AsyncClient() as client:
        result = await get_server_download(client, Loader.FORGE, "1.20.1", "47.4.10")

    assert result.is_installer is True
    assert result.file_name == "forge-1.20.1-47.4.10-installer.jar"
    assert result.url == (
        "https://maven.minecraftforge.net/net/minecraftforge/forge/"
        "1.20.1-47.4.10/forge-1.20.1-47.4.10-installer.jar"
    )


@pytest.mark.asyncio
async def test_neoforge_server_download_builds_installer_url_without_network():
    async with httpx.AsyncClient() as client:
        result = await get_server_download(client, Loader.NEOFORGE, "1.21.1", "21.1.100")

    assert result.is_installer is True
    assert result.file_name == "neoforge-21.1.100-installer.jar"
    assert result.url == (
        "https://maven.neoforged.net/releases/net/neoforged/neoforge/"
        "21.1.100/neoforge-21.1.100-installer.jar"
    )


# -- export/server.py: ServerPackExporter entegrasyonu ----------------------


def _make_pack(**kwargs) -> Pack:
    defaults = dict(name="Test", minecraft="1.20.1", loader=Loader.VANILLA, loader_version="")
    defaults.update(kwargs)
    return Pack(**defaults)


@pytest.mark.asyncio
async def test_server_pack_bundles_real_vanilla_server_jar(tmp_path: Path):
    pack = _make_pack()
    manifest = {"versions": [{"id": "1.20.1", "url": "https://x/1.20.1.json"}]}
    version_meta = {"downloads": {"server": {"url": "https://x/server.jar", "sha1": None, "size": None}}}

    output_path = tmp_path / "server.zip"
    with respx.mock:
        respx.get(VERSION_MANIFEST_URL).mock(return_value=httpx.Response(200, json=manifest))
        respx.get("https://x/1.20.1.json").mock(return_value=httpx.Response(200, json=version_meta))
        respx.get("https://x/server.jar").mock(return_value=httpx.Response(200, content=b"fake-server-bytes"))
        async with httpx.AsyncClient() as client:
            await ServerPackExporter().export(
                pack,
                source_dir=tmp_path / "src",
                output_path=output_path,
                cache_dir=tmp_path / "cache",
                content_root=tmp_path / "content",
                client=client,
            )

    with zipfile.ZipFile(output_path) as zf:
        names = set(zf.namelist())
        assert "server.jar" in names
        assert zf.read("server.jar") == b"fake-server-bytes"
        assert SERVER_FILE_MISSING_NOTICE_NAME not in names
        start_sh = zf.read("start.sh").decode()
        assert "installServer" not in start_sh


@pytest.mark.asyncio
async def test_server_pack_falls_back_to_notice_file_when_download_fails(tmp_path: Path):
    """Ağ hatası (ya da bu MC versiyonu için resmi dosya yoksa) export
    BOZULMAMALI — sadece kullanıcıyı bilgilendiren bir not dosyası eklenmeli."""
    pack = _make_pack(minecraft="99.99")
    output_path = tmp_path / "server.zip"

    with respx.mock:
        respx.get(VERSION_MANIFEST_URL).mock(return_value=httpx.Response(200, json={"versions": []}))
        async with httpx.AsyncClient() as client:
            await ServerPackExporter().export(
                pack,
                source_dir=tmp_path / "src",
                output_path=output_path,
                cache_dir=tmp_path / "cache",
                content_root=tmp_path / "content",
                client=client,
            )

    with zipfile.ZipFile(output_path) as zf:
        names = set(zf.namelist())
        assert "server.jar" not in names
        assert SERVER_FILE_MISSING_NOTICE_NAME in names
        assert "start.sh" in names  # eski davranış hâlâ var, kullanıcı elle koyabilir


@pytest.mark.asyncio
async def test_server_pack_bundles_forge_installer_with_manual_instructions(tmp_path: Path):
    pack = _make_pack(loader=Loader.FORGE, loader_version="47.4.10")
    output_path = tmp_path / "server.zip"
    installer_url = (
        "https://maven.minecraftforge.net/net/minecraftforge/forge/"
        "1.20.1-47.4.10/forge-1.20.1-47.4.10-installer.jar"
    )

    with respx.mock:
        respx.get(installer_url).mock(return_value=httpx.Response(200, content=b"fake-installer-bytes"))
        async with httpx.AsyncClient() as client:
            await ServerPackExporter().export(
                pack,
                source_dir=tmp_path / "src",
                output_path=output_path,
                cache_dir=tmp_path / "cache",
                content_root=tmp_path / "content",
                client=client,
            )

    with zipfile.ZipFile(output_path) as zf:
        names = set(zf.namelist())
        assert "forge-1.20.1-47.4.10-installer.jar" in names
        assert zf.read("forge-1.20.1-47.4.10-installer.jar") == b"fake-installer-bytes"
        start_sh = zf.read("start.sh").decode()
        assert "forge-1.20.1-47.4.10-installer.jar --installServer" in start_sh
