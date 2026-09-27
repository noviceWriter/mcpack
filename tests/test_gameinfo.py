import httpx
import pytest
import respx

from mcpack.gameinfo import (
    FABRIC_LOADER_URL,
    FORGE_MAVEN_METADATA_URL,
    FORGE_PROMOTIONS_URL,
    MODRINTH_TAG_URL,
    NEOFORGE_VERSIONS_URL,
    QUILT_LOADER_URL,
    GameInfoError,
    get_fabric_loader_versions,
    get_forge_recommended_version,
    get_forge_versions,
    get_loader_versions,
    get_minecraft_versions,
    get_neoforge_versions,
    get_recommended_loader_version,
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


_LEGACY_FORGE_METADATA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<metadata>
  <groupId>net.minecraftforge</groupId>
  <artifactId>forge</artifactId>
  <versioning>
    <versions>
      <version>1.7.10-10.13.4.1614-1.7.10</version>
      <version>1.7.10-10.13.4.1558-1.7.10</version>
      <version>1.7.10-10.13.2.1291</version>
    </versions>
  </versioning>
</metadata>
"""


@pytest.mark.asyncio
async def test_get_forge_versions_sorts_legacy_double_suffixed_builds():
    """Eski Forge build'leri MC versiyonunu maven versiyonuna ikinci kez ekliyor
    (ör. "10.13.4.1614-1.7.10") — bu "-" sonrası build numarasına dahil değil,
    sıralamayı bozmamalı (bkz. gameinfo.py sort_key)."""
    with respx.mock:
        respx.get(FORGE_MAVEN_METADATA_URL).mock(
            return_value=httpx.Response(200, text=_LEGACY_FORGE_METADATA_XML)
        )
        async with httpx.AsyncClient() as client:
            versions = await get_forge_versions(client, "1.7.10")

    assert versions == ["10.13.4.1614-1.7.10", "10.13.4.1558-1.7.10", "10.13.2.1291"]


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
async def test_get_forge_recommended_version_prefers_recommended_over_latest():
    with respx.mock:
        respx.get(FORGE_PROMOTIONS_URL).mock(
            return_value=httpx.Response(
                200,
                json={"promos": {"1.21.1-recommended": "47.3.0", "1.21.1-latest": "47.4.0"}},
            )
        )
        async with httpx.AsyncClient() as client:
            recommended = await get_forge_recommended_version(client, "1.21.1")

    assert recommended == "47.3.0"


@pytest.mark.asyncio
async def test_get_forge_recommended_version_falls_back_to_latest():
    with respx.mock:
        respx.get(FORGE_PROMOTIONS_URL).mock(
            return_value=httpx.Response(200, json={"promos": {"1.21.1-latest": "47.4.0"}})
        )
        async with httpx.AsyncClient() as client:
            recommended = await get_forge_recommended_version(client, "1.21.1")

    assert recommended == "47.4.0"


@pytest.mark.asyncio
async def test_get_forge_recommended_version_none_on_network_error():
    with respx.mock:
        respx.get(FORGE_PROMOTIONS_URL).mock(return_value=httpx.Response(500))
        async with httpx.AsyncClient() as client:
            recommended = await get_forge_recommended_version(client, "1.21.1")

    assert recommended is None


@pytest.mark.asyncio
async def test_get_recommended_loader_version_fabric_picks_first_stable():
    with respx.mock:
        respx.get(FABRIC_LOADER_URL).mock(
            return_value=httpx.Response(
                200,
                json=[
                    {"version": "0.17.0-beta.1", "stable": False},
                    {"version": "0.16.5", "stable": True},
                    {"version": "0.16.4", "stable": True},
                ],
            )
        )
        async with httpx.AsyncClient() as client:
            recommended = await get_recommended_loader_version(client, Loader.FABRIC, "1.21.1")

    assert recommended == "0.16.5"


@pytest.mark.asyncio
async def test_get_recommended_loader_version_quilt_picks_first_stable():
    with respx.mock:
        respx.get(QUILT_LOADER_URL).mock(
            return_value=httpx.Response(200, json=[{"version": "0.27.0", "stable": True}])
        )
        async with httpx.AsyncClient() as client:
            recommended = await get_recommended_loader_version(client, Loader.QUILT, "1.21.1")

    assert recommended == "0.27.0"


@pytest.mark.asyncio
async def test_get_recommended_loader_version_neoforge_returns_none():
    async with httpx.AsyncClient() as client:
        recommended = await get_recommended_loader_version(client, Loader.NEOFORGE, "1.21.1")

    assert recommended is None


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
