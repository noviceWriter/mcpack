import httpx
import pytest
import respx

from mcpack.gameinfo import (
    FABRIC_LOADER_URL,
    FORGE_MAVEN_METADATA_URL,
    MODRINTH_TAG_URL,
    NEOFORGE_VERSIONS_URL,
    GameInfoError,
    get_fabric_loader_versions,
    get_forge_versions,
    get_loader_versions,
    get_minecraft_versions,
    get_neoforge_versions,
)
from mcpack.models import Loader


@pytest.mark.asyncio
async def test_get_minecraft_versions_filters_releases():
    with respx.mock:
        respx.get(MODRINTH_TAG_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"version": "1.21.1", "version_type": "release"},
                    {"version": "24w10a", "version_type": "snapshot"},
                    {"version": "1.21", "version_type": "release"},
                ],
            )
        )
        async with httpx.AsyncClient() as client:
            versions = await get_minecraft_versions(client)

    assert versions == ["1.21.1", "1.21"]


@pytest.mark.asyncio
async def test_get_fabric_loader_versions():
    with respx.mock:
        respx.get(FABRIC_LOADER_URL).mock(
            return_value=httpx.Response(200, json=[{"version": "0.16.5"}, {"version": "0.16.4"}])
        )
        async with httpx.AsyncClient() as client:
            versions = await get_fabric_loader_versions(client)

    assert versions == ["0.16.5", "0.16.4"]


_FORGE_METADATA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<metadata>
  <groupId>net.minecraftforge</groupId>
  <artifactId>forge</artifactId>
  <versioning>
    <versions>
      <version>1.21.1-47.3.1</version>
      <version>1.21.1-47.4.0</version>
      <version>1.21.1-47.2.0</version>
      <version>1.20.1-47.1.0</version>
    </versions>
  </versioning>
</metadata>
"""


@pytest.mark.asyncio
async def test_get_forge_versions_returns_full_catalog_sorted_desc():
    with respx.mock:
        respx.get(FORGE_MAVEN_METADATA_URL).mock(
            return_value=httpx.Response(200, text=_FORGE_METADATA_XML)
        )
        async with httpx.AsyncClient() as client:
            versions = await get_forge_versions(client, "1.21.1")

    assert versions == ["47.4.0", "47.3.1", "47.2.0"]


@pytest.mark.asyncio
async def test_get_forge_versions_empty_when_no_match():
    with respx.mock:
        respx.get(FORGE_MAVEN_METADATA_URL).mock(
            return_value=httpx.Response(200, text=_FORGE_METADATA_XML)
        )
        async with httpx.AsyncClient() as client:
            versions = await get_forge_versions(client, "1.99.9")

    assert versions == []


@pytest.mark.asyncio
async def test_get_neoforge_versions_filters_by_mc_version_and_sorts_desc():
    with respx.mock:
        respx.get(NEOFORGE_VERSIONS_URL).mock(
            return_value=httpx.Response(
                200,
                json={
                    "versions": [
                        "21.1.0", "21.1.100", "21.1.20", "20.4.50",  # 20.4.50 farklı MC versiyonu
                    ]
                },
            )
        )
        async with httpx.AsyncClient() as client:
            versions = await get_neoforge_versions(client, "1.21.1")

    assert versions == ["21.1.100", "21.1.20", "21.1.0"]


@pytest.mark.asyncio
async def test_get_loader_versions_vanilla_returns_empty():
    async with httpx.AsyncClient() as client:
        versions = await get_loader_versions(client, Loader.VANILLA, "1.21.1")
    assert versions == []


@pytest.mark.asyncio
async def test_get_loader_versions_http_error_wrapped():
    with respx.mock:
        respx.get(FABRIC_LOADER_URL).mock(return_value=httpx.Response(500))
        async with httpx.AsyncClient() as client:
            with pytest.raises(GameInfoError):
                await get_loader_versions(client, Loader.FABRIC, "1.21.1")
