"""Mod ikonlarını (Modrinth/CurseForge icon_url) async indirip QPixmap
olarak sağlar — CurseForge/Modrinth/Prism launcher'larındaki "ikonlu kart"
görünümü için (proje-amacı.md §2.6 UI ilhamı: gerçek launcher'lardan)."""

from __future__ import annotations

import asyncio
from collections import OrderedDict
from collections.abc import Callable

import shiboken6
from PySide6.QtCore import QObject, Qt, QThread, Signal
from PySide6.QtGui import QImage, QPixmap

from mcpack.downloader import make_client

_MAX_CACHE_SIZE = 150
"""Sonsuz kaydırmayla yüzlerce mod gezilebilir — ikonları sınırsız biriktirmek
bellek sızıntısına yol açar. LRU: limit aşılınca en eski kullanılan atılır."""
_MAX_ICON_DIM = 96
"""Kartlarda 40px gösteriliyor; cache'te ham (ör. 512x512) boyutunu değil,
makul bir üst sınırla küçültülmüş halini tutuyoruz (bellek ~28x azalır)."""

_cache: "OrderedDict[str, QPixmap]" = OrderedDict()
_active: list[_IconWorker] = []


def _cache_get(url: str) -> QPixmap | None:
    pixmap = _cache.get(url)
    if pixmap is not None:
        _cache.move_to_end(url)
    return pixmap


def _cache_put(url: str, pixmap: QPixmap) -> None:
    _cache[url] = pixmap
    _cache.move_to_end(url)
    while len(_cache) > _MAX_CACHE_SIZE:
        _cache.popitem(last=False)


class _IconSignals(QObject):
    loaded = Signal(str, QImage)
    """QPixmap DEĞİL QImage: QPixmap sadece GUI thread'inde oluşturulabilir;
    worker thread'de oluşturmak heap bozulmasıyla rastgele çökmeye yol açıyordu
    ("malloc(): unaligned tcache chunk detected"). QImage thread-safe'tir,
    QPixmap'e dönüşüm on_loaded'da (GUI thread) yapılır."""


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
            image = QImage()
            if image.loadFromData(data):
                if image.width() > _MAX_ICON_DIM or image.height() > _MAX_ICON_DIM:
                    image = image.scaled(
                        _MAX_ICON_DIM,
                        _MAX_ICON_DIM,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    )
                self.signals.loaded.emit(self.url, image)


def load_icon(
    url: str | None,
    callback: Callable[[QPixmap], None],
    *,
    owner: object | None = None,
) -> None:
    """url'deki ikonu async indirir, hazır olunca callback(QPixmap) çağrılır.

    Daha önce indirilmiş bir URL varsa cache'den senkron döner.

    owner: callback'in dokunacağı Qt widget'ı (ör. bir QLabel). İndirme
    tamamlandığında bu widget artık yoksa (ör. kullanıcı hızlıca yeni bir
    arama yapıp listeyi temizlediyse) callback hiç çağrılmaz — aksi halde
    silinmiş bir C++ nesnesine erişim "libshiboken: already deleted"
    RuntimeError'ına ve uygulamanın çökmesine yol açar.
    """
    if not url:
        return
    cached = _cache_get(url)
    if cached is not None:
        if owner is None or shiboken6.isValid(owner):
            callback(cached)
        return

    worker = _IconWorker(url)
    _active.append(worker)

    def on_loaded(loaded_url: str, image: QImage) -> None:
        pixmap = QPixmap.fromImage(image)
        _cache_put(loaded_url, pixmap)
        if owner is not None and not shiboken6.isValid(owner):
            return
        try:
            callback(pixmap)
        except RuntimeError:
            pass  # ek güvenlik: owner verilmediyse veya callback başka silinmiş bir widget'a dokunduysa

    def cleanup() -> None:
        # finished, thread tamamen bitmeden yayınlanır; son referansı bırakmadan
        # önce bekle ki QThread hâlâ çalışırken silinmesin.
        worker.wait()
        if worker in _active:
            _active.remove(worker)

    worker.signals.loaded.connect(on_loaded)
    worker.finished.connect(cleanup)
    worker.start()
