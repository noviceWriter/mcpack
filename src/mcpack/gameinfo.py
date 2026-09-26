"""Minecraft, Fabric, Quilt, Forge, NeoForge versiyon listelerini çeker.

"Yeni Pack" diyaloğunda kullanıcı versiyon numaralarını elle yazmak yerine
(hataya çok açık — yanlış yazılan bir loader versiyonu export'u/launcher
kurulumunu sessizce bozar) gerçek, güncel listelerden seçer.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET

import httpx

from mcpack.models import Loader

MODRINTH_TAG_URL = "https://api.modrinth.com/v2/tag/game_version"
FABRIC_LOADER_URL = "https://meta.fabricmc.net/v2/versions/loader"
QUILT_LOADER_URL = "https://meta.quiltmc.org/v3/versions/loader"
FORGE_MAVEN_METADATA_URL = "https://maven.minecraftforge.net/net/minecraftforge/forge/maven-metadata.xml"
NEOFORGE_VERSIONS_URL = "https://maven.neoforged.net/api/maven/versions/releases/net/neoforged/neoforge"


class GameInfoError(Exception):
    """Versiyon listesi çekilemediğinde Türkçe mesajla fırlatılır."""


async def _get_json(client: httpx.AsyncClient, url: str, *, what: str) -> object:
    try:
        response = await client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise GameInfoError(f"{what} alınamadı: {exc}") from exc
    return response.json()


async def get_minecraft_versions(client: httpx.AsyncClient) -> list[str]:
    """Sadece stabil release'ler (snapshot/beta/alpha hariç), yeniden eskiye."""
    data = await _get_json(client, MODRINTH_TAG_URL, what="Minecraft versiyon listesi")
    return [v["version"] for v in data if v.get("version_type") == "release"]


async def get_fabric_loader_versions(client: httpx.AsyncClient) -> list[str]:
    data = await _get_json(client, FABRIC_LOADER_URL, what="Fabric loader versiyon listesi")
    return [v["version"] for v in data]


async def get_quilt_loader_versions(client: httpx.AsyncClient) -> list[str]:
    data = await _get_json(client, QUILT_LOADER_URL, what="Quilt loader versiyon listesi")
    return [v["version"] for v in data]


async def get_forge_versions(client: httpx.AsyncClient, minecraft_version: str) -> list[str]:
    """Verilen Minecraft versiyonu için TÜM Forge build numaraları (yeniden eskiye).

    Önceden sadece promotions_slim.json'daki "recommended"/"latest" etiketli
    (Forge ekibinin öne çıkardığı, en fazla 2 tane) build gösteriliyordu —
    ör. 1.20.6 için gerçekte 84 build varken sadece 2'si listeleniyordu.
    Gerçek tam katalog maven-metadata.xml'de, "<mc_versiyonu>-<build>" olarak.
    """
    try:
        response = await client.get(FORGE_MAVEN_METADATA_URL)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise GameInfoError(f"Forge versiyon listesi alınamadı: {exc}") from exc

    try:
        root = ET.fromstring(response.text)
    except ET.ParseError as exc:
        raise GameInfoError(f"Forge versiyon listesi alınamadı: {exc}") from exc

    prefix = f"{minecraft_version}-"
    versions: set[str] = set()
    for el in root.iterfind("./versioning/versions/version"):
        text = (el.text or "").strip()
        if text.startswith(prefix):
            versions.add(text[len(prefix):])

    def sort_key(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(p) for p in v.split("."))
        except ValueError:
            return (0,)

    return sorted(versions, key=sort_key, reverse=True)


def _neoforge_prefix(minecraft_version: str) -> str:
    """NeoForge versiyonları '<mc_minor>.<mc_patch>.<build>' şeklinde (MC 1.21.1 -> 21.1.x)."""
    parts = minecraft_version.split(".")
    minor = parts[1] if len(parts) > 1 else "0"
    patch = parts[2] if len(parts) > 2 else "0"
    return f"{minor}.{patch}."


async def get_neoforge_versions(client: httpx.AsyncClient, minecraft_version: str) -> list[str]:
    data = await _get_json(client, NEOFORGE_VERSIONS_URL, what="NeoForge versiyon listesi")
    prefix = _neoforge_prefix(minecraft_version)
    matching = [v for v in data.get("versions", []) if v.startswith(prefix)]

    def sort_key(v: str) -> tuple[int, ...]:
        try:
            return tuple(int(p) for p in v.split("."))
        except ValueError:
            return (0,)

    return sorted(matching, key=sort_key, reverse=True)


async def get_loader_versions(
    client: httpx.AsyncClient, loader: Loader, minecraft_version: str
) -> list[str]:
    """Loader tipine göre uygun versiyon listesi. Vanilla için boş liste döner."""
    if loader == Loader.VANILLA:
        return []
    if loader == Loader.FABRIC:
        return await get_fabric_loader_versions(client)
    if loader == Loader.QUILT:
        return await get_quilt_loader_versions(client)
    if loader == Loader.FORGE:
        return await get_forge_versions(client, minecraft_version)
    if loader == Loader.NEOFORGE:
        return await get_neoforge_versions(client, minecraft_version)
    raise ValueError(f"Bilinmeyen loader: {loader}")
