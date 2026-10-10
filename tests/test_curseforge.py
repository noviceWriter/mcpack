import httpx
import pytest
import respx

from mcpack.models import Loader
from mcpack.sources.base import SourceAPIError
from mcpack.sources.curseforge import BASE_URL, CurseForgeClient, CurseForgeConfigError


def test_missing_api_key_raises():
    with pytest.raises(CurseForgeConfigError):
        CurseForgeClient("")


@pytest.mark.asyncio
async def test_search_parses_mods():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/mods/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 238222,
                            "slug": "jei",
                            "name": "Just Enough Items",
                            "summary": "Tarif görüntüleyici",
                            "logo": {"thumbnailUrl": "https://example.com/icon.png"},
                            "downloadCount": 5000,
                            "categories": [{"name": "Utility"}],
                        }
                    ]
                },
            )
        )
        client = CurseForgeClient("fake-key")
        results = await client.search("jei", game_version="1.21.1", loader=Loader.FABRIC)
        await client.aclose()

    assert len(results) == 1
    assert results[0].project_id == "238222"
    assert results[0].title == "Just Enough Items"


@pytest.mark.asyncio
async def test_get_versions_skips_files_without_download_url():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/mods/238222/files").mock(
            return_value=httpx.Response(
                200,
                json={
                    "data": [
                        {
                            "id": 1,
                            "modId": 238222,
                            "displayName": "jei-1.21.1.jar",
                            "fileName": "jei-1.21.1.jar",
                            "downloadUrl": None,
                            "gameVersions": ["1.21.1"],
                            "hashes": [{"value": "abc", "algo": 1}],
                            "dependencies": [],
                            "fileLength": 100,
                        },
                        {
                            "id": 2,
                            "modId": 238222,
                            "displayName": "jei-1.21.1-v2.jar",
                            "fileName": "jei-1.21.1-v2.jar",
                            "downloadUrl": "https://edge.forgecdn.net/jei.jar",
                            "gameVersions": ["1.21.1"],
                            "hashes": [{"value": "def", "algo": 1}],
                            "dependencies": [{"modId": 111, "relationType": 3}],
                            "fileLength": 200,
                        },
                    ]
                },
            )
        )
        client = CurseForgeClient("fake-key")
        versions = await client.get_versions("238222", game_version="1.21.1", loader=Loader.FABRIC)
        await client.aclose()

    assert len(versions) == 1
    assert versions[0].version_id == "2"
    assert versions[0].dependencies[0].project_id == "111"
    assert versions[0].dependencies[0].dependency_type == "required"


@pytest.mark.asyncio
async def test_cloudfront_block_page_gets_cdn_hint():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/mods/1").mock(
            return_value=httpx.Response(
                403,
                headers={"x-cache": "Error from cloudfront", "x-amz-cf-id": "abc123"},
                text="<H1>403 ERROR</H1><H2>The request could not be satisfied.</H2>",
            )
        )
        client = CurseForgeClient("fake-key")
        with pytest.raises(SourceAPIError, match="CDN.*abc123"):
            await client.get_project("1")
        await client.aclose()


@pytest.mark.asyncio
async def test_plain_403_gets_api_key_hint():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/mods/search").mock(return_value=httpx.Response(403))
        mock.get("/v1/mods/1").mock(return_value=httpx.Response(403))
        client = CurseForgeClient("fake-key")
        with pytest.raises(SourceAPIError, match="API key"):
            await client.get_project("1")
        await client.aclose()


@pytest.mark.asyncio
async def test_empty_cloudfront_403_blames_key_not_cdn():
    # Origin'in boş 403'ü de "Error from cloudfront" başlığıyla gelir — bu CDN engeli değil.
    valid_looking = "$2a$10$" + "a" * 53
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/mods/search").mock(return_value=httpx.Response(403))
        mock.get("/v1/mods/1").mock(
            return_value=httpx.Response(403, headers={"x-cache": "Error from cloudfront"})
        )
        client = CurseForgeClient(valid_looking)
        with pytest.raises(SourceAPIError, match="iptal edilmiş") as exc_info:
            await client.get_project("1")
        assert "CDN" not in str(exc_info.value)
        await client.aclose()


@pytest.mark.asyncio
async def test_malformed_key_gets_format_hint():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/mods/search").mock(return_value=httpx.Response(403))
        mock.get("/v1/mods/1").mock(return_value=httpx.Response(403))
        client = CurseForgeClient("short-key")
        with pytest.raises(SourceAPIError, match="biçimi beklenene"):
            await client.get_project("1")
        await client.aclose()


@pytest.mark.asyncio
async def test_restricted_key_reports_missing_permission():
    # Arama çalışıyor ama mod detayı 403 → key geçerli, yetki kısıtlı.
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/v1/mods/search").mock(return_value=httpx.Response(200, json={"data": []}))
        mock.get("/v1/mods/1").mock(return_value=httpx.Response(403))
        client = CurseForgeClient("fake-key")
        with pytest.raises(SourceAPIError, match="geçerli.*yetkisi yok"):
            await client.get_project("1")
        await client.aclose()
