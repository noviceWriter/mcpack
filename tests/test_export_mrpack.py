import json
import zipfile
from pathlib import Path

import httpx
import pytest

from mcpack.export.mrpack import MrpackExporter
from mcpack.models import EnvRequirement, Loader, ModEntry, ModEnv, ModHashes, ModSourceType, Pack


@pytest.mark.asyncio
async def test_mrpack_export_writes_index_and_overrides(tmp_path: Path):
    pack = Pack(
        name="Test Pack",
        version="1.0.0",
        minecraft="1.21.1",
        loader=Loader.FABRIC,
        loader_version="0.16.5",
    )
    pack.mods = [
        ModEntry(
            source=ModSourceType.MODRINTH,
            project_id="AANobbMI",
            version_id="v1",
            file_name="sodium-0.6.jar",
            file_size=100,
            hashes=ModHashes(sha1="a" * 40, sha512="b" * 128),
            download_url="https://cdn.modrinth.com/sodium-0.6.jar",
            env=ModEnv(client=EnvRequirement.REQUIRED, server=EnvRequirement.UNSUPPORTED),
        )
    ]

    source_dir = tmp_path / "src"
    (source_dir / "config").mkdir(parents=True)
    (source_dir / "config" / "sodium-options.json").write_text("{}")

    output_path = tmp_path / "out.mrpack"

    async with httpx.AsyncClient() as client:
        result = await MrpackExporter().export(
            pack,
            source_dir=source_dir,
            output_path=output_path,
            cache_dir=tmp_path / "cache",
            client=client,
        )

    assert result == output_path
    with zipfile.ZipFile(output_path) as zf:
        names = zf.namelist()
        assert "modrinth.index.json" in names
        assert "overrides/config/sodium-options.json" in names

        index = json.loads(zf.read("modrinth.index.json"))
        assert index["dependencies"] == {"minecraft": "1.21.1", "fabric-loader": "0.16.5"}
        assert index["files"][0]["env"] == {"client": "required", "server": "unsupported"}
        assert index["files"][0]["hashes"]["sha1"] == "a" * 40
