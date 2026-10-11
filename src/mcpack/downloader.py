"""Tüm dosya indirmelerinin tek geçtiği yer: async HTTP + hash doğrulama + rate limit.

proje-amacı.md §6: "Her indirmede hash doğrula" ve "Rate limit'lere saygı göster
(özellikle Modrinth)" kurallarını burada merkezi olarak uyguluyoruz.
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
import time
import uuid
from collections.abc import Callable
from pathlib import Path

import httpx

from mcpack import __version__
from mcpack.logging_setup import NETWORK, get_logger

log = get_logger(__name__)

USER_AGENT = f"mcpack/{__version__} (github.com/mcpack; iletisim: gunselahmet53@gmail.com)"

ProgressCallback = Callable[[int, int], None]
"""(indirilen_bayt, toplam_bayt) -> None"""


class DownloadError(Exception):
    pass


class DownloadCancelledError(DownloadError):
    """Kullanıcı export/indirmeyi iptal ettiğinde fırlatılır (proje-amacı.md §6)."""


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


_START_KEY = "mcpack_started"


async def _on_request(request: httpx.Request) -> None:
    request.extensions[_START_KEY] = time.perf_counter()


async def _on_response(response: httpx.Response) -> None:
    """Her yanıt ağ kaydına (logging_setup.NETWORK) düşer — Geliştirici
    sayfasındaki "Ağ" sekmesi buradan beslenir. Başlıklar (CurseForge
    x-api-key) KAYDEDİLMEZ, sadece yöntem/URL/durum/süre."""
    request = response.request
    started = request.extensions.get(_START_KEY)
    elapsed_ms = (time.perf_counter() - started) * 1000 if started is not None else None
    event = NETWORK.record(request.method, str(request.url), response.status_code, elapsed_ms)
    level = 30 if response.status_code >= 400 else 10  # WARNING / DEBUG
    log.log(level, "HTTP %s %s -> %s (%.0f ms)", request.method, event.url, response.status_code, elapsed_ms or 0)


def make_client(*, extra_headers: dict[str, str] | None = None) -> httpx.AsyncClient:
    headers = {"User-Agent": USER_AGENT}
    if extra_headers:
        headers.update(extra_headers)
    return httpx.AsyncClient(
        headers=headers,
        timeout=30.0,
        follow_redirects=True,
        event_hooks={"request": [_on_request], "response": [_on_response]},
    )


async def download_file(
    client: httpx.AsyncClient,
    url: str,
    dest: Path,
    *,
    sha1: str | None = None,
    sha512: str | None = None,
    progress_cb: ProgressCallback | None = None,
    max_retries: int = 3,
    cancel_event: threading.Event | None = None,
) -> Path:
    """Dosyayı indirir, hash doğrular. Uyuşmazsa dosyayı siler ve tekrar dener.

    cancel_event set edilmişse (kullanıcı export'u iptal ettiyse) indirme
    chunk aralarında kontrol edilip DownloadCancelledError ile durdurulur.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    last_error: Exception | None = None

    for attempt in range(1, max_retries + 1):
        if cancel_event is not None and cancel_event.is_set():
            raise DownloadCancelledError(f"{dest.name}: kullanıcı tarafından iptal edildi")
        # Benzersiz tmp dosyası (sabit bir ad DEĞİL): aynı dest'e eşzamanlı
        # iki indirme başlarsa (ör. kullanıcı "Hazırla"ya art arda hızlı
        # tıklarsa, ya da artık Qt VE web paneli aynı pack'i aynı anda
        # hazırlarsa) ikisi de AYNI tmp dosyasını kullanıp biri diğerini
        # rename'den önce silebiliyordu (gerçek bir FileNotFoundError
        # olarak web panelinde yakalandı) — her çağrı kendi tmp dosyasını
        # alınca bu çakışma artık mümkün değil.
        tmp_path = dest.with_name(f"{dest.name}.{uuid.uuid4().hex[:8]}.part")
        try:
            downloaded = 0
            async with client.stream("GET", url) as response:
                response.raise_for_status()
                total = int(response.headers.get("Content-Length", 0))
                with tmp_path.open("wb") as f:
                    async for chunk in response.aiter_bytes(64 * 1024):
                        if cancel_event is not None and cancel_event.is_set():
                            raise DownloadCancelledError(f"{dest.name}: kullanıcı tarafından iptal edildi")
                        f.write(chunk)
                        downloaded += len(chunk)
                        if progress_cb:
                            progress_cb(downloaded, total)
            tmp_path.replace(dest)
            if sha1 or sha512:
                verify_hashes(dest, sha1=sha1, sha512=sha512)
            log.debug("İndirildi: %s (%d bayt, deneme %d)", dest.name, downloaded, attempt)
            return dest
        except DownloadCancelledError:
            tmp_path.unlink(missing_ok=True)
            log.info("İndirme iptal edildi: %s", dest.name)
            raise
        except HashMismatchError as exc:
            dest.unlink(missing_ok=True)
            last_error = exc
            log.warning("Hash uyuşmazlığı (deneme %d/%d): %s", attempt, max_retries, exc)
        except httpx.HTTPError as exc:
            tmp_path.unlink(missing_ok=True)
            last_error = exc
            if isinstance(exc, httpx.RequestError):  # durum hataları zaten yanıt hook'unda kaydedildi
                NETWORK.record("GET", url, None, None, error=f"{type(exc).__name__}: {exc}")
            log.warning("İndirme hatası (deneme %d/%d) %s: %s", attempt, max_retries, dest.name, exc)
            await asyncio.sleep(min(2**attempt, 10))

    log.error("İndirme başarısız: %s (%d deneme) — son hata: %s", dest.name, max_retries, last_error)
    raise DownloadError(f"{dest.name} indirilemedi ({max_retries} denemeden sonra)") from last_error
