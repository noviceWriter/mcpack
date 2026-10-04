"""Sunucu çalıştırılabilir dosyasının resmi indirme bilgisini bulur.

Kullanıcı isteği: "server dosyasını kullanıcı indirsin mi yoksa biz
indirtebilir miyiz?" — ServerPackExporter artık start.sh/.bat'ın beklediği
gerçek sunucu dosyasını (vanilla/Fabric/Quilt: hazır, çalıştırılabilir
"server.jar"; Forge/NeoForge: resmi bir "installer" — hazır bir server jar'ı
yok, kullanıcının bir kere `java -jar <installer> --installServer`
çalıştırması gerekiyor) gerçek, kimlik doğrulama gerektirmeyen resmi
API'lerden otomatik bulup indiriyor.

Şimdilik (kullanıcı isteği: "sadece otomatik indirme kısmını yapalım")
Forge/NeoForge installer'ının ÇALIŞTIRILMASI otomatikleştirilmiyor — sadece
doğru dosya bulunup indiriliyor, kurulum adımı kullanıcıya bırakılıyor
(bkz. ServerDownload.is_installer, export/server.py'deki start script
metni)."""

from __future__ import annotations

import httpx
from pydantic import BaseModel

from mcpack.models import Loader

VERSION_MANIFEST_URL = "https://piston-meta.mojang.com/mc/game/version_manifest_v2.json"
FABRIC_INSTALLER_VERSIONS_URL = "https://meta.fabricmc.net/v2/versions/installer"
FABRIC_SERVER_JAR_BASE = "https://meta.fabricmc.net/v2/versions/loader"
QUILT_INSTALLER_VERSIONS_URL = "https://meta.quiltmc.org/v3/versions/installer"
QUILT_SERVER_JAR_BASE = "https://meta.quiltmc.org/v3/versions/loader"
FORGE_MAVEN_BASE = "https://maven.minecraftforge.net/net/minecraftforge/forge"
NEOFORGE_MAVEN_BASE = "https://maven.neoforged.net/releases/net/neoforged/neoforge"


class ServerDownloadError(Exception):
    """Sunucu dosyasının indirme bilgisi bulunamadığında (ağ hatası, ya da bu
    Minecraft/loader kombinasyonu için resmi bir sunucu dosyası yoksa)
    fırlatılır — çağıran taraf (export/server.py) export'u BOZMADAN kullanıcıyı
    bilgilendiren bir not dosyasına düşer."""


class ServerDownload(BaseModel):
    file_name: str
    url: str
    sha1: str | None = None
    size: int | None = None
    is_installer: bool = False
    """True ise bu dosya ÇALIŞTIRILABİLİR bir sunucu değil, bir kurulum
    programıdır (Forge/NeoForge) — kullanıcının bir kere `java -jar
    <dosya> --installServer` çalıştırması gerekir."""


async def _get_json(client: httpx.AsyncClient, url: str, *, what: str) -> dict:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise ServerDownloadError(f"{what} alınamadı: {exc}") from exc
    return response.json()


async def _vanilla_server_download(client: httpx.AsyncClient, minecraft_version: str) -> ServerDownload:
    manifest = await _get_json(client, VERSION_MANIFEST_URL, what="Minecraft versiyon manifesti")
    entry = next((v for v in manifest.get("versions", []) if v.get("id") == minecraft_version), None)
    if entry is None:
        raise ServerDownloadError(f"Minecraft {minecraft_version} resmi versiyon listesinde bulunamadı.")

    version_meta = await _get_json(
        client, entry["url"], what=f"Minecraft {minecraft_version} versiyon bilgisi"
    )
    server = version_meta.get("downloads", {}).get("server")
    if not server:
        # Çok eski versiyonlarda (1.2'den önce) ayrı bir sunucu dosyası resmen yok.
        raise ServerDownloadError(f"Minecraft {minecraft_version} için resmi bir sunucu dosyası yayınlanmamış.")
    return ServerDownload(file_name="server.jar", url=server["url"], sha1=server.get("sha1"), size=server.get("size"))


async def _fabric_like_server_download(
    client: httpx.AsyncClient,
    *,
    installer_versions_url: str,
    server_jar_base: str,
    minecraft_version: str,
    loader_version: str,
    label: str,
) -> ServerDownload:
    """Fabric ve Quilt'in meta API'leri birebir aynı şekli paylaşıyor: bir
    "installer" versiyonu seçip onu loader meta endpoint'ine ekleyince hazır,
    çalıştırılabilir bir sunucu jar'ı üretiliyor (ayrıca bir kurulum adımı
    gerekmiyor — Fabric/Quilt'in resmi dokümantasyonundaki akış budur)."""
    installers = await _get_json(client, installer_versions_url, what=f"{label} installer versiyon listesi")
    if not installers:
        raise ServerDownloadError(f"{label} installer versiyonu bulunamadı.")
    installer_version = next((i["version"] for i in installers if i.get("stable")), installers[0]["version"])
    url = f"{server_jar_base}/{minecraft_version}/{loader_version}/{installer_version}/server/jar"
    return ServerDownload(file_name="server.jar", url=url)


async def _forge_server_download(minecraft_version: str, loader_version: str) -> ServerDownload:
    file_name = f"forge-{minecraft_version}-{loader_version}-installer.jar"
    url = f"{FORGE_MAVEN_BASE}/{minecraft_version}-{loader_version}/{file_name}"
    return ServerDownload(file_name=file_name, url=url, is_installer=True)


async def _neoforge_server_download(loader_version: str) -> ServerDownload:
    file_name = f"neoforge-{loader_version}-installer.jar"
    url = f"{NEOFORGE_MAVEN_BASE}/{loader_version}/{file_name}"
    return ServerDownload(file_name=file_name, url=url, is_installer=True)


async def get_server_download(
    client: httpx.AsyncClient, loader: Loader, minecraft_version: str, loader_version: str
) -> ServerDownload:
    """pack.loader/pack.minecraft/pack.loader_version'a uygun GERÇEK resmi
    sunucu dosyasının indirme bilgisini döner. Forge/NeoForge'ta dönen dosya
    bir installer'dır (bkz. ServerDownload.is_installer) — kurulum adımı
    şimdilik kullanıcıya bırakılıyor (bkz. modül docstring'i)."""
    if loader == Loader.VANILLA:
        return await _vanilla_server_download(client, minecraft_version)
    if loader == Loader.FABRIC:
        return await _fabric_like_server_download(
            client,
            installer_versions_url=FABRIC_INSTALLER_VERSIONS_URL,
            server_jar_base=FABRIC_SERVER_JAR_BASE,
            minecraft_version=minecraft_version,
            loader_version=loader_version,
            label="Fabric",
        )
    if loader == Loader.QUILT:
        return await _fabric_like_server_download(
            client,
            installer_versions_url=QUILT_INSTALLER_VERSIONS_URL,
            server_jar_base=QUILT_SERVER_JAR_BASE,
            minecraft_version=minecraft_version,
            loader_version=loader_version,
            label="Quilt",
        )
    if loader == Loader.FORGE:
        return await _forge_server_download(minecraft_version, loader_version)
    if loader == Loader.NEOFORGE:
        return await _neoforge_server_download(loader_version)
    raise ValueError(f"Bilinmeyen loader: {loader}")
