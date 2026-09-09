"""Tüm dosya indirmelerinin tek geçtiği yer: async HTTP + hash doğrulama + rate limit.

proje-amacı.md §6: "Her indirmede hash doğrula" ve "Rate limit'lere saygı göster
(özellikle Modrinth)" kurallarını burada merkezi olarak uyguluyoruz.
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import Callable
from pathlib import Path

import httpx

USER_AGENT = "mcpack/0.1.0 (github.com/mcpack; iletisim: gunselahmet53@gmail.com)"

ProgressCallback = Callable[[int, int], None]
"""(indirilen_bayt, toplam_bayt) -> None"""


class DownloadError(Exception):
    pass


class HashMismatchError(DownloadError):
    def __init__(self, path: Path, algo: str, expected: str, actual: str) -> None:
        super().__init__(
            f"{path.name}: {algo} uyuşmuyor (beklenen={expected}, gerçek={actual})"
        )
        self.path = path
        self.algo = algo
        self.expected = expected
        self.actual = actual


def compute_hash(path: Path, algo: str) -> str:
    h = hashlib.new(algo)
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_hashes(path: Path, *, sha1: str | None = None, sha512: str | None = None) -> None:
    """Verilen hash'leri dosyayla karşılaştırır, uyuşmazsa HashMismatchError fırlatır."""
    if sha1:
        actual = compute_hash(path, "sha1")
        if actual.lower() != sha1.lower():
            raise HashMismatchError(path, "sha1", sha1, actual)
    if sha512:
        actual = compute_hash(path, "sha512")
        if actual.lower() != sha512.lower():
            raise HashMismatchError(path, "sha512", sha512, actual)


class RateLimiter:
    """Modrinth'in X-Ratelimit-* header'larına göre kendini yavaşlatan basit limiter."""

    def __init__(self, min_remaining: int = 2) -> None:
        self._min_remaining = min_remaining
        self._lock = asyncio.Lock()

    async def observe(self, response: httpx.Response) -> None:
        remaining = response.headers.get("X-Ratelimit-Remaining")
        reset = response.headers.get("X-Ratelimit-Reset")
        if remaining is None or reset is None:
            return
        try:
            remaining_i = int(remaining)
            reset_f = float(reset)
        except ValueError:
            return
        if remaining_i <= self._min_remaining:
            async with self._lock:
                await asyncio.sleep(min(reset_f, 10.0))


def make_client(*, extra_headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    headers = {"User-Agent": USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    return httpx.AsyncClient(headers=headers, timeout=30.0, follow_redirects=True)


async def download_file(
    client: httpx.AsyncClient,
    url: str,
    dest: Path,
    *,
    sha1: str | None = None,
    sha512: str | None = None,
    progress_cb: ProgressCallback | None = None,
    max_retries: int = 3,
) -> Path:
    """Dosyayı indirir, hash doğrular. Uyuşmazsa dosyayı siler ve tekrar dener."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        try:
            downloaded = 0
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length", 0))
                tmp_path = dest.with_suffix(dest.suffix + ".part")
                with tmp_path.open("wb") as f:
                    async for chunk in response.aiter_bytes(64 * 1024):
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb:
                            progress_cb(downloaded, total)
            tmp_path.replace(dest)
            if sha1 or sha512:
                verify_hashes(dest, sha1=sha1, sha512=sha512)
            return dest
        except HashMismatchError as exc:
            dest.unlink(missing_ok=True)
            last_error = exc
        except httpx.HTTPError as exc:
            last_error = exc
            await asyncio.sleep(min(2**attempt, 10))

    raise DownloadError(f"{dest.name} indirilemedi ({max_retries} denemeden sonra)") from last_error
