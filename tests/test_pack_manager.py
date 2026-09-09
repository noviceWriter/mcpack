from pathlib import Path

import pytest

from mcpack.models import EnvRequirement, Loader, ModEntry, ModHashes, ModSourceType
from mcpack.packs.manager import PackManager


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
