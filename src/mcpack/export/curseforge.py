"""CurseForge modpack export.

Format: ZIP arşivi, kökte `manifest.json` + `overrides/` klasörü.
CF manifest'i sadece CurseForge kaynaklı modları projectID/fileID ile
referans edebilir (indirme CurseForge launcher'ı üzerinden olur). Modrinth
kaynaklı (veya CF'de bulunmayan) modlar bu yüzden jar olarak indirilip
doğrudan `overrides/mods/` altına gömülür — packwiz gibi araçların da
kullandığı standart yaklaşım budur.

Referans: https://docs.curseforge.com/ (Modpack manifest şeması resmi
olarak belgelenmemiştir ama fiilen bu alanlar kullanılır).
"""

from __future__ import annotations

import json
from pathlib import Path

import httpx

from mcpack.export.base import (
    EXCLUDED_OVERRIDE_DIR_NAMES,
    Exporter,
    ProgressCallback,
    collect_override_files,
    ensure_mods_downloaded,
    write_zip,
)
from mcpack.models import Loader, ModSourceType, Pack

_LOADER_ID_PREFIX = {
    Loader.FABRIC: "fabric",
    Loader.QUILT: "quilt",
    Loader.FORGE: "forge",
    Loader.NEOFORGE: "neoforge",
}


def build_manifest(pack: Pack) -> dict:
    cf_mods = [m for m in pack.mods if m.source == ModSourceType.CURSEFORGE]
    mod_loaders = (
        []
        if pack.loader == Loader.VANILLA
        else [{"id": f"{_LOADER_ID_PREFIX[pack.loader]}-{pack.loader_version}", "primary": True}]
    )
    return {
        "minecraft": {
            "version": pack.minecraft,
            "modLoaders": mod_loaders,
        },
        "manifestType": "minecraftModpack",
        "manifestVersion": 1,
        "name": pack.name,
        "version": pack.version,
        "author": pack.author,
        "files": [
            {
                "projectID": int(m.project_id),
                "fileID": int(m.version_id),
                "required": True,
            }
            for m in cf_mods
        ],
        "overrides": "overrides",
    }


class CurseForgeExporter(Exporter):
    format_name = "CurseForge"
    file_extension = ".zip"

    async def export(
        self,
        pack: Pack,
        *,
        source_dir: Path,
        output_path: Path,
        cache_dir: Path,
        client: httpx.AsyncClient,
        exclude_dirs: set[str] | None = None,
        progress_cb: ProgressCallback | None = None,
        cancel_event=None,
    ) -> Path:
        manifest = build_manifest(pack)

        # CF olmayan kaynaklı modlar manifest'te referans edilemez, jar
        # olarak overrides/mods/ altına gömülmeli.
        non_cf_mods = [m for m in pack.mods if m.source != ModSourceType.CURSEFORGE]
        embedded_files = await ensure_mods_downloaded(
            non_cf_mods, cache_dir, client, progress_cb=progress_cb, cancel_event=cancel_event
        )

        override_files = collect_override_files(
            source_dir,
            pack.overrides.include,
            exclude_dirs=exclude_dirs if exclude_dirs is not None else EXCLUDED_OVERRIDE_DIR_NAMES,
        )
        for path in embedded_files.values():
            override_files.append((path, f"mods/{path.name}"))

        return write_zip(
            output_path,
            manifest_entries=[("manifest.json", json.dumps(manifest, indent=2, ensure_ascii=False))],
            override_files=override_files,
            override_arc_prefix="overrides",
        )
