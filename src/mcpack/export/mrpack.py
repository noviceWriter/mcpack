"""Modrinth `.mrpack` export.

Format: ZIP arşivi, kökte `modrinth.index.json` + `overrides/` klasörü.
ÖNEMLİ: .mrpack mod jar'larını arşive GÖMMEZ — sadece download URL + hash
referans eder, dosyaları launcher kurulum anında indirir. Bu yüzden burada
mod dosyalarını cache'e indirmiyoruz, sadece manifest üretiyoruz.

Referans: https://docs.modrinth.com/modpacks/format/
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from mcpack.export.base import (
    EXCLUDED_OVERRIDE_DIR_NAMES,
    Exporter,
    ProgressCallback,
    collect_content_download_files,
    collect_override_files,
    collect_world_files,
    ensure_mods_downloaded,
    write_zip,
)
from mcpack.models import ContentKind, Loader, ModEntry, Pack

_LOADER_DEPENDENCY_KEY = {
    Loader.FABRIC: "fabric-loader",
    Loader.QUILT: "quilt-loader",
    Loader.FORGE: "forge",
    Loader.NEOFORGE: "neoforge",
}


def _mod_file_entry(entry: ModEntry) -> dict:
    return {
        "path": f"mods/{entry.file_name}",
        "hashes": {
            k: v
            for k, v in {"sha1": entry.hashes.sha1, "sha512": entry.hashes.sha512}.items()
            if v
        },
        "env": {"client": entry.env.client.value, "server": entry.env.server.value},
        "downloads": [entry.download_url],
        "fileSize": entry.file_size or 0,
    }


def build_index(pack: Pack) -> dict:
    dependencies = {"minecraft": pack.minecraft}
    if pack.loader != Loader.VANILLA:
        dependencies[_LOADER_DEPENDENCY_KEY[pack.loader]] = pack.loader_version

    return {
        "formatVersion": 1,
        "game": "minecraft",
        "versionId": pack.version,
        "name": pack.name,
        "summary": pack.summary,
        "files": [_mod_file_entry(m) for m in pack.mods],
        "dependencies": dependencies,
    }


class MrpackExporter(Exporter):
    format_name = "Modrinth"
    file_extension = ".mrpack"

    async def export(
        self,
        pack: Pack,
        *,
        source_dir: Path,
        output_path: Path,
        cache_dir: Path,
        content_root: Path,
        client: httpx.AsyncClient,
        exclude_dirs: set[str] | None = None,
        progress_cb: ProgressCallback | None = None,
        cancel_event=None,
    ) -> Path:
        # .mrpack mod jar'larını indirmez (sadece URL referans eder) ama
        # shader/resourcepack/datapack indirilip overrides/ altına gömülür
        # (bkz. export/base.py:ensure_mods_downloaded) — bu yüzden cancel_event
        # burada da geçerli.
        index = build_index(pack)
        override_files = collect_override_files(
            source_dir,
            pack.overrides.include,
            exclude_dirs=exclude_dirs if exclude_dirs is not None else EXCLUDED_OVERRIDE_DIR_NAMES,
        )
        override_files += collect_world_files(pack, content_root)
        downloaded_content = await ensure_mods_downloaded(
            pack.content_downloads, cache_dir, client, progress_cb=progress_cb, cancel_event=cancel_event
        )
        datapack_world_roots = [f"saves/{w.name}" for w in pack.content_of(ContentKind.WORLD)]
        override_files += collect_content_download_files(
            pack.content_downloads, downloaded_content, datapack_world_roots=datapack_world_roots
        )
        if progress_cb:
            progress_cb(1, 1)
        return write_zip(
            output_path,
            manifest_entries=[("modrinth.index.json", json.dumps(index, indent=2, ensure_ascii=False))],
            override_files=override_files,
            override_arc_prefix="overrides",
        )
