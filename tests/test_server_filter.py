from mcpack.export.server import filter_server_mods, is_server_compatible
from mcpack.models import EnvRequirement, Loader, ModEntry, ModEnv, ModHashes, ModSourceType, Pack


def _entry(project_id: str, *, slug: str | None = None, server=EnvRequirement.REQUIRED, file_name=None) -> ModEntry:
    return ModEntry(
        source=ModSourceType.MODRINTH,
        project_id=project_id,
        slug=slug,
        version_id="v1",
        file_name=file_name or f"{project_id}.jar",
        hashes=ModHashes(sha1="a" * 40),
        download_url="https://example.com/mod.jar",
        env=ModEnv(client=EnvRequirement.REQUIRED, server=server),
    )


def test_modrinth_env_unsupported_is_excluded():
    entry = _entry("sodium", server=EnvRequirement.UNSUPPORTED)
    assert is_server_compatible(entry, known_client_only_slugs=set()) is False


def test_both_side_mod_is_included():
    entry = _entry("fabric-api", server=EnvRequirement.REQUIRED)
    assert is_server_compatible(entry, known_client_only_slugs=set()) is True


def test_known_slug_fallback_excludes_curseforge_mod_without_env():
    entry = _entry("123456", slug="iris", server=EnvRequirement.REQUIRED)
    assert is_server_compatible(entry, known_client_only_slugs={"iris"}) is False


def test_filter_server_mods_on_pack():
    pack = Pack(name="Test", minecraft="1.21.1", loader=Loader.FABRIC, loader_version="0.16.5")
    pack.mods = [
        _entry("fabric-api"),
        _entry("sodium", server=EnvRequirement.UNSUPPORTED),
        _entry("999", slug="modmenu"),
    ]
    result = filter_server_mods(pack, known_client_only_slugs={"modmenu"})
    assert [m.project_id for m in result] == ["fabric-api"]
