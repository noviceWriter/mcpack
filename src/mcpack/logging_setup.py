"""Merkezi loglama + hata ayıklama altyapısı.

Önceden hiç loglama yoktu: hatalar sadece `traceback.print_exc()` ile
terminale basılıyordu — PyInstaller ile paketlenmiş (konsolsuz) sürümde bu
çıktı tamamen kayboluyor, kullanıcı "çöktü" dediğinde elde hiçbir iz
kalmıyordu. Burası üç hedefe aynı anda yazar:

1. Dönen log dosyası: `<config_dir>/logs/mcpack.log` (2 MB x 5 yedek).
2. stderr (geliştirici terminalden çalıştırıyorsa).
3. Bellekte halka tampon (`MEMORY_HANDLER`) — GUI'deki Geliştirici sayfası
   ve web panelinin /api/logs uç noktası canlı log akışını buradan okur.

Ek olarak:
- `install_exception_hooks()` sys/threading/unraisable hook'larını kurar;
  yakalanmamış her istisna loglanır ve `logs/crash/` altına sistem bilgisiyle
  birlikte bir crash raporu yazılır.
- `NETWORK` — downloader.make_client'ın httpx event hook'larının doldurduğu
  ağ isteği kaydı (yöntem/URL/durum/süre). Başlıklar (dolayısıyla CurseForge
  `x-api-key`) ASLA kaydedilmez; URL'deki kullanıcı:şifre kısmı maskelenir.
- `EXCEPTIONS` — yakalanan/yakalanmayan istisnaların özet listesi (tekrar
  sayısıyla), Geliştirici sayfasındaki "İstisnalar" sekmesi için.

Debug modu: `MCPACK_DEBUG=1` ortam değişkeni, `mcpack --debug` ya da
çalışma anında `set_debug(True)` — mcpack logger'larını DEBUG seviyesine
indirir (ağ istekleri dahil her şey loglanır).
"""

from __future__ import annotations

import logging
import logging.handlers
import os
import platform
import sys
import threading
import time
import traceback
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

LOGGER_NAME = "mcpack"
LOG_FILE_NAME = "mcpack.log"
LOG_FORMAT = "%(asctime)s.%(msecs)03d %(levelname)-8s [%(threadName)s] %(name)s: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
MEMORY_BUFFER_SIZE = 5000
NETWORK_BUFFER_SIZE = 1000
EXCEPTION_BUFFER_SIZE = 200


def get_logger(name: str) -> logging.Logger:
    """Modüller `log = get_logger(__name__)` ile alır — `mcpack.` öneki
    yoksa eklenir ki hepsi aynı kök logger'ın altında toplansın."""
    if name != LOGGER_NAME and not name.startswith(LOGGER_NAME + "."):
        name = f"{LOGGER_NAME}.{name}"
    return logging.getLogger(name)


def logs_dir() -> Path:
    # config_dir import'u burada (fonksiyon içinde): config.py ileride
    # logger kullanırsa döngüsel import olmasın.
    from mcpack.config import config_dir

    path = config_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def crash_dir() -> Path:
    path = logs_dir() / "crash"
    path.mkdir(parents=True, exist_ok=True)
    return path


# -- bellek tamponu -------------------------------------------------------------


@dataclass(frozen=True)
class LogEntry:
    seq: int
    created: float
    level: str
    levelno: int
    logger: str
    message: str
    thread: str
    exc_text: str | None = None

    @property
    def time_text(self) -> str:
        return datetime.fromtimestamp(self.created).strftime("%H:%M:%S.%f")[:-3]

    def format_line(self) -> str:
        line = f"{self.time_text} {self.level:<8} [{self.thread}] {self.logger}: {self.message}"
        if self.exc_text:
            line += "\n" + self.exc_text
        return line

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "created": self.created,
            "time": self.time_text,
            "level": self.level,
            "levelno": self.levelno,
            "logger": self.logger,
            "message": self.message,
            "thread": self.thread,
            "exc_text": self.exc_text,
        }


LogSubscriber = Callable[[LogEntry], None]


class MemoryLogHandler(logging.Handler):
    """Son N kaydı tutan, thread-safe halka tampon + abonelik.

    Aboneler (GUI log görüntüleyicisi, web paneli WebSocket'i) kaydı
    yayınlayan HER thread'den çağrılır — GUI tarafı bunu kendi Qt sinyaline
    (QueuedConnection) çevirmekle yükümlüdür, burada widget'a dokunulmaz."""

    def __init__(self, capacity: int = MEMORY_BUFFER_SIZE) -> None:
        super().__init__(level=logging.DEBUG)
        self._buffer: deque[LogEntry] = deque(maxlen=capacity)
        self._lock_ = threading.Lock()
        self._seq = 0
        self._subscribers: list[LogSubscriber] = []

    def emit(self, record: logging.LogRecord) -> None:
        try:
            message = record.getMessage()
        except Exception:  # noqa: BLE001 - bozuk format argümanları loglamayı düşürmesin
            message = str(record.msg)
        exc_text = None
        if record.exc_info:
            exc_text = "".join(traceback.format_exception(*record.exc_info)).rstrip()
        elif record.exc_text:
            exc_text = record.exc_text
        with self._lock_:
            self._seq += 1
            entry = LogEntry(
                seq=self._seq,
                created=record.created,
                level=record.levelname,
                levelno=record.levelno,
                logger=record.name,
                message=message,
                thread=record.threadName or "?",
                exc_text=exc_text,
            )
            self._buffer.append(entry)
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(entry)
            except Exception:  # noqa: BLE001 - bir abonenin hatası diğerlerini etkilemesin
                pass

    def snapshot(
        self, *, min_level: int = 0, after_seq: int = 0, limit: int | None = None
    ) -> list[LogEntry]:
        with self._lock_:
            items = [e for e in self._buffer if e.levelno >= min_level and e.seq > after_seq]
        if limit is not None:
            items = items[-limit:]
        return items

    def clear(self) -> None:
        with self._lock_:
            self._buffer.clear()

    def subscribe(self, callback: LogSubscriber) -> None:
        with self._lock_:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: LogSubscriber) -> None:
        with self._lock_:
            if callback in self._subscribers:
                self._subscribers.remove(callback)


MEMORY_HANDLER = MemoryLogHandler()


# -- ağ isteği kaydı ---------------------------------------------------------------


def mask_url(url: str) -> str:
    """URL'deki kullanıcı:şifre kısmını maskeler (başlıklar zaten hiç
    kaydedilmiyor — CurseForge anahtarı `x-api-key` başlığında)."""
    try:
        parts = urlsplit(url)
    except ValueError:
        return url
    if parts.username or parts.password:
        host = parts.hostname or ""
        if parts.port:
            host = f"{host}:{parts.port}"
        parts = parts._replace(netloc=f"***@{host}")
    return urlunsplit(parts)


@dataclass(frozen=True)
class NetworkEvent:
    seq: int
    created: float
    method: str
    url: str
    status: int | None
    elapsed_ms: float | None
    error: str | None = None

    @property
    def host(self) -> str:
        return urlsplit(self.url).hostname or ""

    def to_dict(self) -> dict:
        return {
            "seq": self.seq,
            "created": self.created,
            "method": self.method,
            "url": self.url,
            "host": self.host,
            "status": self.status,
            "elapsed_ms": self.elapsed_ms,
            "error": self.error,
        }


class _RingRecorder:
    def __init__(self, capacity: int) -> None:
        self._buffer: deque = deque(maxlen=capacity)
        self._lock = threading.Lock()
        self._seq = 0
        self._subscribers: list[Callable[[object], None]] = []

    def _next_seq(self) -> int:
        self._seq += 1
        return self._seq

    def _publish(self, item: object) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(item)
            except Exception:  # noqa: BLE001
                pass

    def snapshot(self) -> list:
        with self._lock:
            return list(self._buffer)

    def clear(self) -> None:
        with self._lock:
            self._buffer.clear()

    def subscribe(self, callback: Callable[[object], None]) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[object], None]) -> None:
        with self._lock:
            if callback in self._subscribers:
                self._subscribers.remove(callback)


class NetworkRecorder(_RingRecorder):
    def record(
        self,
        method: str,
        url: str,
        status: int | None,
        elapsed_ms: float | None,
        error: str | None = None,
    ) -> NetworkEvent:
        with self._lock:
            event = NetworkEvent(
                seq=self._next_seq(),
                created=time.time(),
                method=method,
                url=mask_url(url),
                status=status,
                elapsed_ms=elapsed_ms,
                error=error,
            )
            self._buffer.append(event)
        self._publish(event)
        return event

    def stats(self) -> dict:
        events = self.snapshot()
        total = len(events)
        failed = sum(1 for e in events if e.error or (e.status is not None and e.status >= 400))
        timings = [e.elapsed_ms for e in events if e.elapsed_ms is not None]
        return {
            "total": total,
            "failed": failed,
            "avg_ms": (sum(timings) / len(timings)) if timings else None,
            "max_ms": max(timings) if timings else None,
        }


NETWORK = NetworkRecorder(NETWORK_BUFFER_SIZE)


# -- istisna kaydı ---------------------------------------------------------------


@dataclass
class ExceptionEvent:
    key: str
    type_name: str
    message: str
    traceback_text: str
    origin: str
    first_seen: float
    last_seen: float
    count: int = 1
    crash_report: str | None = None
    extra: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "key": self.key,
            "type": self.type_name,
            "message": self.message,
            "traceback": self.traceback_text,
            "origin": self.origin,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "count": self.count,
            "crash_report": self.crash_report,
        }


class ExceptionRecorder(_RingRecorder):
    """Aynı istisna (tip + mesaj + son çerçeve) tekrarlanırsa yeni satır
    eklenmez, sayacı artırılır — döngüde patlayan bir hata listeyi
    doldurmasın."""

    def record(
        self, exc: BaseException, *, origin: str, crash_report: str | None = None
    ) -> ExceptionEvent:
        tb_text = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip()
        frames = traceback.extract_tb(exc.__traceback__) if exc.__traceback__ else []
        last = f"{frames[-1].filename}:{frames[-1].lineno}" if frames else ""
        key = f"{type(exc).__name__}|{exc}|{last}"
        now = time.time()
        with self._lock:
            existing = next((e for e in self._buffer if e.key == key), None)
            if existing is not None:
                existing.count += 1
                existing.last_seen = now
                if crash_report:
                    existing.crash_report = crash_report
                event = existing
            else:
                event = ExceptionEvent(
                    key=key,
                    type_name=type(exc).__name__,
                    message=str(exc),
                    traceback_text=tb_text,
                    origin=origin,
                    first_seen=now,
                    last_seen=now,
                    crash_report=crash_report,
                )
                self._buffer.append(event)
        self._publish(event)
        return event


EXCEPTIONS = ExceptionRecorder(EXCEPTION_BUFFER_SIZE)


def record_exception(exc: BaseException, *, origin: str, logger: logging.Logger | None = None) -> None:
    """Yakalanmış (GUI'ye kullanıcı dostu mesaj olarak giden) bir istisnayı
    tam traceback'iyle loglar ve İstisnalar listesine ekler."""
    (logger or get_logger("errors")).error(
        "%s: %s", origin, exc, exc_info=(type(exc), exc, exc.__traceback__)
    )
    EXCEPTIONS.record(exc, origin=origin)


# -- sistem bilgisi / crash raporu -------------------------------------------------


def app_version() -> str:
    # Tek doğruluk kaynağı paketin kendi __version__'ı — importlib.metadata
    # editable kurulumda eski (kurulum anındaki) sürümü döndürebiliyor.
    from mcpack import __version__

    return __version__


def system_info() -> dict[str, str]:
    info: dict[str, str] = {
        "mcpack": app_version(),
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "executable": sys.executable,
        "frozen": str(bool(getattr(sys, "frozen", False))),
        "pid": str(os.getpid()),
        "cwd": str(Path.cwd()),
    }
    try:
        from PySide6 import __version__ as pyside_version
        from PySide6.QtCore import qVersion

        info["pyside6"] = pyside_version
        info["qt"] = qVersion()
    except Exception:  # noqa: BLE001
        pass
    for module in ("httpx", "pydantic", "fastapi", "uvicorn"):
        try:
            mod = __import__(module)
            info[module] = getattr(mod, "__version__", "?")
        except Exception:  # noqa: BLE001
            pass
    try:
        from mcpack.config import config_dir

        info["config_dir"] = str(config_dir())
        info["log_dir"] = str(logs_dir())
    except Exception:  # noqa: BLE001
        pass
    try:
        from mcpack.server_runtime import get_system_memory_mb

        total = get_system_memory_mb()
        if total:
            info["memory_total"] = f"{total / 1024:.1f} GB"
    except Exception:  # noqa: BLE001
        pass
    info["debug"] = str(is_debug())
    return info


def write_crash_report(exc: BaseException, *, origin: str) -> Path | None:
    try:
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        path = crash_dir() / f"crash-{stamp}-{os.getpid()}.txt"
        lines = [
            f"mcpack crash report — {datetime.now().isoformat(timespec='seconds')}",
            f"origin: {origin}",
            "",
            "== system ==",
            *(f"{k}: {v}" for k, v in system_info().items()),
            "",
            "== traceback ==",
            "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)).rstrip(),
            "",
            "== last log lines ==",
            *(e.format_line() for e in MEMORY_HANDLER.snapshot(limit=200)),
            "",
        ]
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
    except Exception:  # noqa: BLE001 - crash raporu yazılamazsa asıl hatayı örtmesin
        return None


def list_crash_reports() -> list[Path]:
    try:
        return sorted(crash_dir().glob("crash-*.txt"), reverse=True)
    except OSError:
        return []


def _handle_uncaught(exc: BaseException, origin: str) -> None:
    report = write_crash_report(exc, origin=origin)
    get_logger("crash").critical(
        "Yakalanmamış istisna (%s)%s",
        origin,
        f" — crash raporu: {report}" if report else "",
        exc_info=(type(exc), exc, exc.__traceback__),
    )
    EXCEPTIONS.record(exc, origin=origin, crash_report=str(report) if report else None)


_hooks_installed = False


def install_exception_hooks() -> None:
    """sys.excepthook / threading.excepthook / sys.unraisablehook. Qt'nin
    kendi mesajları için bkz. gui/app.py (qInstallMessageHandler) — burası
    Qt'ye bağımlı değil, CLI/web paneli de kullanabilir."""
    global _hooks_installed
    if _hooks_installed:
        return
    _hooks_installed = True

    previous_excepthook = sys.excepthook

    def excepthook(exc_type, exc, tb) -> None:
        if issubclass(exc_type, KeyboardInterrupt):
            previous_excepthook(exc_type, exc, tb)
            return
        if exc.__traceback__ is None:
            exc = exc.with_traceback(tb)
        _handle_uncaught(exc, "main-thread")

    def thread_excepthook(args: threading.ExceptHookArgs) -> None:
        if args.exc_value is None or isinstance(args.exc_value, SystemExit):
            return
        name = args.thread.name if args.thread is not None else "?"
        _handle_uncaught(args.exc_value, f"thread:{name}")

    def unraisablehook(unraisable) -> None:
        exc = unraisable.exc_value
        if exc is None:
            return
        get_logger("unraisable").warning(
            "Unraisable istisna: %s (%r)",
            unraisable.err_msg or "",
            unraisable.object,
            exc_info=(type(exc), exc, unraisable.exc_traceback),
        )
        EXCEPTIONS.record(exc, origin="unraisable")

    sys.excepthook = excepthook
    threading.excepthook = thread_excepthook
    sys.unraisablehook = unraisablehook


def asyncio_exception_handler(loop, context: dict) -> None:
    """asyncio.run ile açılan her loop'a (bkz. gui/tasks.py) takılır —
    "Task exception was never retrieved" gibi sessizce kaybolan hataları
    loglar."""
    exc = context.get("exception")
    message = context.get("message", "asyncio hatası")
    if exc is not None:
        get_logger("asyncio").error("%s", message, exc_info=(type(exc), exc, exc.__traceback__))
        EXCEPTIONS.record(exc, origin="asyncio")
    else:
        get_logger("asyncio").error("%s", message)


# -- kurulum ---------------------------------------------------------------------

_configured = False
_debug = False
_file_handler: logging.Handler | None = None
_stderr_handler: logging.Handler | None = None


def is_debug() -> bool:
    return _debug


def set_debug(enabled: bool) -> None:
    """Çalışma anında DEBUG seviyesini aç/kapat. Dosya ve bellek her zaman
    DEBUG kabul eder; filtreleme mcpack logger seviyesinde yapılır."""
    global _debug
    _debug = enabled
    level = logging.DEBUG if enabled else logging.INFO
    logging.getLogger(LOGGER_NAME).setLevel(level)
    if _stderr_handler is not None:
        _stderr_handler.setLevel(logging.DEBUG if enabled else logging.WARNING)
    get_logger("logging").info("Debug modu %s", "AÇIK" if enabled else "kapalı")


def log_file_path() -> Path:
    return logs_dir() / LOG_FILE_NAME


def setup_logging(*, debug: bool | None = None, to_file: bool = True, to_stderr: bool = True) -> None:
    """Idempotent: birden çok kez çağrılabilir (GUI, CLI, testler)."""
    global _configured, _file_handler, _stderr_handler
    if debug is None:
        debug = os.environ.get("MCPACK_DEBUG", "").strip().lower() in {"1", "true", "yes", "on"}

    root = logging.getLogger(LOGGER_NAME)
    if not _configured:
        _configured = True
        root.propagate = False
        formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
        root.addHandler(MEMORY_HANDLER)

        if to_file:
            try:
                _file_handler = logging.handlers.RotatingFileHandler(
                    log_file_path(), maxBytes=2 * 1024 * 1024, backupCount=5, encoding="utf-8"
                )
                _file_handler.setFormatter(formatter)
                _file_handler.setLevel(logging.DEBUG)
                root.addHandler(_file_handler)
            except OSError as exc:  # salt-okunur dizin vb. — dosyasız devam
                if sys.stderr is not None:
                    sys.stderr.write(f"mcpack: log dosyası açılamadı: {exc}\n")

        # PyInstaller --windowed (konsolsuz) derlemede sys.stderr None'dır.
        if to_stderr and sys.stderr is not None:
            _stderr_handler = logging.StreamHandler(sys.stderr)
            _stderr_handler.setFormatter(formatter)
            root.addHandler(_stderr_handler)

        # Üçüncü taraf kütüphanelerin uyarıları da dosyaya düşsün.
        for name in ("httpx", "uvicorn.error", "asyncio"):
            third = logging.getLogger(name)
            third.setLevel(logging.WARNING)
            third.addHandler(MEMORY_HANDLER)
            if _file_handler is not None:
                third.addHandler(_file_handler)

    set_debug(debug)
    root.info("mcpack %s başlatıldı (python %s, %s)", app_version(), sys.version.split()[0], platform.platform())
