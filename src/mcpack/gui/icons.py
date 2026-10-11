"""Mod/proje ikonu servisi.

Eski yükleyici HER ikon için ayrı bir QThread + ayrı bir asyncio loop + ayrı
bir HTTP istemcisi açıyordu (20 sonuçluk bir sayfa = 20 thread). Burada tek
bir arka plan thread'inde, kalıcı bir asyncio loop ve tek bir HTTP istemcisi
var; eşzamanlılık bir semafor ile sınırlanır. Ayrıca:

- Bellek içi LRU (QPixmap) + disk önbelleği (`<config_dir>/cache/icons/`),
  böylece uygulama yeniden açıldığında ikonlar ağa gitmeden gelir.
- QImage arka planda decode edilir (thread-safe), QPixmap'e dönüşüm SADECE
  GUI thread'inde yapılır (bkz. eski "malloc(): unaligned tcache chunk"
  çökmesi).
- Aynı URL için eşzamanlı istekler birleştirilir (tek indirme, çok alıcı).
- Callback'in dokunacağı widget silinmişse (shiboken6.isValid) çağrılmaz.
"""

from __future__ import annotations

import asyncio
import hashlib
import threading
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

import shiboken6
from PySide6.QtCore import QObject, Qt, Signal, Slot
from PySide6.QtGui import QImage, QPixmap

from mcpack.config import config_dir
from mcpack.downloader import make_client
from mcpack.logging_setup import get_logger

log = get_logger(__name__)

MAX_MEMORY_ITEMS = 300
MAX_ICON_DIM = 128
MAX_CONCURRENCY = 8


def icon_cache_dir() -> Path:
    path = config_dir() / "cache" / "icons"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _cache_path(url: str) -> Path:
    return icon_cache_dir() / (hashlib.sha1(url.encode("utf-8")).hexdigest() + ".png")


class IconService(QObject):
    _loaded = Signal(str, QImage)

    def __init__(self) -> None:
        super().__init__()
        self._memory: OrderedDict[str, QPixmap] = OrderedDict()
        self._waiting: dict[str, list[tuple[Callable[[QPixmap], None], object | None]]] = {}
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._ready = threading.Event()
        self.failures = 0
        self.downloads = 0
        self._loaded.connect(self._on_loaded, Qt.ConnectionType.QueuedConnection)

    # -- arka plan loop'u ----------------------------------------------------------

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is not None:
            return self._loop
        self._thread = threading.Thread(target=self._run_loop, name="icon-loader", daemon=True)
        self._thread.start()
        self._ready.wait(5)
        assert self._loop is not None
        return self._loop

    def _run_loop(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENCY)
        self._client = make_client()
        self._ready.set()
        try:
            loop.run_forever()
        finally:
            try:
                loop.run_until_complete(self._client.aclose())
            except Exception:  # noqa: BLE001
                pass
            loop.close()

    def shutdown(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)
            if self._thread is not None:
                self._thread.join(timeout=2)
            self._loop = None

    async def _fetch(self, url: str) -> None:
        disk = _cache_path(url)
        image = QImage()
        try:
            if disk.exists() and image.load(str(disk)):
                self._loaded.emit(url, image)
                return
            async with self._semaphore:
                response = await self._client.get(url, timeout=10.0)
                response.raise_for_status()
                data = response.content
            if not image.loadFromData(data):
                raise ValueError("decode edilemedi")
            if image.width() > MAX_ICON_DIM or image.height() > MAX_ICON_DIM:
                image = image.scaled(
                    MAX_ICON_DIM, MAX_ICON_DIM,
                    Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation,
                )
            try:
                image.save(str(disk), "PNG")
            except Exception:  # noqa: BLE001 - disk önbelleği opsiyonel
                pass
            self.downloads += 1
        except Exception as exc:  # noqa: BLE001 - ikon yüklenemezse sessizce yer tutucu kalır
            self.failures += 1
            log.debug("İkon yüklenemedi %s: %s", url, exc)
            image = QImage()
        self._loaded.emit(url, image)

    # -- GUI tarafı ----------------------------------------------------------------

    def load(self, url: str | None, callback: Callable[[QPixmap], None], *, owner: object | None = None) -> None:
        if not url:
            return
        cached = self._memory.get(url)
        if cached is not None:
            self._memory.move_to_end(url)
            if owner is None or shiboken6.isValid(owner):
                callback(cached)
            return
        waiters = self._waiting.setdefault(url, [])
        waiters.append((callback, owner))
        if len(waiters) > 1:
            return  # aynı URL zaten indiriliyor
        loop = self._ensure_loop()
        asyncio.run_coroutine_threadsafe(self._fetch(url), loop)

    @Slot(str, QImage)
    def _on_loaded(self, url: str, image: QImage) -> None:
        waiters = self._waiting.pop(url, [])
        if image.isNull():
            return
        pixmap = QPixmap.fromImage(image)
        self._memory[url] = pixmap
        self._memory.move_to_end(url)
        while len(self._memory) > MAX_MEMORY_ITEMS:
            self._memory.popitem(last=False)
        for callback, owner in waiters:
            if owner is not None and not shiboken6.isValid(owner):
                continue
            try:
                callback(pixmap)
            except RuntimeError:
                pass

    def stats(self) -> dict[str, int]:
        try:
            disk_files = sum(1 for _ in icon_cache_dir().glob("*.png"))
        except OSError:
            disk_files = 0
        return {
            "memory": len(self._memory),
            "pending": len(self._waiting),
            "downloads": self.downloads,
            "failures": self.failures,
            "disk": disk_files,
        }

    def clear(self) -> int:
        self._memory.clear()
        removed = 0
        for path in icon_cache_dir().glob("*.png"):
            try:
                path.unlink()
                removed += 1
            except OSError:
                pass
        return removed


_service: IconService | None = None


def icons() -> IconService:
    global _service
    if _service is None:
        _service = IconService()
    return _service
