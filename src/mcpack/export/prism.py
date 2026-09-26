"""Prism Launcher / MultiMC instance export.

Format: ZIP arşivi, kökte tek bir instance klasörü:
  <pack-adı>/instance.cfg
  <pack-adı>/mmc-pack.json
  <pack-adı>/.minecraft/mods/*.jar
  <pack-adı>/.minecraft/<overrides...>

mmc-pack.json component uid'leri Prism/MultiMC'nin meta.json bileşen
kataloğuyla eşleşir (net.minecraft, net.fabricmc.fabric-loader, ...).
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
from mcpack.models import Loader, Pack

_LOADER_COMPONENT = {
    Loader.FABRIC: ("net.fabricmc.fabric-loader", "Fabric Loader"),
    Loader.QUILT: ("org.quiltmc.quilt-loader", "Quilt Loader"),
    Loader.FORGE: ("net.minecraftforge", "Forge"),
    Loader.NEOFORGE: ("net.neoforged", "NeoForge"),
}


def build_mmc_pack(pack: Pack) -> dict:
    components = [
        {
            "cachedName": "Minecraft",
            "cachedVersion": pack.minecraft,
            "important": True,
            "uid": "net.minecraft",
            "version": pack.minecraft,
        }
    ]
    if pack.loader != Loader.VANILLA:
        loader_uid, loader_name = _LOADER_COMPONENT[pack.loader]
        components.append(
            {
                "cachedName": loader_name,
                "cachedVersion": pack.loader_version,
                "uid": loader_uid,
                "version": pack.loader_version,
            }
        )
    return {"components": components, "formatVersion": 1}


def build_instance_cfg(pack: Pack) -> str:
    lines = [
        "[General]",
        "ConfigVersion=1.2",
        "InstanceType=OneSix",
        "iconKey=default",
        f"name={pack.name}",
        "OverrideCommands=false",
        "OverrideConsole=false",
        "OverrideJavaArgs=false",
        "OverrideJavaLocation=false",
        "OverrideMemory=false",
        "OverrideWindow=false",
        "lastLaunchTime=0",
        "totalTimePlayed=0",
        "lastTimePlayed=0",
        "",
    ]
    return "\n".join(lines)


class PrismExporter(Exporter):
    format_name = "Prism / MultiMC"
    file_extension = ".zip"

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
        root = pack.name.strip().replace("/", "-") or pack.id

        mod_files = await ensure_mods_downloaded(
            pack.mods, cache_dir, client, progress_cb=progress_cb, cancel_event=cancel_event
        )
        override_files = collect_override_files(
            source_dir,
            pack.overrides.include,
            exclude_dirs=exclude_dirs if exclude_dirs is not None else EXCLUDED_OVERRIDE_DIR_NAMES,
        )
        override_files += collect_world_files(pack, content_root)
        downloaded_content = await ensure_mods_downloaded(
            pack.content_downloads, cache_dir, client, cancel_event=cancel_event
        )
        override_files += collect_content_download_files(pack.content_downloads, downloaded_content)

        return write_zip(
            output_path,
            manifest_entries=[
                (f"{root}/instance.cfg", build_instance_cfg(pack)),
                (f"{root}/mmc-pack.json", json.dumps(build_mmc_pack(pack), indent=2)),
            ],
            mod_files=mod_files,
            mod_arc_prefix=f"{root}/.minecraft/mods/",
            override_files=[(p, f"{root}/.minecraft/{rel}") for p, rel in override_files],
            override_arc_prefix="",  # rel yolları zaten prefix içinde tam veriliyor
        )
