"""Export formatlarının ortak arayüzü + paylaşılan yardımcılar
(mod indirme cache'i, overrides toplama, zip yazma).

proje-amacı.md §3.2: her format kendi manifest'ini + overrides/ klasörünü
içeren bir ZIP üretir; bu dosya o ortak iskeleti sağlar.
"""

from __future__ import annotations

import threading
import zipfile
from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path

import httpx

from mcpack.downloader import DownloadCancelledError, HashMismatchError, download_file, verify_hashes
from mcpack.models import ModEntry, Pack
from mcpack.packs.storage import PathTraversalError, safe_join

ProgressCallback = Callable[[int, int], None]

EXCLUDED_OVERRIDE_DIR_NAMES = {"logs", "crash-reports", "saves"}
"""proje-amacı.md §2.3: export sırasında hariç tutulabilecek dizinler."""


async def ensure_mods_downloaded(
    mods: list[ModEntry],
    cache_dir: Path,
    client: httpx.AsyncClient,
    *,
    progress_cb: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> dict[str, Path]:
    """Verilen mod listesini cache_dir'e indirir (hash doğrulanır).

    Zaten diskte olup hash'i tutan dosyalar tekrar indirilmez — export'u
    tekrar tekrar çalıştırmak ucuz olsun diye.

    cancel_event set edilmişse (büyük pack'lerde kullanıcı iptal ederse,
    proje-amacı.md §6) kalan modlar indirilmeden DownloadCancelledError
    yükseltilir.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, Path] = {}

    for i, entry in enumerate(mods):
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelledError("Export kullanıcı tarafından iptal edildi")

        dest = cache_dir / entry.file_name
        if dest.exists():
            try:
                verify_hashes(dest, sha1=entry.hashes.sha1, sha512=entry.hashes.sha512)
                result[entry.project_id] = dest
                if progress_cb:
                    progress_cb(i + 1, len(mods))
                continue
            except HashMismatchError:
                dest.unlink(missing_ok=True)

        await download_file(
            client,
            entry.download_url,
            dest,
            sha1=entry.hashes.sha1,
            sha512=entry.hashes.sha512,
            cancel_event=cancel_event,
        )
        result[entry.project_id] = dest
        if progress_cb:
            progress_cb(i + 1, len(mods))

    return result


def collect_override_files(
    source_dir: Path, include: list[str], *, exclude_dirs: set[str] | None = None
) -> list[tuple[Path, str]]:
    """(gerçek_yol, arşiv_içi_göreli_yol) çiftlerini döner.

    `safe_join` sayesinde `include` listesindeki bir girdi `..` ile
    source_dir dışına çıkmaya çalışırsa sessizce atlanır (path traversal koruması).
    """
    exclude_dirs = exclude_dirs or set()
    files: list[tuple[Path, str]] = []

    for name in include:
        if name in exclude_dirs:
            continue
        try:
            entry_path = safe_join(source_dir, name)
        except PathTraversalError:
            continue
        if not entry_path.exists():
            continue
        if entry_path.is_file():
            files.append((entry_path, name))
            continue
        for path in entry_path.rglob("*"):
            if not path.is_file():
                continue
            rel = path.relative_to(source_dir)
            if exclude_dirs & set(rel.parts):
                continue
            files.append((path, str(rel).replace("\\", "/")))

    return files


def write_zip(
    output_path: Path,
    *,
    manifest_entries: list[tuple[str, str | bytes]],
    mod_files: dict[str, Path] | None = None,
    mod_arc_prefix: str = "",
    override_files: list[tuple[Path, str]] | None = None,
    override_arc_prefix: str = "overrides",
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for arcname, content in manifest_entries:
            data = content.encode("utf-8") if isinstance(content, str) else content
            zf.writestr(arcname, data)

        if mod_files:
            for path in mod_files.values():
                arcname = f"{mod_arc_prefix}{path.name}" if mod_arc_prefix else path.name
                zf.write(path, arcname)

        if override_files:
            for real_path, rel in override_files:
                arcname = f"{override_arc_prefix}/{rel}" if override_arc_prefix else rel
                zf.write(real_path, arcname)

    return output_path


class Exporter(ABC):
    """Her export formatının (mrpack/CF/Prism/server) uyduğu ortak arayüz."""

    format_name: str
    file_extension: str

    @abstractmethod
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
        cancel_event: threading.Event | None = None,
    ) -> Path:
        """pack'i dışa aktarır ve üretilen dosyanın yolunu döner.

        source_dir: overrides (config, kubejs, ...) için kaynak dizin — genelde
        kullanıcının pack'i düzenlerken kullandığı çalışma klasörü.
        exclude_dirs: overrides'tan hariç tutulacak alt dizin adları (logs,
        crash-reports, saves, ...). None ise EXCLUDED_OVERRIDE_DIR_NAMES
        kullanılır (proje-amacı.md §2.3 — "saves opsiyonel" hariç tutulabilmeli,
        bu yüzden sabit değil, çağıran taraf Settings'ten besler).
        cancel_event: set edilirse indirme kalan modlara geçmeden
        DownloadCancelledError ile durur (proje-amacı.md §6 — iptal desteği).
        """
        ...
