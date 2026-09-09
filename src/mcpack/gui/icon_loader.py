"""Mod ikonlarını (Modrinth/CurseForge icon_url) async indirip QPixmap
olarak sağlar — CurseForge/Modrinth/Prism launcher'larındaki "ikonlu kart"
görünümü için (proje-amacı.md §2.6 UI ilhamı: gerçek launcher'lardan)."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QPixmap

from mcpack.downloader import make_client

_cache: dict[str, QPixmap] = {}
_active: list[_IconWorker] = []


class _IconSignals(QObject):
    loaded = Signal(str, QPixmap)


class _IconWorker(QThread):
    def __init__(self, url: str) -> None:
        super().__init__()
        self.url = url
        self.signals = _IconSignals()

    def run(self) -> None:
        async def fetch() -> bytes | None:
            try:
                async with make_client() as client:
                    response = await client.get(self.url, timeout=10.0)
                    response.raise_for_status()
                    return response.content
            except Exception:  # ikon indirilemezse sessizce vazgeç
                return None

        data = asyncio.run(fetch())
        if data:
            pixmap = QPixmap()
            if pixmap.loadFromData(data):
                self.signals.loaded.emit(self.url, pixmap)


def load_icon(url: str | None, callback: Callable[[QPixmap], None]) -> None:
    """url'deki ikonu async indirir, hazır olunca callback(QPixmap) çağrılır.

    Daha önce indirilmiş bir URL varsa cache'den senkron döner.
    """
    if not url:
        return
    if url in _cache:
        callback(_cache[url])
        return

    worker = _IconWorker(url)
    _active.append(worker)

    def on_loaded(loaded_url: str, pixmap: QPixmap) -> None:
        _cache[loaded_url] = pixmap
        callback(pixmap)

    def cleanup() -> None:
        if worker in _active:
            _active.remove(worker)

    worker.signals.loaded.connect(on_loaded)
    worker.finished.connect(cleanup)
    worker.start()
