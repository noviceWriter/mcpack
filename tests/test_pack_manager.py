from pathlib import Path

import pytest

from mcpack.models import EnvRequirement, Loader, ModEntry, ModHashes, ModSourceType
from mcpack.packs.manager import PackManager, _version_to_entry
from mcpack.sources.base import ModDetail, ModVersion, VersionFile


def _add_dummy_mod(manager: PackManager, pack, project_id: str = "sodium") -> None:
    entry = ModEntry(
        source=ModSourceType.CURSEFORGE,
        project_id=project_id,
        version_id="1",
        file_name=f"{project_id}.jar",
        download_url="https://example.com/mod.jar",
        hashes=ModHashes(),
    )
    pack.mods.append(entry)
    manager.save(pack)


def test_set_mod_env_updates_and_persists(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.21.1", loader=Loader.FABRIC, loader_version="0.16.5")
    _add_dummy_mod(manager, pack)

    manager.set_mod_env(pack, "sodium", server=EnvRequirement.UNSUPPORTED)

    reloaded = manager.load(pack.id)
    entry = reloaded.find_mod("sodium")
    assert entry is not None
    assert entry.env.server == EnvRequirement.UNSUPPORTED
    assert entry.env.client == EnvRequirement.REQUIRED  # değiştirilmedi


def test_set_mod_env_missing_project_raises(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.21.1", loader=Loader.FABRIC, loader_version="0.16.5")

    with pytest.raises(ValueError):
        manager.set_mod_env(pack, "does-not-exist", client=EnvRequirement.OPTIONAL)


def _cf_version(slug: str) -> tuple[ModVersion, ModDetail]:
    version = ModVersion(
        source=ModSourceType.CURSEFORGE,
        version_id="1",
        project_id="123",
        name="v1",
        files=[VersionFile(file_name=f"{slug}.jar", url="https://example.com/mod.jar")],
    )
    detail = ModDetail(source=ModSourceType.CURSEFORGE, project_id="123", slug=slug, title=slug, description="")
    return version, detail


def test_curseforge_mod_matching_known_slug_marked_client_only():
    version, detail = _cf_version("sodium")
    entry = _version_to_entry(version, detail)
    assert entry.env.client == EnvRequirement.REQUIRED
    assert entry.env.server == EnvRequirement.UNSUPPORTED


def test_curseforge_mod_unknown_slug_defaults_to_required_both_sides():
    version, detail = _cf_version("some-random-gameplay-mod")
    entry = _version_to_entry(version, detail)
    assert entry.env.client == EnvRequirement.REQUIRED
    assert entry.env.server == EnvRequirement.REQUIRED
