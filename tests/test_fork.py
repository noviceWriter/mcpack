"""PackManager.fork_pack testleri.

Kullanıcı isteği: "fork, bir mod paketini üst/alt Minecraft sürümlerine
uyarlamak demek — o modun uygun sürümü yoksa kullanıcıya bilgi verir, modu
eklemez." Burada test edilen: her modun kendi kaynağında (Modrinth/
CurseForge/Wurst/Meteor) yeni MC versiyonu için yeniden aranması, bulunamayan
modların SESSİZCE değil isim listesiyle atlanması, ve yerel içeriğin (dünya)
MC versiyonundan bağımsız olarak doğrudan kopyalanması."""

from pathlib import Path

import httpx
import pytest
import respx

from mcpack.models import ContentKind, Loader, ModSourceType
from mcpack.packs.manager import PackManager
from mcpack.sources.base import ModDetail, ModVersion, VersionFile
from mcpack.sources.cheat_mods import METEOR_DOWNLOAD_API, WURST_RELEASES_API


class _FakeSource:
    """get_versions sadece _available içindeki project_id'ler için versiyon
    döner — diğerleri "bu MC versiyonu için uyumlu sürüm yok" senaryosunu
    simüle eder."""

    def __init__(self, source: ModSourceType, available: set[str]) -> None:
        self.source = source
        self._available = available

    async def get_versions(self, project_id, *, game_version=None, loader=None):
        if project_id not in self._available:
            return []
        return [
            ModVersion(
                source=self.source,
                version_id=f"v-{project_id}-{game_version}",
                project_id=project_id,
                name=project_id,
                files=[VersionFile(file_name=f"{project_id}.jar", url=f"https://x/{project_id}.jar")],
            )
        ]

    async def get_project(self, project_id):
        return ModDetail(
            source=self.source, project_id=project_id, slug=project_id, title=project_id.upper(),
            description="",
        )


def _fake_version(project_id: str, source=ModSourceType.MODRINTH) -> ModVersion:
    return ModVersion(
        source=source,
        version_id=f"v-{project_id}",
        project_id=project_id,
        name=project_id,
        files=[VersionFile(file_name=f"{project_id}.jar", url=f"https://x/{project_id}.jar")],
    )


@pytest.mark.asyncio
async def test_fork_pack_recreates_compatible_mods_for_new_version(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Perf Pack", minecraft="1.20.1", loader=Loader.FABRIC, loader_version="0.15.0")
    manager.add_mod(pack, _fake_version("sodium"), None)
    manager.add_mod(pack, _fake_version("lithium"), None)

    modrinth = _FakeSource(ModSourceType.MODRINTH, available={"sodium", "lithium"})

    async with httpx.AsyncClient() as http_client:
        new_pack, failed = await manager.fork_pack(
            pack,
            name="Perf Pack (Fork)",
            minecraft="1.21.1",
            loader_version="0.16.5",
            modrinth=modrinth,
            curseforge=None,
            http_client=http_client,
        )

    assert failed == []
    assert new_pack.id != pack.id
    assert new_pack.minecraft == "1.21.1"
    assert new_pack.loader == Loader.FABRIC
    assert new_pack.loader_version == "0.16.5"
    assert {m.project_id for m in new_pack.mods} == {"sodium", "lithium"}
    # orijinal pack dokunulmamış kalmalı
    assert pack.minecraft == "1.20.1"


@pytest.mark.asyncio
async def test_fork_pack_skips_mods_without_compatible_version(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.20.1", loader=Loader.FABRIC, loader_version="0.15.0")
    manager.add_mod(pack, _fake_version("sodium"), None)
    manager.add_mod(pack, _fake_version("old-abandoned-mod"), None)

    # "old-abandoned-mod" yeni versiyon için hiç güncellenmemiş -> bulunamaz
    modrinth = _FakeSource(ModSourceType.MODRINTH, available={"sodium"})

    async with httpx.AsyncClient() as http_client:
        new_pack, failed = await manager.fork_pack(
            pack, name="Fork", minecraft="1.21.1", loader_version="0.16.5",
            modrinth=modrinth, curseforge=None, http_client=http_client,
        )

    assert {m.project_id for m in new_pack.mods} == {"sodium"}
    assert failed == ["old-abandoned-mod.jar"]


@pytest.mark.asyncio
async def test_fork_pack_without_curseforge_client_skips_curseforge_mods(tmp_path: Path):
    """CurseForge API anahtarı ayarlanmamışsa (curseforge=None) o kaynaktan
    gelen modlar sessizce değil, uyarı listesiyle atlanmalı."""
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.20.1", loader=Loader.FABRIC, loader_version="0.15.0")
    manager.add_mod(pack, _fake_version("cf-mod", source=ModSourceType.CURSEFORGE), None)

    modrinth = _FakeSource(ModSourceType.MODRINTH, available=set())

    async with httpx.AsyncClient() as http_client:
        new_pack, failed = await manager.fork_pack(
            pack, name="Fork", minecraft="1.21.1", loader_version="0.16.5",
            modrinth=modrinth, curseforge=None, http_client=http_client,
        )

    assert new_pack.mods == []
    assert failed == ["cf-mod.jar"]


@pytest.mark.asyncio
async def test_fork_pack_copies_local_world_content_regardless_of_mc_version(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.20.1", loader=Loader.VANILLA, loader_version="")

    world_dir = tmp_path / "MyWorld"
    (world_dir / "region").mkdir(parents=True)
    (world_dir / "level.dat").write_bytes(b"leveldata")
    manager.add_content(pack, ContentKind.WORLD, world_dir)

    modrinth = _FakeSource(ModSourceType.MODRINTH, available=set())

    async with httpx.AsyncClient() as http_client:
        new_pack, failed = await manager.fork_pack(
            pack, name="Fork", minecraft="1.21.1", loader_version="",
            modrinth=modrinth, curseforge=None, http_client=http_client,
        )

    assert failed == []
    assert [c.name for c in new_pack.content] == ["MyWorld"]
    copied = manager.content_root(new_pack) / new_pack.content[0].stored_path
    assert (copied / "level.dat").read_bytes() == b"leveldata"


@pytest.mark.asyncio
async def test_fork_pack_re_resolves_cheat_mods_for_new_mc_version(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.20.1", loader=Loader.FABRIC, loader_version="0.15.0")
    manager.add_cheat_mod(
        pack, ModSourceType.WURST, "Wurst-Client-v7.42-MC1.20.1.jar",
        "https://x/old.jar",
    )

    releases = [
        {
            "assets": [
                {"name": "Wurst-Client-v7.50-MC1.21.1.jar", "browser_download_url": "https://x/new.jar"},
            ]
        }
    ]
    modrinth = _FakeSource(ModSourceType.MODRINTH, available=set())

    with respx.mock:
        respx.get(WURST_RELEASES_API).mock(return_value=httpx.Response(200, json=releases))
        async with httpx.AsyncClient() as http_client:
            new_pack, failed = await manager.fork_pack(
                pack, name="Fork", minecraft="1.21.1", loader_version="0.16.5",
                modrinth=modrinth, curseforge=None, http_client=http_client,
            )

    assert failed == []
    wurst_entry = new_pack.find_mod("wurst")
    assert wurst_entry is not None
    assert wurst_entry.file_name == "Wurst-Client-v7.50-MC1.21.1.jar"


@pytest.mark.asyncio
async def test_fork_pack_reports_cheat_mod_unavailable_for_new_version(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.20.1", loader=Loader.FABRIC, loader_version="0.15.0")
    manager.add_cheat_mod(pack, ModSourceType.METEOR, "meteor-1.20.1.jar", "https://x/old.jar")

    modrinth = _FakeSource(ModSourceType.MODRINTH, available=set())

    with respx.mock:
        respx.get(METEOR_DOWNLOAD_API).mock(
            return_value=httpx.Response(200, json={"error": "Failed to get maven version."})
        )
        async with httpx.AsyncClient() as http_client:
            new_pack, failed = await manager.fork_pack(
                pack, name="Fork", minecraft="1.7.10", loader_version="0.16.5",
                modrinth=modrinth, curseforge=None, http_client=http_client,
            )

    assert new_pack.find_mod("meteor") is None
    assert failed == ["Meteor Client"]
