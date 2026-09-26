"""Shader/dünya/datapack/görüntü paketi ekleme testleri.

Kullanıcı isteği: shader/resourcepack/datapack "yine mod yükler gibi"
Modrinth/CurseForge'ta aranıp eklenebilsin (bkz. PackManager.add_content_download);
dünya indirilebilir bir kaynak olmadığı için diskten seçilip pack'e kopyalanır
(bkz. PackManager.add_content). Server pack oluştururken yüklü dünyalardan biri
seçilip "world/" adıyla dahil edilebilsin.
"""

import zipfile
from pathlib import Path

import httpx
import pytest
import respx

from mcpack.export.base import collect_content_download_files, collect_world_files
from mcpack.export.curseforge import CurseForgeExporter
from mcpack.export.mrpack import MrpackExporter
from mcpack.export.server import ServerPackExporter
from mcpack.models import ContentKind, Loader, ModSourceType, Pack
from mcpack.packs.manager import PackManager
from mcpack.sources.base import ModDetail, ModVersion, VersionFile


def _make_pack(**kwargs) -> Pack:
    defaults = dict(name="Test", minecraft="1.21.1", loader=Loader.VANILLA)
    defaults.update(kwargs)
    return Pack(**defaults)


def _make_version(
    *, source=ModSourceType.MODRINTH, project_id="p1", version_id="1", url: str, file_name: str
) -> ModVersion:
    return ModVersion(
        source=source,
        version_id=version_id,
        project_id=project_id,
        name="v1",
        files=[VersionFile(file_name=file_name, url=url, primary=True)],
    )


# -- Dünya: yerel dosya/klasör kopyalama (indirilebilir bir kaynak değil) ----


def test_add_content_copies_world_folder_and_records_entry(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack()

    world_dir = tmp_path / "MyWorld"
    (world_dir / "region").mkdir(parents=True)
    (world_dir / "level.dat").write_bytes(b"leveldata")
    (world_dir / "region" / "r.0.0.mca").write_bytes(b"regiondata")

    entry = manager.add_content(pack, ContentKind.WORLD, world_dir)

    assert entry.is_dir
    assert pack.content == [entry]
    stored = manager.content_root(pack) / entry.stored_path
    assert (stored / "level.dat").read_bytes() == b"leveldata"
    assert (stored / "region" / "r.0.0.mca").read_bytes() == b"regiondata"

    # kaynak klasör silinse bile pack'teki kopya duruyor olmalı.
    import shutil

    shutil.rmtree(world_dir)
    assert stored.exists()


def test_add_content_same_name_replaces_existing(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack()

    world_dir = tmp_path / "World"
    world_dir.mkdir()
    (world_dir / "level.dat").write_bytes(b"v1")
    manager.add_content(pack, ContentKind.WORLD, world_dir)

    (world_dir / "level.dat").write_bytes(b"v2")
    manager.add_content(pack, ContentKind.WORLD, world_dir)

    assert len(pack.content_of(ContentKind.WORLD)) == 1
    entry = pack.content_of(ContentKind.WORLD)[0]
    assert (manager.content_root(pack) / entry.stored_path / "level.dat").read_bytes() == b"v2"


def test_remove_content_deletes_folder_and_entry(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack()

    world_dir = tmp_path / "World"
    world_dir.mkdir()
    (world_dir / "level.dat").write_bytes(b"data")
    entry = manager.add_content(pack, ContentKind.WORLD, world_dir)
    stored = manager.content_root(pack) / entry.stored_path

    manager.remove_content(pack, ContentKind.WORLD, "World")

    assert pack.content == []
    assert not stored.exists()


def test_collect_world_files_without_selection_uses_saves_and_own_name(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack()

    world_dir = tmp_path / "MyWorld"
    world_dir.mkdir()
    (world_dir / "level.dat").write_bytes(b"x")
    manager.add_content(pack, ContentKind.WORLD, world_dir)

    files = collect_world_files(pack, manager.content_root(pack))
    assert files == [(manager.content_root(pack) / "worlds" / "MyWorld" / "level.dat", "saves/MyWorld/level.dat")]


def test_collect_world_files_with_selection_renames_to_world(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack()

    for name in ("WorldA", "WorldB"):
        world_dir = tmp_path / name
        world_dir.mkdir()
        (world_dir / "level.dat").write_bytes(name.encode())
        manager.add_content(pack, ContentKind.WORLD, world_dir)

    files = collect_world_files(pack, manager.content_root(pack), selected_world="WorldB")
    assert len(files) == 1
    real_path, arc_rel = files[0]
    assert arc_rel == "world/level.dat"
    assert real_path.read_bytes() == b"WorldB"


# -- Shader/Resourcepack/Datapack: Modrinth/CurseForge'tan arayıp ekleme -----


def test_add_content_download_records_entry(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack()

    version = _make_version(url="https://cdn.modrinth.com/shader.zip", file_name="shader.zip")
    detail = ModDetail(
        source=ModSourceType.MODRINTH, project_id="p1", slug="my-shader", title="My Shader", description=""
    )

    entry = manager.add_content_download(pack, ContentKind.SHADERPACK, version, detail)

    assert entry.kind == ContentKind.SHADERPACK
    assert entry.file_name == "shader.zip"
    assert entry.download_url == "https://cdn.modrinth.com/shader.zip"
    assert pack.content_downloads == [entry]


def test_add_content_download_same_project_replaces_existing(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack()

    v1 = _make_version(url="https://cdn.modrinth.com/shader-v1.zip", file_name="shader-v1.zip")
    manager.add_content_download(pack, ContentKind.SHADERPACK, v1)

    v2 = _make_version(url="https://cdn.modrinth.com/shader-v2.zip", file_name="shader-v2.zip")
    manager.add_content_download(pack, ContentKind.SHADERPACK, v2)

    assert len(pack.content_downloads_of(ContentKind.SHADERPACK)) == 1
    assert pack.content_downloads_of(ContentKind.SHADERPACK)[0].file_name == "shader-v2.zip"


def test_remove_content_download(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack()

    version = _make_version(url="https://cdn.modrinth.com/shader.zip", file_name="shader.zip")
    manager.add_content_download(pack, ContentKind.SHADERPACK, version)

    manager.remove_content_download(pack, ContentKind.SHADERPACK, "p1")

    assert pack.content_downloads == []


def test_collect_content_download_files_maps_kind_to_archive_dir(tmp_path: Path):
    pack = _make_pack()
    manager = PackManager(tmp_path / "packs")
    shader_version = _make_version(url="https://x/shader.zip", file_name="shader.zip")
    rp_version = _make_version(url="https://x/rp.zip", file_name="rp.zip", project_id="p2")
    shader_entry = manager.add_content_download(pack, ContentKind.SHADERPACK, shader_version)
    rp_entry = manager.add_content_download(pack, ContentKind.RESOURCEPACK, rp_version)

    fake_shader_path = tmp_path / "shader.zip"
    fake_rp_path = tmp_path / "rp.zip"
    downloaded = {shader_entry.project_id: fake_shader_path, rp_entry.project_id: fake_rp_path}

    files = collect_content_download_files(pack.content_downloads, downloaded)
    arc_names = sorted(rel for _, rel in files)
    assert arc_names == ["resourcepacks/rp.zip", "shaderpacks/shader.zip"]


# -- Export entegrasyonu ------------------------------------------------------


@pytest.mark.asyncio
async def test_mrpack_export_embeds_content_downloads_and_world(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack(loader=Loader.FABRIC, loader_version="0.16.5")

    world_dir = tmp_path / "MyWorld"
    world_dir.mkdir()
    (world_dir / "level.dat").write_bytes(b"worlddata")
    manager.add_content(pack, ContentKind.WORLD, world_dir)

    shader_version = _make_version(url="https://cdn.modrinth.com/shader.zip", file_name="shader.zip")
    manager.add_content_download(pack, ContentKind.SHADERPACK, shader_version)

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_path = tmp_path / "out.mrpack"

    with respx.mock as mock:
        mock.get("https://cdn.modrinth.com/shader.zip").mock(
            return_value=httpx.Response(200, content=b"fake-shader-bytes")
        )
        async with httpx.AsyncClient() as client:
            await MrpackExporter().export(
                pack,
                source_dir=source_dir,
                output_path=output_path,
                cache_dir=tmp_path / "cache",
                content_root=manager.content_root(pack),
                client=client,
            )

    with zipfile.ZipFile(output_path) as zf:
        names = set(zf.namelist())
        assert "overrides/shaderpacks/shader.zip" in names
        assert "overrides/saves/MyWorld/level.dat" in names


@pytest.mark.asyncio
async def test_curseforge_export_references_cf_content_and_embeds_others(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack(loader=Loader.FABRIC, loader_version="0.16.5")

    cf_shader = _make_version(
        source=ModSourceType.CURSEFORGE, url="https://edge.forgecdn.net/shader.zip",
        file_name="shader.zip", project_id="1001", version_id="2002",
    )
    manager.add_content_download(pack, ContentKind.SHADERPACK, cf_shader)

    mr_resourcepack = _make_version(url="https://cdn.modrinth.com/rp.zip", file_name="rp.zip", project_id="p2")
    manager.add_content_download(pack, ContentKind.RESOURCEPACK, mr_resourcepack)

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_path = tmp_path / "out.zip"

    with respx.mock as mock:
        mock.get("https://cdn.modrinth.com/rp.zip").mock(
            return_value=httpx.Response(200, content=b"fake-rp-bytes")
        )
        async with httpx.AsyncClient() as client:
            await CurseForgeExporter().export(
                pack,
                source_dir=source_dir,
                output_path=output_path,
                cache_dir=tmp_path / "cache",
                content_root=manager.content_root(pack),
                client=client,
            )

    with zipfile.ZipFile(output_path) as zf:
        names = set(zf.namelist())
        assert "overrides/resourcepacks/rp.zip" in names
        assert "overrides/shaderpacks/shader.zip" not in names  # CF-kaynaklı, manifest'te referans edildi

        import json

        manifest = json.loads(zf.read("manifest.json"))
        assert {"projectID": 1001, "fileID": 2002, "required": True} in manifest["files"]


@pytest.mark.asyncio
async def test_server_pack_includes_selected_world_and_datapacks_excludes_shaders(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack(loader=Loader.FABRIC, loader_version="0.16.5")

    world_dir = tmp_path / "MyWorld"
    world_dir.mkdir()
    (world_dir / "level.dat").write_bytes(b"worlddata")
    manager.add_content(pack, ContentKind.WORLD, world_dir)

    shader_version = _make_version(url="https://cdn.modrinth.com/shader.zip", file_name="shader.zip")
    manager.add_content_download(pack, ContentKind.SHADERPACK, shader_version)

    datapack_version = _make_version(
        url="https://cdn.modrinth.com/dp.zip", file_name="dp.zip", project_id="p2"
    )
    manager.add_content_download(pack, ContentKind.DATAPACK, datapack_version)

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_path = tmp_path / "server.zip"

    with respx.mock as mock:
        mock.get("https://cdn.modrinth.com/dp.zip").mock(
            return_value=httpx.Response(200, content=b"fake-dp-bytes")
        )
        async with httpx.AsyncClient() as client:
            await ServerPackExporter().export(
                pack,
                source_dir=source_dir,
                output_path=output_path,
                cache_dir=tmp_path / "cache",
                content_root=manager.content_root(pack),
                client=client,
                selected_world="MyWorld",
            )

    with zipfile.ZipFile(output_path) as zf:
        names = set(zf.namelist())
        assert "world/level.dat" in names
        assert "datapacks/dp.zip" in names
        assert not any(n.startswith("shaderpacks/") for n in names)


@pytest.mark.asyncio
async def test_server_pack_without_selected_world_has_no_world_folder(tmp_path: Path):
    manager = PackManager(tmp_path / "packs")
    pack = _make_pack(loader=Loader.FABRIC, loader_version="0.16.5")

    world_dir = tmp_path / "MyWorld"
    world_dir.mkdir()
    (world_dir / "level.dat").write_bytes(b"worlddata")
    manager.add_content(pack, ContentKind.WORLD, world_dir)

    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_path = tmp_path / "server.zip"

    async with httpx.AsyncClient() as client:
        await ServerPackExporter().export(
            pack,
            source_dir=source_dir,
            output_path=output_path,
            cache_dir=tmp_path / "cache",
            content_root=manager.content_root(pack),
            client=client,
        )

    with zipfile.ZipFile(output_path) as zf:
        names = zf.namelist()
        assert not any(n.startswith("world/") for n in names)
