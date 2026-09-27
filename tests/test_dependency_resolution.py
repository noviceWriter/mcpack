from pathlib import Path

import pytest

from mcpack.models import Loader, ModSourceType
from mcpack.packs.manager import PackManager
from mcpack.sources.base import ModVersion, VersionDependency, VersionFile


class _FakeSource:
    def __init__(self, versions_by_project: dict[str, ModVersion]) -> None:
        self._versions_by_project = versions_by_project

    async def get_versions(self, project_id, *, game_version=None, loader=None):
        version = self._versions_by_project.get(project_id)
        return [version] if version else []


def _version(project_id: str, deps: list[VersionDependency] | None = None) -> ModVersion:
    return ModVersion(
        source=ModSourceType.MODRINTH,
        version_id=f"v-{project_id}",
        project_id=project_id,
        name=project_id,
        dependencies=deps or [],
        files=[VersionFile(file_name=f"{project_id}.jar", url=f"https://example.com/{project_id}.jar")],
    )


@pytest.mark.asyncio
async def test_resolve_dependencies_follows_required_chain(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.21.1", loader=Loader.FABRIC, loader_version="0.16.5")

    # A -> required B -> required C (C zaten pack'te değil)
    version_c = _version("c")
    version_b = _version("b", [VersionDependency(project_id="c", dependency_type="required")])
    version_a = _version("a", [VersionDependency(project_id="b", dependency_type="required")])
    source = _FakeSource({"b": version_b, "c": version_c})

    resolved, failed = await manager.resolve_dependencies(pack, source, version_a)

    assert {v.project_id for v in resolved} == {"b", "c"}
    assert failed == []


@pytest.mark.asyncio
async def test_resolve_dependencies_skips_already_in_pack(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.21.1", loader=Loader.FABRIC, loader_version="0.16.5")
    manager.add_mod(pack, _version("b"), None)  # b zaten pack'te

    version_a = _version("a", [VersionDependency(project_id="b", dependency_type="required")])
    source = _FakeSource({"b": _version("b")})

    resolved, failed = await manager.resolve_dependencies(pack, source, version_a)

    assert resolved == []
    assert failed == []


@pytest.mark.asyncio
async def test_resolve_dependencies_reports_unresolvable_required_dependency(tmp_path: Path):
    """Kullanıcı geri bildirimi: Prism'de açılışta hata verdi çünkü zorunlu
    bir bağımlılığın pack.minecraft/pack.loader için uyumlu versiyonu
    yoktu ve bu SESSİZCE atlanıyordu. Artık isim listesiyle raporlanmalı."""
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.21.1", loader=Loader.FABRIC, loader_version="0.16.5")

    # "b" gerekli ama source'ta hiçbir versiyonu yok (uyumsuz MC/loader).
    version_a = _version("a", [VersionDependency(project_id="b", dependency_type="required")])
    source = _FakeSource({})

    resolved, failed = await manager.resolve_dependencies(pack, source, version_a)

    assert resolved == []
    assert failed == ["b"]  # _FakeSource'ta get_project yok -> id'ye düşer


@pytest.mark.asyncio
async def test_resolve_optional_dependencies_does_not_recurse(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.21.1", loader=Loader.FABRIC, loader_version="0.16.5")

    version_a = _version(
        "a",
        [
            VersionDependency(project_id="opt1", dependency_type="optional"),
            VersionDependency(project_id="req1", dependency_type="required"),
        ],
    )
    source = _FakeSource({"opt1": _version("opt1"), "req1": _version("req1")})

    optional = await manager.resolve_optional_dependencies(pack, source, version_a)

    assert {v.project_id for v in optional} == {"opt1"}


@pytest.mark.asyncio
async def test_resolve_optional_dependencies_skips_already_in_pack(tmp_path: Path):
    manager = PackManager(tmp_path)
    pack = manager.create_pack(name="Test", minecraft="1.21.1", loader=Loader.FABRIC, loader_version="0.16.5")
    manager.add_mod(pack, _version("opt1"), None)

    version_a = _version("a", [VersionDependency(project_id="opt1", dependency_type="optional")])
    source = _FakeSource({"opt1": _version("opt1")})

    optional = await manager.resolve_optional_dependencies(pack, source, version_a)

    assert optional == []
