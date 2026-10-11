import json
import zipfile
from pathlib import Path

import httpx
import pytest

from mcpack.export.mrpack import MrpackExporter
from mcpack.importers import ModpackImportError, detect_format, import_modpack
from mcpack.models import ContentKind, EnvRequirement, Loader, ModSourceType
from mcpack.packs import PackManager
from mcpack.sources.base import ModDetail, ModVersion, VersionDependency, VersionFile


def _version(pid, vid, fname, sha1, deps=()):
    return ModVersion(
        source=ModSourceType.MODRINTH, version_id=vid, project_id=pid, name=vid,
        files=[VersionFile(file_name=fname, url=f"https://cdn.modrinth.com/data/{pid}/versions/{vid}/{fname}", sha1=sha1, sha512="5" * 128)],
        dependencies=[VersionDependency(project_id=d) for d in deps],
    )


class FakeModrinth:
    def __init__(self, versions: dict[str, ModVersion]):
        self.versions = versions

    async def versions_for_hashes(self, hashes):
        return {h: self.versions[h] for h in hashes if h in self.versions}

    async def get_projects(self, ids):
        return {i: ModDetail(source=ModSourceType.MODRINTH, project_id=i, slug=i, title=i.title(), description="",
                             server_side=EnvRequirement.UNSUPPORTED if i == "sodium" else EnvRequirement.REQUIRED)
                for i in ids}


def _write_mrpack(path: Path, index: dict, extra: dict[str, bytes] | None = None) -> Path:
    with zipfile.ZipFile(path, "w") as zf:
        zf.writestr("modrinth.index.json", json.dumps(index))
        for name, data in (extra or {}).items():
            zf.writestr(name, data)
    return path


INDEX = {
    "formatVersion": 1, "game": "minecraft", "versionId": "2.0.0", "name": "Imported", "summary": "hi",
    "dependencies": {"minecraft": "1.21.1", "fabric-loader": "0.16.5"},
    "files": [
        {"path": "mods/sodium.jar", "hashes": {"sha1": "a" * 40, "sha512": "5" * 128},
         "env": {"client": "required", "server": "unsupported"}, "downloads": ["https://cdn.modrinth.com/x/sodium.jar"], "fileSize": 10},
        {"path": "mods/custom.jar", "hashes": {"sha1": "c" * 40, "sha512": "6" * 128},
         "downloads": ["https://github.com/me/custom/releases/custom.jar"], "fileSize": 5},
        {"path": "resourcepacks/faithful.zip", "hashes": {"sha1": "f" * 40},
         "downloads": ["https://cdn.modrinth.com/x/faithful.zip"]},
        {"path": "../../evil.jar", "hashes": {"sha1": "e" * 40}, "downloads": ["https://x/evil.jar"]},
    ],
}


async def test_mrpack_import_maps_everything(tmp_path):
    src = _write_mrpack(tmp_path / "p.mrpack", INDEX, {
        "overrides/config/sodium.json": b"{}",
        "overrides/saves/MyWorld/level.dat": b"lvl",
        "overrides/../../escape.txt": b"nope",
        "client-overrides/options.txt": b"fov:90",
    })
    manager = PackManager(tmp_path / "packs")
    modrinth = FakeModrinth({
        "a" * 40: _version("sodium", "v1", "sodium.jar", "a" * 40, deps=["fabric-api"]),
        "f" * 40: _version("faithful", "r1", "faithful.zip", "f" * 40),
    })
    result = await import_modpack(manager, src, modrinth=modrinth, curseforge=None)
    pack = manager.load(result.pack.id)

    assert (pack.name, pack.minecraft, pack.loader, pack.loader_version, pack.version) == ("Imported", "1.21.1", Loader.FABRIC, "0.16.5", "2.0.0")
    sodium = pack.find_mod("sodium")
    assert sodium.source == ModSourceType.MODRINTH and sodium.name == "Sodium" and sodium.version_id == "v1"
    assert sodium.env.server == EnvRequirement.UNSUPPORTED  # pack'teki env korunur
    assert sodium.dependencies == ["fabric-api"]
    custom = next(m for m in pack.mods if m.file_name == "custom.jar")
    assert custom.source == ModSourceType.URL and custom.hashes.sha1 == "c" * 40
    assert result.url_sourced == ["custom.jar"]
    assert [c.project_id for c in pack.content_downloads_of(ContentKind.RESOURCEPACK)] == ["faithful"]
    assert [w.name for w in pack.content_of(ContentKind.WORLD)] == ["MyWorld"]
    assert any("evil" in s for s in result.skipped)
    overrides = manager.content_root(pack) / "overrides"
    assert (overrides / "config" / "sodium.json").exists() and (overrides / "options.txt").exists()
    assert not (overrides / "saves").exists()
    assert sorted(pack.overrides.include) == ["config", "options.txt"]
    assert not (tmp_path / "escape.txt").exists() and not (tmp_path / "packs" / "escape.txt").exists()


async def test_round_trip_with_our_own_exporter(tmp_path):
    manager = PackManager(tmp_path / "packs")
    pack = manager.create_pack(name="RT", minecraft="1.21.1", loader=Loader.QUILT, loader_version="0.26.0")
    detail = ModDetail(source=ModSourceType.MODRINTH, project_id="lithium", slug="lithium", title="Lithium", description="")
    manager.add_mod(pack, _version("lithium", "l1", "lithium.jar", "b" * 40), detail)
    out = tmp_path / "rt.mrpack"
    async with httpx.AsyncClient() as client:
        await MrpackExporter().export(pack, source_dir=tmp_path, output_path=out, cache_dir=tmp_path / "c",
                                      content_root=manager.content_root(pack), client=client)
    assert detect_format(out) == "mrpack"
    result = await import_modpack(manager, out, modrinth=FakeModrinth({"b" * 40: _version("lithium", "l1", "lithium.jar", "b" * 40)}), curseforge=None)
    assert result.pack.id != pack.id
    assert [m.project_id for m in result.pack.mods] == ["lithium"]
    assert result.pack.loader == Loader.QUILT


class FakeCF:
    async def get_file(self, pid, fid):
        return ModVersion(source=ModSourceType.CURSEFORGE, version_id=fid, project_id=pid, name=fid,
                          files=[VersionFile(file_name=f"{pid}.jar", url=f"https://edge.forgecdn.net/{fid}", sha1="d" * 40)])

    async def get_project(self, pid):
        return ModDetail(source=ModSourceType.CURSEFORGE, project_id=pid, slug=f"s{pid}", title=f"P{pid}", description="",
                         class_id=12 if pid == "200" else 6)


async def test_curseforge_zip_import(tmp_path):
    manifest = {
        "minecraft": {"version": "1.20.1", "modLoaders": [{"id": "forge-47.2.0", "primary": True}]},
        "manifestType": "minecraftModpack", "name": "CF Pack", "version": "3", "author": "me",
        "files": [{"projectID": 100, "fileID": 1, "required": True}, {"projectID": 200, "fileID": 2, "required": True}],
        "overrides": "overrides",
    }
    src = tmp_path / "cf.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("manifest.json", json.dumps(manifest))
        zf.writestr("overrides/kubejs/startup.js", "x")
    manager = PackManager(tmp_path / "packs")
    result = await import_modpack(manager, src, modrinth=None, curseforge=FakeCF())
    pack = result.pack
    assert (pack.loader, pack.loader_version, pack.minecraft, pack.author) == (Loader.FORGE, "47.2.0", "1.20.1", "me")
    assert [m.project_id for m in pack.mods] == ["100"]
    assert [c.project_id for c in pack.content_downloads_of(ContentKind.RESOURCEPACK)] == ["200"]
    assert pack.overrides.include == ["kubejs"]


async def test_curseforge_without_key_fails_and_leaves_no_pack(tmp_path):
    src = tmp_path / "cf.zip"
    with zipfile.ZipFile(src, "w") as zf:
        zf.writestr("manifest.json", json.dumps({"minecraft": {"version": "1.20.1"}, "files": []}))
    manager = PackManager(tmp_path / "packs")
    with pytest.raises(ModpackImportError):
        await import_modpack(manager, src, modrinth=None, curseforge=None)
    assert manager.list_packs() == []


async def test_failure_midway_rolls_back(tmp_path):
    class Boom(FakeModrinth):
        async def get_projects(self, ids):
            raise RuntimeError("ağ yok")

    src = _write_mrpack(tmp_path / "p.mrpack", INDEX, {"overrides/saves/W/level.dat": b"x"})
    manager = PackManager(tmp_path / "packs")

    async def broken_absorb(*_a, **_k):
        raise RuntimeError("disk")

    import mcpack.importers as imp
    original = imp._absorb_overrides
    imp._absorb_overrides = broken_absorb
    try:
        with pytest.raises(RuntimeError):
            await import_modpack(manager, src, modrinth=Boom({}), curseforge=None)
    finally:
        imp._absorb_overrides = original
    assert manager.list_packs() == []
    assert not any((tmp_path / "packs" / "content").glob("*")) if (tmp_path / "packs" / "content").exists() else True


def test_detect_format_rejects_random_zip(tmp_path):
    p = tmp_path / "x.zip"
    with zipfile.ZipFile(p, "w") as zf:
        zf.writestr("readme.txt", "hi")
    assert detect_format(p) is None
    (tmp_path / "not.zip").write_text("nope")
    assert detect_format(tmp_path / "not.zip") is None
