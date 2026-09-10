"""Server pack üretimi: client pack'ten server-only paket türetme.

proje-amacı.md §2.4: client-only modları ele (Sodium, Iris, ModMenu, REI vb.),
server-side/both modları tut, config/script klasörlerini kopyala, isteğe
bağlı start.bat/start.sh ekle.

Eleme mantığı iki katmanlı:
1. Modrinth API'sinden gelen gerçek env bilgisi (ModEntry.env) — güvenilir.
2. CurseForge gibi env bilgisi vermeyen kaynaklar için data/client_only_mods.json
   içindeki bilinen slug listesiyle sezgisel eşleştirme (fallback).
"""

from __future__ import annotations

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
from mcpack.known_mods import load_known_client_only_slugs
from mcpack.models import ModEntry, ModSourceType, Pack


def is_server_compatible(entry: ModEntry, known_client_only_slugs: set[str] | None = None) -> bool:
    """Bir modun server pack'te kalıp kalmayacağına karar verir."""
    if entry.env.server.value == "unsupported":
        return False

    # Modrinth API'si zaten gerçek env bilgisi veriyor — bilinen sezgisel
    # listeyle bunun üzerine yazmıyoruz. Aksi halde örn. JEI (gerçekte
    # server: optional) sırf bizim listemizde "client-only" varsayımıyla
    # yer aldığı için yanlışlıkla server pack'ten elenirdi.
    if entry.source == ModSourceType.MODRINTH:
        return True

    known = known_client_only_slugs if known_client_only_slugs is not None else load_known_client_only_slugs()
    if entry.slug and entry.slug.lower() in known:
        return False
    if any(slug in entry.file_name.lower() for slug in known):
        return False

    return True


def filter_server_mods(pack: Pack, known_client_only_slugs: set[str] | None = None) -> list[ModEntry]:
    known = known_client_only_slugs if known_client_only_slugs is not None else load_known_client_only_slugs()
    return [m for m in pack.mods if is_server_compatible(m, known)]


_START_SH = """#!/usr/bin/env bash
# Basit sunucu başlatma script'i - Java yolunu/argümanlarını ihtiyaca göre düzenleyin.
java -Xmx4G -Xms2G -jar server.jar nogui
"""

_START_BAT = """@echo off
REM Basit sunucu baslatma script'i - Java yolunu/argumanlarini ihtiyaca gore duzenleyin.
java -Xmx4G -Xms2G -jar server.jar nogui
pause
"""


class ServerPackExporter(Exporter):
    format_name = "Server Pack"
    file_extension = ".zip"

    def __init__(self, *, include_start_scripts: bool = True) -> None:
        self.include_start_scripts = include_start_scripts

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
        server_mods = filter_server_mods(pack)
        mod_files = await ensure_mods_downloaded(
            server_mods, cache_dir, client, progress_cb=progress_cb, cancel_event=cancel_event
        )

        override_files = collect_override_files(
            source_dir,
            pack.overrides.include,
            exclude_dirs=exclude_dirs if exclude_dirs is not None else EXCLUDED_OVERRIDE_DIR_NAMES,
        )

        manifest_entries: list[tuple[str, str | bytes]] = []
        if self.include_start_scripts:
            manifest_entries.append(("start.sh", _START_SH))
            manifest_entries.append(("start.bat", _START_BAT))

        return write_zip(
            output_path,
            manifest_entries=manifest_entries,
            mod_files=mod_files,
            mod_arc_prefix="mods/",
            override_files=override_files,
            override_arc_prefix="",
        )
