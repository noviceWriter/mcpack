import zipfile
from pathlib import Path

import httpx
import pytest

from mcpack.export.base import EXCLUDED_OVERRIDE_DIR_NAMES
from mcpack.export.mrpack import MrpackExporter
from mcpack.models import Loader, Pack


def _make_pack_with_overrides(tmp_path: Path) -> tuple[Pack, Path]:
    pack = Pack(
        name="Test",
        minecraft="1.21.1",
        loader=Loader.FABRIC,
        loader_version="0.16.5",
    )
    pack.overrides.include = ["config", "saves"]

    source_dir = tmp_path / "src"
    (source_dir / "config").mkdir(parents=True)
    (source_dir / "config" / "options.txt").write_text("x")
    (source_dir / "saves" / "world").mkdir(parents=True)
    (source_dir / "saves" / "world" / "level.dat").write_text("x")

    return pack, source_dir


@pytest.mark.asyncio
async def test_default_excludes_saves(tmp_path: Path):
    pack, source_dir = _make_pack_with_overrides(tmp_path)
    output_path = tmp_path / "out.mrpack"

    async with httpx.AsyncClient() as client:
        await MrpackExporter().export(
            pack, source_dir=source_dir, output_path=output_path,
            cache_dir=tmp_path / "cache", content_root=tmp_path / "content", client=client,
        )

    with zipfile.ZipFile(output_path) as zf:
        names = zf.namelist()
        assert "overrides/config/options.txt" in names
        assert not any("saves" in n for n in names)


@pytest.mark.asyncio
async def test_exclude_dirs_empty_includes_saves(tmp_path: Path):
    pack, source_dir = _make_pack_with_overrides(tmp_path)
    output_path = tmp_path / "out.mrpack"

    async with httpx.AsyncClient() as client:
        await MrpackExporter().export(
            pack, source_dir=source_dir, output_path=output_path,
            cache_dir=tmp_path / "cache", content_root=tmp_path / "content", client=client, exclude_dirs=set(),
        )

    with zipfile.ZipFile(output_path) as zf:
        names = zf.namelist()
        assert "overrides/saves/world/level.dat" in names


def test_default_exclude_set_contains_expected_dirs():
    assert EXCLUDED_OVERRIDE_DIR_NAMES == {"logs", "crash-reports", "saves"}
