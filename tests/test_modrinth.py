import httpx
import pytest
import respx

from mcpack.models import Loader
from mcpack.sources.base import SourceAPIError
from mcpack.sources.modrinth import BASE_URL, ModrinthClient


@pytest.mark.asyncio
async def test_search_parses_hits():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/search").mock(
            return_value=httpx.Response(
                200,
                json={
                    "hits": [
                        {
                            "project_id": "AANobbMI",
                            "slug": "sodium",
                            "title": "Sodium",
                            "description": "Performans modu",
                            "icon_url": None,
                            "downloads": 1000,
                            "categories": ["optimization"],
                        }
                    ]
                },
            )
        )
        client = ModrinthClient()
        results = await client.search("sodium", game_version="1.21.1", loader=Loader.FABRIC)
        await client.aclose()

    assert len(results) == 1
    assert results[0].project_id == "AANobbMI"
    assert results[0].title == "Sodium"


@pytest.mark.asyncio
async def test_get_versions_parses_files_and_dependencies():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/project/AANobbMI/version").mock(
            return_value=httpx.Response(
                200,
                json=[
                    {
                        "id": "ver1",
                        "project_id": "AANobbMI",
                        "name": "0.6.0",
                        "game_versions": ["1.21.1"],
                        "loaders": ["fabric"],
                        "dependencies": [
                            {
                                "project_id": "P7dR8mSH",
                                "version_id": None,
                                "dependency_type": "required",
                            }
                        ],
                        "files": [
                            {
                                "filename": "sodium-0.6.0.jar",
                                "url": "https://cdn.modrinth.com/sodium-0.6.0.jar",
                                "hashes": {"sha1": "abc", "sha512": "def"},
                                "size": 12345,
                                "primary": True,
                            }
                        ],
                    }
                ],
            )
        )
        client = ModrinthClient()
        versions = await client.get_versions("AANobbMI", game_version="1.21.1", loader=Loader.FABRIC)
        await client.aclose()

    assert len(versions) == 1
    v = versions[0]
    assert v.primary_file.file_name == "sodium-0.6.0.jar"
    assert v.dependencies[0].project_id == "P7dR8mSH"
    assert v.dependencies[0].dependency_type == "required"


@pytest.mark.asyncio
async def test_http_error_wrapped_with_turkish_message():
    with respx.mock(base_url=BASE_URL) as mock:
        mock.get("/project/doesnotexist").mock(return_value=httpx.Response(404))
        client = ModrinthClient()
        with pytest.raises(SourceAPIError, match="bulunamadı"):
            await client.get_project("doesnotexist")
        await client.aclose()
