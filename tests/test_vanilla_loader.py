from mcpack.export.curseforge import build_manifest
from mcpack.export.mrpack import build_index
from mcpack.export.prism import build_mmc_pack
from mcpack.models import Loader, Pack


def _vanilla_pack() -> Pack:
    return Pack(name="Vanilla Pack", minecraft="1.21.1", loader=Loader.VANILLA)


def test_mrpack_index_has_no_loader_dependency():
    index = build_index(_vanilla_pack())
    assert index["dependencies"] == {"minecraft": "1.21.1"}


def test_curseforge_manifest_has_no_mod_loaders():
    manifest = build_manifest(_vanilla_pack())
    assert manifest["minecraft"]["modLoaders"] == []


def test_prism_mmc_pack_has_only_minecraft_component():
    mmc_pack = build_mmc_pack(_vanilla_pack())
    assert len(mmc_pack["components"]) == 1
    assert mmc_pack["components"][0]["uid"] == "net.minecraft"


def test_pack_loader_version_defaults_to_empty_string():
    pack = _vanilla_pack()
    assert pack.loader_version == ""
