import httpx
import pytest
import respx

from mcpack.models import ContentKind, EnvRequirement, Loader, ModSourceType
from mcpack.packs import PackManager
from mcpack.packs.updates import check_updates
from mcpack.sources.base import ModDetail, ModVersion, VersionDependency, VersionFile
from mcpack.sources.modrinth import BASE_URL, ModrinthClient


def _v(source, pid, vid, fname, sha1=None, deps=()):
    return ModVersion(
        source=source, version_id=vid, project_id=pid, name=vid,
        files=[VersionFile(file_name=fname, url=f"https://x/{fname}", sha1=sha1)],
        dependencies=[VersionDependency(project_id=d) for d in deps],
    )


class FakeSource:
    def __init__(self, versions):
        self.versions = versions
        self.calls = []

    async def get_versions(self, project_id, *, game_version=None, loader=None):
        self.calls.append(project_id)
        return self.versions.get(project_id, [])


@pytest.fixture
def setup(tmp_path):
    m = PackManager(tmp_path)
    pack = m.create_pack(name="P", minecraft="1.21.1", loader=Loader.FABRIC, loader_version="0.16.5")
    detail = ModDetail(source=ModSourceType.MODRINTH, project_id="sodium", slug="sodium", title="Sodium", description="")
    m.add_mod(pack, _v(ModSourceType.MODRINTH, "sodium", "v1", "sodium-1.jar", sha1="aaa"), detail)
    cf_detail = ModDetail(source=ModSourceType.CURSEFORGE, project_id="123", slug="jei", title="JEI", description="")
    m.add_mod(pack, _v(ModSourceType.CURSEFORGE, "123", "1000", "jei-1.jar"), cf_detail)
    return m, pack


async def test_finds_updates_from_both_sources(setup):
    m, pack = setup
    modrinth = FakeSource({"sodium": [_v(ModSourceType.MODRINTH, "sodium", "v2", "sodium-2.jar"), _v(ModSourceType.MODRINTH, "sodium", "v1", "sodium-1.jar")]})
    cf = FakeSource({"123": [_v(ModSourceType.CURSEFORGE, "123", "999", "old.jar"), _v(ModSourceType.CURSEFORGE, "123", "1005", "jei-2.jar")]})
    updates, errors = await check_updates(pack, modrinth=modrinth, curseforge=cf)
    assert errors == []
    assert {(u.project_id, u.new_file) for u in updates} == {("sodium", "sodium-2.jar"), ("123", "jei-2.jar")}


async def test_up_to_date_mods_report_nothing(setup):
    m, pack = setup
    modrinth = FakeSource({"sodium": [_v(ModSourceType.MODRINTH, "sodium", "v1", "sodium-1.jar")]})
    cf = FakeSource({"123": [_v(ModSourceType.CURSEFORGE, "123", "1000", "jei-1.jar")]})
    updates, _errors = await check_updates(pack, modrinth=modrinth, curseforge=cf)
    assert updates == []


async def test_missing_curseforge_key_is_reported_not_fatal(setup):
    m, pack = setup
    modrinth = FakeSource({"sodium": []})
    updates, errors = await check_updates(pack, modrinth=modrinth, curseforge=None)
    assert updates == [] and len(errors) == 1 and "JEI" in errors[0]


async def test_modrinth_bulk_endpoint_used_single_request(setup):
    m, pack = setup
    new = {
        "id": "v2", "project_id": "sodium", "name": "v2", "game_versions": ["1.21.1"], "loaders": ["fabric"],
        "files": [{"filename": "sodium-2.jar", "url": "https://x/s2", "hashes": {"sha1": "bbb"}, "primary": True}],
        "dependencies": [],
    }
    with respx.mock:
        route = respx.post(f"{BASE_URL}/version_files/update").mock(return_value=httpx.Response(200, json={"aaa": new}))
        client = ModrinthClient()
        try:
            updates, _ = await check_updates(pack, modrinth=client, curseforge=FakeSource({}))
        finally:
            await client.aclose()
    assert route.call_count == 1
    body = route.calls[0].request.read()
    assert b'"aaa"' in body and b'"fabric"' in body and b'"1.21.1"' in body
    assert [u.new_file for u in updates] == ["sodium-2.jar"]


def test_update_mod_preserves_manual_env_and_name(setup):
    m, pack = setup
    m.set_mod_env(pack, "sodium", client=EnvRequirement.REQUIRED, server=EnvRequirement.UNSUPPORTED)
    entry = m.update_mod(pack, _v(ModSourceType.MODRINTH, "sodium", "v2", "sodium-2.jar", deps=["fabric-api"]))
    assert entry.file_name == "sodium-2.jar"
    assert entry.name == "Sodium"
    assert entry.env.server == EnvRequirement.UNSUPPORTED
    assert entry.dependencies == ["fabric-api"]
    assert [x.project_id for x in m.load(pack.id).mods].index("sodium") == 0  # sıra korunur


def test_update_content_download(tmp_path):
    m = PackManager(tmp_path)
    pack = m.create_pack(name="P", minecraft="1.21.1", loader=Loader.FABRIC, loader_version="0.16.5")
    d = ModDetail(source=ModSourceType.MODRINTH, project_id="bsl", slug="bsl", title="BSL", description="")
    m.add_content_download(pack, ContentKind.SHADERPACK, _v(ModSourceType.MODRINTH, "bsl", "v1", "bsl1.zip"), d)
    fresh = m.update_content_download(pack, ContentKind.SHADERPACK, _v(ModSourceType.MODRINTH, "bsl", "v2", "bsl2.zip"))
    assert fresh.file_name == "bsl2.zip" and fresh.name == "BSL"
