import pytest

from mcpack.models import ModSourceType
from mcpack.sources.base import SearchResult
from mcpack.sources.combined import search_all


class _FakeSource:
    def __init__(self, source: ModSourceType, results: list[SearchResult]) -> None:
        self.source = source
        self._results = results

    async def search(self, query, *, game_version=None, loader=None, limit=20, offset=0):
        return self._results


def _result(source: ModSourceType, project_id: str, title: str) -> SearchResult:
    return SearchResult(source=source, project_id=project_id, slug=title.lower(), title=title, description="")


@pytest.mark.asyncio
async def test_prefers_modrinth_on_duplicate_title():
    modrinth = _FakeSource(ModSourceType.MODRINTH, [_result(ModSourceType.MODRINTH, "mr1", "Sodium")])
    curseforge = _FakeSource(ModSourceType.CURSEFORGE, [_result(ModSourceType.CURSEFORGE, "cf1", "Sodium")])

    results = await search_all(
        "sodium", modrinth=modrinth, curseforge=curseforge, prefer_modrinth=True
    )

    assert len(results) == 1
    assert results[0].source == ModSourceType.MODRINTH
    assert results[0].project_id == "mr1"


@pytest.mark.asyncio
async def test_prefers_curseforge_when_configured():
    modrinth = _FakeSource(ModSourceType.MODRINTH, [_result(ModSourceType.MODRINTH, "mr1", "Sodium")])
    curseforge = _FakeSource(ModSourceType.CURSEFORGE, [_result(ModSourceType.CURSEFORGE, "cf1", "Sodium")])

    results = await search_all(
        "sodium", modrinth=modrinth, curseforge=curseforge, prefer_modrinth=False
    )

    assert results[0].source == ModSourceType.CURSEFORGE
    assert results[0].project_id == "cf1"


@pytest.mark.asyncio
async def test_distinct_titles_both_kept():
    modrinth = _FakeSource(ModSourceType.MODRINTH, [_result(ModSourceType.MODRINTH, "mr1", "Sodium")])
    curseforge = _FakeSource(ModSourceType.CURSEFORGE, [_result(ModSourceType.CURSEFORGE, "cf1", "Iris")])

    results = await search_all("s", modrinth=modrinth, curseforge=curseforge)

    assert {r.project_id for r in results} == {"mr1", "cf1"}


@pytest.mark.asyncio
async def test_no_curseforge_client_returns_modrinth_only():
    modrinth = _FakeSource(ModSourceType.MODRINTH, [_result(ModSourceType.MODRINTH, "mr1", "Sodium")])

    results = await search_all("sodium", modrinth=modrinth, curseforge=None)

    assert len(results) == 1
    assert results[0].project_id == "mr1"
