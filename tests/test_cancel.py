import threading
from pathlib import Path

import httpx
import pytest

from mcpack.downloader import DownloadCancelledError, download_file
from mcpack.export.base import ensure_mods_downloaded
from mcpack.models import ModEntry, ModHashes, ModSourceType


def _entry(project_id: str) -> ModEntry:
    return ModEntry(
        source=ModSourceType.MODRINTH,
        project_id=project_id,
        version_id="1",
        file_name=f"{project_id}.jar",
        download_url="https://example.com/mod.jar",
        hashes=ModHashes(),
    )


@pytest.mark.asyncio
async def test_download_file_raises_when_already_cancelled(tmp_path: Path):
    event = threading.Event()
    event.set()

    async with httpx.AsyncClient() as client:
        with pytest.raises(DownloadCancelledError):
            await download_file(client, "https://example.com/mod.jar", tmp_path / "mod.jar", cancel_event=event)


@pytest.mark.asyncio
async def test_ensure_mods_downloaded_stops_on_cancel(tmp_path: Path):
    event = threading.Event()
    event.set()
    mods = [_entry("a"), _entry("b")]

    async with httpx.AsyncClient() as client:
        with pytest.raises(DownloadCancelledError):
            await ensure_mods_downloaded(mods, tmp_path / "cache", client, cancel_event=event)


@pytest.mark.asyncio
async def test_ensure_mods_downloaded_skips_remaining_after_first_cached(tmp_path: Path):
    """İlk mod zaten diskte (hash tutuyor) olsa bile, ikinci moda geçmeden
    önce cancel_event kontrol edilmeli."""
    cache_dir = tmp_path / "cache"
    cache_dir.mkdir()
    mods = [_entry("a"), _entry("b")]
    # 'a' zaten cache'de ama hash beklenmiyor (ModHashes bos), bu yuzden
    # dogrudan var sayilir.
    (cache_dir / "a.jar").write_bytes(b"fake")

    event = threading.Event()

    async def cancel_after_first(done, total):
        event.set()

    async with httpx.AsyncClient() as client:
        with pytest.raises(DownloadCancelledError):
            # 'a' cache'den okunurken progress_cb cagrilir ve event set edilir,
            # 'b' indirilmeye baslamadan once kontrol edilip durmali.
            await ensure_mods_downloaded(
                mods,
                cache_dir,
                client,
                cancel_event=event,
                progress_cb=lambda done, total: event.set(),
            )
