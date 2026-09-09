import json
import zipfile
from pathlib import Path

import httpx
import pytest
import respx

from mcpack.export.curseforge import CurseForgeExporter
from mcpack.models import Loader, ModEntry, ModHashes, ModSourceType, Pack


@pytest.mark.asyncio
async def test_curseforge_export_embeds_non_cf_mods(tmp_path: Path):
    pack = Pack(
        name="Test Pack",
        version="1.0.0",
        author="tester",
        minecraft="1.21.1",
        loader=Loader.FABRIC,
        loader_version="0.16.5",
    )
    pack.mods = [
        ModEntry(
            source=ModSourceType.CURSEFORGE,
            project_id="238222",
            version_id="555",
            file_name="jei.jar",
            download_url="https://edge.forgecdn.net/jei.jar",
            hashes=ModHashes(),
        ),
        ModEntry(
            source=ModSourceType.MODRINTH,
            project_id="AANobbMI",
            version_id="v1",
            file_name="sodium.jar",
            download_url="https://cdn.modrinth.com/sodium.jar",
            hashes=ModHashes(),
        ),
    ]

    output_path = tmp_path / "out.zip"
    source_dir = tmp_path / "src"
    source_dir.mkdir()

    with respx.mock as mock:
        mock.get("https://cdn.modrinth.com/sodium.jar").mock(
            return_value=httpx.Response(200, content=b"fake-jar-bytes")
        )
        async with httpx.AsyncClient() as client:
            result = await CurseForgeExporter().export(
                pack,
                source_dir=source_dir,
                output_path=output_path,
                cache_dir=tmp_path / "cache",
                client=client,
            )

    assert result == output_path
    with zipfile.ZipFile(output_path) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert "overrides/mods/sodium.jar" in names
        assert "overrides/mods/jei.jar" not in names  # CF modu manifest'te, jar gömülmedi

        manifest = json.loads(zf.read("manifest.json"))
        assert manifest["files"] == [{"projectID": 238222, "fileID": 555, "required": True}]
        assert manifest["minecraft"]["modLoaders"][0]["id"] == "fabric-0.16.5"
