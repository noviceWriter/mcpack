"""Arka plan görev yöneticisi.

Eski `run_async` her coroutine'i bir QThread'de çalıştırıyordu ama iki
önemli sorunu vardı:

1. İlerleme callback'i (`progress_cb=self.set_progress`) arka plan
   thread'inden DOĞRUDAN bir QProgressBar'a dokunuyordu — Qt widget'ları
   sadece GUI thread'inden değiştirilebilir; bu, daha önce QPixmap'te
   yaşanan rastgele çökmelerle aynı sınıftan bir hataydı.
2. Hiçbir iz bırakmıyordu: hangi görev ne zaman başladı/bitti/neden
   patladı, sadece terminale basılan bir traceback vardı.

Burada her görev bir `Task` kaydıdır (başlık, durum, ilerleme, süre, hata,
tam traceback) ve TaskManager'ın sinyalleriyle izlenir (durum çubuğu,
Geliştirici > Görevler sekmesi). İlerleme `TaskContext.progress()` ile
bildirilir; bu fonksiyon thread-safe'tir (sinyal + QueuedConnection) ve
GUI'yi boğmamak için kısıtlanır (throttle). Tüm callback'ler (on_success/
on_error) GARANTİLİ olarak GUI thread'inde çağrılır.
"""

from __future__ import annotations

import asyncio
import itertools
import threading
import time
import traceback
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

import shiboken6
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot

from mcpack.downloader import DownloadCancelledError
from mcpack.logging_setup import EXCEPTIONS, asyncio_exception_handler, get_logger

log = get_logger(__name__)

def _expected_errors() -> tuple[type[BaseException], ...]:
    """Kullanıcıya anlaşılır mesajla gösterilen, program hatası OLMAYAN
    durumlar (geçersiz API anahtarı, ağ hatası, uyumlu sürüm yok, Java yok…).
    Bunlar tek satırlık WARNING olarak loglanır ve İstisnalar listesine
    eklenmez; tam traceback yine görev ayrıntısında ve DEBUG logunda durur."""
    from mcpack.downloader import DownloadError
    from mcpack.gameinfo import GameInfoError
    from mcpack.launcher import SKLauncherError
    from mcpack.server_jar import ServerDownloadError
    from mcpack.server_runtime import ServerRuntimeError
    from mcpack.sources.base import SourceAPIError
    from mcpack.sources.cheat_mods import CheatModUnavailableError
    from mcpack.sources.curseforge import CurseForgeConfigError

    return (
        SourceAPIError, CurseForgeConfigError, DownloadError, GameInfoError, ServerDownloadError,
        ServerRuntimeError, SKLauncherError, CheatModUnavailableError,
    )


PROGRESS_THROTTLE_S = 0.05
HISTORY_LIMIT = 300

QUEUED = "queued"
RUNNING = "running"
DONE = "done"
FAILED = "failed"
CANCELLED = "cancelled"


@dataclass
class Task:
    id: int
    title: str
    category: str = "general"
    cancellable: bool = False
    silent: bool = False
    """True ise durum çubuğunda/bildirimlerde gösterilmez (ör. ikon yükleme,
    oyuncu listesi yoklaması) — yine de Görevler sekmesinde görünür."""
    status: str = QUEUED
    done: int = 0
    total: int = 0
    message: str = ""
    started_at: float | None = None
    ended_at: float | None = None
    error: str | None = None
    traceback_text: str | None = None
    cancel_event: threading.Event = field(default_factory=threading.Event)

    @property
    def is_active(self) -> bool:
        return self.status in (QUEUED, RUNNING)

    @property
    def duration(self) -> float | None:
        if self.started_at is None:
            return None
        return (self.ended_at or time.time()) - self.started_at

    @property
    def fraction(self) -> float | None:
        if self.total <= 0:
            return None
        return max(0.0, min(1.0, self.done / self.total))


class TaskContext:
    """Coroutine'e verilen bağlam: ilerleme bildirimi + iptal bayrağı."""

    def __init__(self, task: Task, emit_progress: Callable[[int, int, int, str], None]) -> None:
        self._task = task
        self._emit = emit_progress
        self._last_emit = 0.0
        self.cancel_event = task.cancel_event

    @property
    def cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def progress(self, done: int, total: int, message: str = "") -> None:
        """Her thread'den güvenle çağrılabilir. Sık çağrılar kısıtlanır,
        son adım (done >= total) her zaman iletilir."""
        now = time.monotonic()
        if done < total and now - self._last_emit < PROGRESS_THROTTLE_S and not message:
            return
        self._last_emit = now
        self._emit(self._task.id, done, total, message)

    def message(self, text: str) -> None:
        self._emit(self._task.id, self._task.done, self._task.total, text)


CoroFactory = Callable[[TaskContext], Awaitable[Any]]


class _Worker(QThread):
    def __init__(self, task: Task, factory: CoroFactory, bridge: "_Bridge") -> None:
        super().__init__()
        self.task = task
        self._factory = factory
        self._bridge = bridge
        self.setObjectName(f"task-{task.id}")

    def run(self) -> None:
        ctx = TaskContext(self.task, self._bridge.progress.emit)
        self._bridge.started.emit(self.task.id)
        loop = asyncio.new_event_loop()
        loop.set_exception_handler(asyncio_exception_handler)
        try:
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._factory(ctx))
        except DownloadCancelledError as exc:
            self._bridge.cancelled.emit(self.task.id, str(exc))
        except BaseException as exc:  # noqa: BLE001 - görevin her hatası GUI'ye iletilir
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
            expected = isinstance(exc, _expected_errors())
            if not expected:
                EXCEPTIONS.record(exc, origin=f"task:{self.task.title}")
            self._bridge.failed.emit(self.task.id, str(exc) or type(exc).__name__, tb, expected)
        else:
            self._bridge.succeeded.emit(self.task.id, result)
        finally:
            try:
                pending = asyncio.all_tasks(loop)
                for p in pending:
                    p.cancel()
                if pending:
                    loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:  # noqa: BLE001
                pass
            asyncio.set_event_loop(None)
            loop.close()


class _Bridge(QObject):
    """Worker thread'lerinden yayılan sinyaller — TaskManager (GUI thread)
    bunları QueuedConnection ile alır."""

    started = Signal(int)
    progress = Signal(int, int, int, str)
    succeeded = Signal(int, object)
    failed = Signal(int, str, str, bool)
    cancelled = Signal(int, str)


class TaskManager(QObject):
    task_added = Signal(object)
    task_updated = Signal(object)
    task_finished = Signal(object)
    active_count_changed = Signal(int)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._ids = itertools.count(1)
        self._tasks: dict[int, Task] = {}
        self._order: list[int] = []
        self._workers: dict[int, _Worker] = {}
        self._callbacks: dict[int, tuple] = {}
        self._bridge = _Bridge()
        q = Qt.ConnectionType.QueuedConnection
        self._bridge.started.connect(self._on_started, q)
        self._bridge.progress.connect(self._on_progress, q)
        self._bridge.succeeded.connect(self._on_succeeded, q)
        self._bridge.failed.connect(self._on_failed, q)
        self._bridge.cancelled.connect(self._on_cancelled, q)

    # -- genel API ---------------------------------------------------------------

    def run(
        self,
        title: str,
        factory: CoroFactory,
        *,
        on_success: Callable[[Any], None] | None = None,
        on_error: Callable[[str], None] | None = None,
        on_finally: Callable[[], None] | None = None,
        cancellable: bool = False,
        silent: bool = False,
        category: str = "general",
        owner: QObject | None = None,
    ) -> Task:
        """owner: callback'lerin dokunduğu widget/diyalog. Görev bittiğinde
        owner silinmişse (ör. diyalog kapatıldı) callback'ler çağrılmaz."""
        task = Task(id=next(self._ids), title=title, cancellable=cancellable, silent=silent, category=category)
        self._tasks[task.id] = task
        self._order.append(task.id)
        self._trim_history()
        self._callbacks[task.id] = (on_success, on_error, on_finally, owner)
        worker = _Worker(task, factory, self._bridge)
        self._workers[task.id] = worker
        # Lambda DEĞİL bound slot: finished worker thread'inden yayılıyor,
        # bir QObject alıcı olmadan bağlanan lambda o thread'de çalışabilir.
        worker.finished.connect(self._on_worker_finished, Qt.ConnectionType.QueuedConnection)
        (log.debug if silent else log.info)("Görev #%d başladı: %s", task.id, title)
        self.task_added.emit(task)
        self.active_count_changed.emit(self.active_count())
        worker.start()
        return task

    def cancel(self, task_id: int) -> None:
        task = self._tasks.get(task_id)
        if task is not None and task.is_active and task.cancellable:
            task.cancel_event.set()
            task.message = "…"
            log.info("Görev #%d iptal isteniyor: %s", task.id, task.title)
            self.task_updated.emit(task)

    def cancel_all(self) -> None:
        for task in self.active_tasks():
            task.cancel_event.set()

    def tasks(self) -> list[Task]:
        return [self._tasks[i] for i in self._order if i in self._tasks]

    def active_tasks(self, *, include_silent: bool = True) -> list[Task]:
        return [t for t in self.tasks() if t.is_active and (include_silent or not t.silent)]

    def active_count(self, *, include_silent: bool = False) -> int:
        return len(self.active_tasks(include_silent=include_silent))

    def clear_finished(self) -> None:
        self._order = [i for i in self._order if self._tasks[i].is_active]
        self._tasks = {i: self._tasks[i] for i in self._order}

    def wait_all(self, timeout_ms: int = 3000) -> None:
        deadline = time.monotonic() + timeout_ms / 1000
        for worker in list(self._workers.values()):
            remaining = max(0, int((deadline - time.monotonic()) * 1000))
            worker.wait(remaining)

    # -- iç ----------------------------------------------------------------------

    def _trim_history(self) -> None:
        while len(self._order) > HISTORY_LIMIT:
            oldest = next((i for i in self._order if not self._tasks[i].is_active), None)
            if oldest is None:
                break
            self._order.remove(oldest)
            self._tasks.pop(oldest, None)

    @Slot()
    def _on_worker_finished(self) -> None:
        worker = self.sender()
        if not isinstance(worker, _Worker):
            return
        self._workers.pop(worker.task.id, None)
        worker.wait()
        worker.deleteLater()

    def _finish(self, task: Task, status: str) -> None:
        task.status = status
        task.ended_at = time.time()
        self.task_finished.emit(task)
        self.task_updated.emit(task)
        self.active_count_changed.emit(self.active_count())

    @Slot(int)
    def _on_started(self, task_id: int) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.status = RUNNING
        task.started_at = time.time()
        self.task_updated.emit(task)

    @Slot(int, int, int, str)
    def _on_progress(self, task_id: int, done: int, total: int, message: str) -> None:
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.done, task.total = done, total
        if message:
            task.message = message
        self.task_updated.emit(task)

    def _take_callbacks(self, task_id: int):
        on_success, on_error, on_finally, owner = self._callbacks.pop(task_id, (None, None, None, None))
        if owner is not None and not shiboken6.isValid(owner):
            return None, None, None
        return on_success, on_error, on_finally

    def _safe_call(self, task: Task, fn: Callable | None, *args: Any) -> None:
        if fn is None:
            return
        try:
            fn(*args)
        except Exception as exc:  # noqa: BLE001 - callback hatası tüm uygulamayı düşürmesin
            log.exception("Görev #%d callback hatası (%s)", task.id, task.title)
            EXCEPTIONS.record(exc, origin=f"callback:{task.title}")

    @Slot(int, object)
    def _on_succeeded(self, task_id: int, result: object) -> None:
        task = self._tasks.get(task_id)
        on_success, _on_error, on_finally = self._take_callbacks(task_id)
        if task is None:
            return
        self._finish(task, DONE)
        (log.debug if task.silent else log.info)(
            "Görev #%d tamamlandı (%.2fs): %s", task.id, task.duration or 0, task.title
        )
        self._safe_call(task, on_success, result)
        self._safe_call(task, on_finally)

    @Slot(int, str, str, bool)
    def _on_failed(self, task_id: int, message: str, tb: str, expected: bool = False) -> None:
        task = self._tasks.get(task_id)
        _on_success, on_error, on_finally = self._take_callbacks(task_id)
        if task is None:
            return
        task.error = message
        task.traceback_text = tb
        self._finish(task, FAILED)
        if expected:
            log.warning("Görev #%d başarısız (%.2fs): %s — %s", task.id, task.duration or 0, task.title, message)
            log.debug("Görev #%d traceback:\n%s", task.id, tb)
        else:
            (log.warning if task.silent else log.error)(
                "Görev #%d başarısız (%.2fs): %s — %s\n%s", task.id, task.duration or 0, task.title, message, tb
            )
        self._safe_call(task, on_error, message)
        self._safe_call(task, on_finally)

    @Slot(int, str)
    def _on_cancelled(self, task_id: int, message: str) -> None:
        task = self._tasks.get(task_id)
        _on_success, _on_error, on_finally = self._take_callbacks(task_id)
        if task is None:
            return
        task.error = message
        self._finish(task, CANCELLED)
        log.info("Görev #%d iptal edildi: %s", task.id, task.title)
        self._safe_call(task, on_finally)
