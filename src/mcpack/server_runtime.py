"""Yerel bir Minecraft sunucusunu hazırlama, kurma (Forge/NeoForge installer)
ve çalıştırma (başlat/durdur/komut gönder/canlı konsol).

export/server.py'den farkı: o bir ZIP üretir (kullanıcı başka yere taşıyıp
elle çalıştırır), burası pack'in KENDİ kalıcı server_root'unda (bkz.
PackManager.server_root) gerçek, tekrar tekrar güncellenebilen bir kurulum
tutar ve onu doğrudan `java` ile mcpack içinden başlatıp konsolunu canlı
gösterir.

Kullanıcı isteği: "sağlam bir sunucu yönetim kısmı" — ayrı bir terminale
hiç gitmeden pack'i aç, hazırla, başlat, konsolu gör, komut yaz, durdur.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import threading
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Literal

import httpx
from PySide6.QtCore import QObject, Signal

from mcpack.downloader import DownloadCancelledError
from mcpack.export.base import ProgressCallback, collect_world_files, ensure_mods_downloaded
from mcpack.export.server import ensure_server_file_downloaded, filter_server_mods
from mcpack.i18n import t
from mcpack.models import Pack
from mcpack.server_jar import ServerDownload, ServerDownloadError, get_server_download

SYSTEM_MEMORY_RESERVE_MB = 2048
"""Kullanıcı isteği: "16 GB RAM'i olan birinin bilgisayarı en fazla 14 GB
kullansın, kullanıcıya en az 2 GB bıraksın" — sunucuya ayrılabilecek üst
sınır her zaman (toplam RAM - bu pay) olur, sistem donmasın/takılmasın."""


def _linux_total_memory_mb() -> int | None:
    try:
        with open("/proc/meminfo", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) // 1024
    except (OSError, ValueError, IndexError):
        pass
    return None


def _macos_total_memory_mb() -> int | None:
    try:
        result = subprocess.run(
            ["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=5, check=True
        )
        return int(result.stdout.strip()) // (1024 * 1024)
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


def _windows_total_memory_mb() -> int | None:
    try:
        import ctypes

        class _MEMORYSTATUSEX(ctypes.Structure):
            _fields_ = [
                ("dwLength", ctypes.c_ulong),
                ("dwMemoryLoad", ctypes.c_ulong),
                ("ullTotalPhys", ctypes.c_ulonglong),
                ("ullAvailPhys", ctypes.c_ulonglong),
                ("ullTotalPageFile", ctypes.c_ulonglong),
                ("ullAvailPageFile", ctypes.c_ulonglong),
                ("ullTotalVirtual", ctypes.c_ulonglong),
                ("ullAvailVirtual", ctypes.c_ulonglong),
                ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
            ]

        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):  # type: ignore[attr-defined]
            return int(stat.ullTotalPhys // (1024 * 1024))
    except Exception:  # noqa: BLE001 - tespit edilemezse None, sert bir hata değil
        pass
    return None


def get_system_memory_mb() -> int | None:
    """Sistemdeki TOPLAM fiziksel RAM'i MB cinsinden döner — hiçbir ek
    bağımlılık (psutil vb.) gerektirmez. Tespit edilemezse None (çağıran
    taraf, bkz. max_safe_server_memory_mb, bu durumda bir üst sınır
    koymaz — tahmin yürütüp yanlış bir sınır dayatmaktansa sınırsız
    bırakmak daha güvenli)."""
    if sys.platform == "win32":
        return _windows_total_memory_mb()
    if sys.platform == "darwin":
        return _macos_total_memory_mb()
    return _linux_total_memory_mb()


def max_safe_server_memory_mb(
    total_memory_mb: int | None, *, reserve_mb: int = SYSTEM_MEMORY_RESERVE_MB, minimum_mb: int = 512
) -> int | None:
    """Sunucuya ayrılabilecek GÜVENLİ üst sınır: toplam RAM - reserve_mb
    (kullanıcının sistemi için ayrılan pay). total_memory_mb bilinmiyorsa
    None döner (sınır konmaz). Çok düşük RAM'li sistemlerde bile en az
    minimum_mb döner — 0 ya da negatif bir sınır dayatmamak için."""
    if total_memory_mb is None:
        return None
    return max(minimum_mb, total_memory_mb - reserve_mb)


CONSOLE_BUFFER_LINES = 2000
"""ServerProcess'in kendi içinde tuttuğu son satır sayısı — GUI sayfası
değişip geri dönüldüğünde konsolu yeniden çizebilmek için (proje
kuralı: ekranda görünmeyen bir widget'a bağlı kalıp state kaybetmemek)."""


class ServerRuntimeError(Exception):
    """Sunucu hazırlama/kurulum/başlatma sırasında kullanıcıya gösterilecek
    anlaşılır mesajla fırlatılır."""


# -- hazırlama ----------------------------------------------------------------


async def prepare_server(
    pack: Pack,
    *,
    server_root: Path,
    cache_dir: Path,
    content_root: Path,
    client: httpx.AsyncClient,
    progress_cb: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> None:
    """server_root'u pack'in GÜNCEL haline göre hazırlar/günceller:
    server-compatible modlar + gerçek sunucu dosyası (server.jar ya da
    Forge/NeoForge installer'ı, bkz. server_jar.py) + (seçiliyse) dünya.

    export/server.py'deki filter_server_mods/ensure_server_file_downloaded
    ile BİREBİR aynı mantığı kullanır — zip'e gömülen ile burada çalıştırılan
    sunucu dosyası aynı kod yolundan geçer, aralarında sürüklenme olmaz."""
    server_root.mkdir(parents=True, exist_ok=True)
    mods_dir = server_root / "mods"
    mods_dir.mkdir(exist_ok=True)

    server_mods = filter_server_mods(pack)
    mod_files = await ensure_mods_downloaded(
        server_mods, cache_dir, client, progress_cb=progress_cb, cancel_event=cancel_event
    )
    current_names = set()
    for path in mod_files.values():
        dest = mods_dir / path.name
        shutil.copyfile(path, dest)
        current_names.add(path.name)
    for existing in mods_dir.glob("*.jar"):
        if existing.name not in current_names:
            existing.unlink()

    try:
        server_download = await get_server_download(client, pack.loader, pack.minecraft, pack.loader_version)
        downloaded = await ensure_server_file_downloaded(
            server_download, cache_dir, client, cancel_event=cancel_event
        )
        shutil.copyfile(downloaded, server_root / server_download.file_name)
    except DownloadCancelledError:
        raise
    except (ServerDownloadError, httpx.HTTPError) as exc:
        raise ServerRuntimeError(
            t(
                "runtime.error.server_file_download_failed",
                exc=exc,
                minecraft=pack.minecraft,
                loader=pack.loader.value,
                loader_version=pack.loader_version,
            )
        ) from exc

    if pack.server.selected_world:
        world_dest = server_root / "world"
        if world_dest.exists():
            shutil.rmtree(world_dest)
        for real_path, rel in collect_world_files(
            pack, content_root, selected_world=pack.server.selected_world
        ):
            dest = server_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(real_path, dest)


# -- durum / kurulum -----------------------------------------------------------

ServerState = Literal["not_prepared", "needs_install", "ready"]

_RUN_SCRIPT_NAMES = ("run.sh", "run.bat")


def server_state(server_root: Path) -> ServerState:
    """server_root'un mevcut haline bakarak ne yapılması gerektiğini söyler:
    hiç hazırlanmamış, (Forge/NeoForge) kurulum bekliyor, ya da çalıştırmaya
    hazır."""
    if not server_root.exists():
        return "not_prepared"
    if any((server_root / name).exists() for name in _RUN_SCRIPT_NAMES):
        return "ready"
    if list(server_root.glob("server.jar")):
        return "ready"
    if list(server_root.glob("*-installer.jar")):
        return "needs_install"
    return "not_prepared"


def find_installer_jar(server_root: Path) -> Path | None:
    matches = list(server_root.glob("*-installer.jar"))
    return matches[0] if matches else None


async def run_installer(installer_path: Path, server_root: Path, java_path: str) -> list[str]:
    """`java -jar <installer> --installServer` çalıştırır — Forge/NeoForge
    resmi olarak sadece bir kurulum programı yayınlıyor, hazır bir
    server.jar yok (bkz. server_jar.py). GUI'de canlı akıtmak yerine (bu,
    launcher.py:launch() gibi ince bir OS süreç sarmalayıcısı — proje
    genelinde bu tür sarmalayıcılar birim testi yerine gerçek uçtan uca
    doğrulamayla kontrol edilir) tüm çıktı toplanıp döner; sıfır olmayan
    çıkış kodunda son satırlarla birlikte ServerRuntimeError fırlatır."""
    lines: list[str] = []
    process = await _run_subprocess_streaming(
        [java_path, "-jar", str(installer_path), "--installServer"],
        cwd=server_root,
        on_output=lines.append,
    )
    if process.returncode != 0:
        tail = "\n".join(lines[-20:])
        raise ServerRuntimeError(
            t("runtime.error.install_failed", returncode=process.returncode, tail=tail)
        )
    return lines


async def _run_subprocess_streaming(
    cmd: list[str], *, cwd: Path, on_output: Callable[[str], None] | None
) -> subprocess.CompletedProcess:
    import asyncio

    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=str(cwd), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
    )
    assert proc.stdout is not None
    async for raw_line in proc.stdout:
        if on_output is not None:
            on_output(raw_line.decode(errors="replace").rstrip())
    returncode = await proc.wait()
    return subprocess.CompletedProcess(cmd, returncode)


# -- java tespiti ---------------------------------------------------------------


def find_java(settings_java_path: str = "") -> str | None:
    """Ayarlarda elle girilmiş bir yol varsa onu, yoksa PATH'teki `java`'yı
    kullanır (SKLauncher'ın portable yol deseniyle birebir aynı — bkz.
    config.py Settings.sklauncher_path)."""
    if settings_java_path.strip():
        path = Path(settings_java_path.strip())
        return str(path) if path.exists() else None
    found = shutil.which("java")
    return found


async def get_java_major_version(java_path: str) -> int | None:
    """`java -version` çıktısını (Java bunu stderr'e yazar — klasik bir
    tuhaflık) parse edip ana sürüm numarasını döner. Parse edilemezse
    None (sert bir engel değil, sadece bilgilendirici uyarı için kullanılır,
    bkz. required_java_major)."""
    import asyncio

    try:
        proc = await asyncio.create_subprocess_exec(
            java_path, "-version", stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.STDOUT
        )
        stdout, _ = await proc.communicate()
    except OSError:
        return None
    text = stdout.decode(errors="replace")
    match = re.search(r'version "(\d+)(?:\.(\d+))?', text)
    if not match:
        return None
    major = int(match.group(1))
    # Eski Java sürüm şeması: "1.8.0_xxx" -> major aslında 8.
    if major == 1 and match.group(2):
        return int(match.group(2))
    return major


def required_java_major(minecraft_version: str) -> int:
    """Kaba ama kullanışlı bir sezgisel (resmi Mojang gereksinimlerine göre)
    — SADECE bilgilendirici bir uyarı için, sert bir engel değil (bkz.
    gui/server_section.py)."""
    parts = minecraft_version.split(".")
    try:
        major, minor = int(parts[0]), int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
    except ValueError:
        return 17  # ayrıştırılamayan (snapshot vb.) versiyonlar için makul varsayılan

    if (major, minor, patch) >= (1, 20, 5):
        return 21
    if (major, minor) >= (1, 18):
        return 17
    if (major, minor) >= (1, 17):
        return 16
    return 8


# -- başlatma komutu ------------------------------------------------------------

AIKARS_FLAGS: list[str] = [
    "-XX:+UseG1GC",
    "-XX:+ParallelRefProcEnabled",
    "-XX:MaxGCPauseMillis=200",
    "-XX:+UnlockExperimentalVMOptions",
    "-XX:+DisableExplicitGC",
    "-XX:+AlwaysPreTouch",
    "-XX:G1NewSizePercent=30",
    "-XX:G1MaxNewSizePercent=40",
    "-XX:G1HeapRegionSize=8M",
    "-XX:G1ReservePercent=20",
    "-XX:G1HeapWastePercent=5",
    "-XX:G1MixedGCCountTarget=4",
    "-XX:InitiatingHeapOccupancyPercent=15",
    "-XX:G1MixedGCLiveThresholdPercent=90",
    "-XX:G1RSetUpdatingPauseTimePercent=5",
    "-XX:SurvivorRatio=32",
    "-XX:+PerfDisableSharedMem",
    "-XX:MaxTenuringThreshold=1",
]
"""Topluluğun yıllardır bilinen/belgelediği "Aikar's flags" G1GC bayak seti
(bu proje için icat edilmedi — Minecraft sunucusu barındıran topluluklarda
yaygın standart). Tek etkisi Minecraft sunucusunun GC duraklamalarını
azaltmak; mcpack'in kendisiyle ilgisi yok."""


def build_launch_command(server_root: Path, memory_mb: int, *, optimized: bool = False) -> list[str]:
    """server_root'ta ne varsa (hazır server.jar mı, kurulum sonrası oluşan
    run.sh/run.bat mı) ona göre doğru başlatma komutunu kurar. Saf fonksiyon
    — dosya sistemine sadece "var mı" diye bakar, gerçek java/süreç
    başlatmaz (testte gerçek Java olmadan test edilebilir).

    optimized=True ise (run.sh/run.bat DEĞİL, doğrudan server.jar
    durumunda) AIKARS_FLAGS eklenir — run.sh/run.bat kendi JVM argümanlarını
    zaten belirlediği için oraya karışılmaz."""
    xms = max(512, memory_mb // 2)

    if sys.platform == "win32" and (server_root / "run.bat").exists():
        return [str(server_root / "run.bat"), "nogui"]
    if (server_root / "run.sh").exists():
        return ["bash", str(server_root / "run.sh"), "nogui"]
    if (server_root / "server.jar").exists():
        flags = [f"-Xmx{memory_mb}M", f"-Xms{xms}M"]
        if optimized:
            flags += AIKARS_FLAGS
        return ["java", *flags, "-jar", "server.jar", "nogui"]

    raise ServerRuntimeError(t("runtime.error.not_runnable"))


# -- oyuncu listesi / envanter / aksiyon komutları -----------------------------
#
# Hepsi SAF fonksiyonlar (komut string'i üretir ya da konsol satırını parse
# eder) — hiçbiri ağ/süreç çalıştırmaz, tamamı birim testli. Gerçek
# gönderim/yanıt bekleme ServerProcess.send_command/send_command_and_wait
# ile olur (bkz. aşağı). Hepsi tamamen vanilla komutlardır, RCON/eklenti/
# mod GEREKMEZ.


class InventoryItem:
    def __init__(self, slot: int, item_id: str, count: int) -> None:
        self.slot = slot
        self.item_id = item_id
        self.count = count

    def __repr__(self) -> str:  # test okunabilirliği için
        return f"InventoryItem(slot={self.slot}, item_id={self.item_id!r}, count={self.count})"

    def __eq__(self, other: object) -> bool:
        return (
            isinstance(other, InventoryItem)
            and (self.slot, self.item_id, self.count) == (other.slot, other.item_id, other.count)
        )


_LIST_RE = re.compile(r"There are \d+ of a max of \d+ players online:\s*(.*)$")
_ENTITY_DATA_RE = re.compile(r"has the following entity data:\s*(\[.*\])\s*$")
_ITEM_RE = re.compile(r'Slot:\s*(-?\d+)b,\s*id:\s*"([^"]+)",\s*Count:\s*(\d+)b')

def _armor_offhand_labels() -> dict[int, str]:
    # t() burada FONKSİYON İÇİNDE çağrılır (modül seviyesinde sabit DEĞİL) —
    # aksi halde bu sözlük import anında, set_language() çağrılmadan ÖNCE
    # donardı (bkz. i18n.py modül docstring'i).
    return {
        100: t("inventory.slot.boots"),
        101: t("inventory.slot.leggings"),
        102: t("inventory.slot.chestplate"),
        103: t("inventory.slot.helmet"),
        -106: t("inventory.slot.offhand"),
    }


def list_players_command() -> str:
    return "list"


def parse_list_response(line: str) -> list[str] | None:
    """"There are 2 of a max of 20 players online: Steve, Alex" -> ["Steve",
    "Alex"]. Bu satırın bir /list YANITI olup olmadığını da bu şekilde
    anlıyoruz (None = bu satır /list yanıtı değil)."""
    match = _LIST_RE.search(line)
    if not match:
        return None
    names = match.group(1).strip()
    return [n.strip() for n in names.split(",")] if names else []


def inventory_query_command(player: str) -> str:
    return f"data get entity {player} Inventory"


def ender_chest_query_command(player: str) -> str:
    return f"data get entity {player} EnderItems"


def parse_item_list_response(line: str) -> list[InventoryItem] | None:
    """"<ad> has the following entity data: [{Slot: 0b, id: "minecraft:...",
    Count: 1b}, ...]" satırını InventoryItem listesine çevirir. Hem
    Inventory hem EnderItems sorgu yanıtları aynı sarmalayıcı metni kullanır
    — ikisi için de bu fonksiyon yeterli (kategorizasyon ayrı, bkz.
    categorize_inventory_slot — SADECE Inventory bağlamında anlamlı).

    Bilinçli sınır: iç içe `tag:` bileşik etiketlerini (büyü, isim vb.)
    AYRIŞTIRMAZ, sadece Slot/id/Count — tam bir NBT/SNBT parser değil."""
    match = _ENTITY_DATA_RE.search(line)
    if not match:
        return None
    body = match.group(1)
    return [InventoryItem(slot=int(s), item_id=item_id, count=int(c)) for s, item_id, c in _ITEM_RE.findall(body)]


def categorize_inventory_slot(slot: int) -> str:
    """SADECE Inventory sorgusu (EnderItems değil) için — ana envanter/sıcak
    çubuk/zırh/ikinci el ayrımı. Vanilla'nın sabit Slot numaralandırmasına
    dayanır (proje icadı değil)."""
    labels = _armor_offhand_labels()
    if slot in labels:
        return labels[slot]
    if 0 <= slot <= 8:
        return t("inventory.slot.hotbar")
    if 9 <= slot <= 35:
        return t("inventory.slot.main")
    return f"Slot {slot}"


def _version_tuple(minecraft_version: str) -> tuple[int, int, int]:
    parts = minecraft_version.split(".")
    try:
        major = int(parts[0])
        minor = int(parts[1]) if len(parts) > 1 else 0
        patch = int(parts[2]) if len(parts) > 2 else 0
        return (major, minor, patch)
    except ValueError:
        return (1, 999, 0)  # ayrıştırılamayan (snapshot vb.) versiyon -> /damage'ı dene


def heal_command(player: str) -> str:
    """Tam (pratikte): instant_health amplifier 10, herhangi bir makul
    max-can değerinin çok üzerinde iyileştirir — vanilla'da doğrudan
    "/heal" komutu YOK, bu yaygın bilinen eşdeğeri."""
    return f"effect give {player} minecraft:instant_health 1 10 true"


def kill_command(player: str) -> str:
    return f"kill {player}"


def damage_command(player: str, amount: int, minecraft_version: str) -> str:
    """MC 1.19.4+'ta /damage ile TAM, HASSAS hasar. Öncesinde vanilla'da
    hassas bir "X kadar hasar ver" komutu yok — instant_damage efektiyle
    SADECE YAKLAŞIK (hasar 2'nin katları şeklinde arttığı için amount'a
    doğrusal eşlenemez, en yakın amplifier'a yuvarlanır)."""
    if _version_tuple(minecraft_version) >= (1, 19, 4):
        return f"damage {player} {amount}"
    amplifier = max(0, min(9, (max(amount, 1) - 1).bit_length() - 1))
    return f"effect give {player} minecraft:instant_damage 1 {amplifier} true"


def feed_command(player: str) -> str:
    """Pratikte tam: saturation efekti aktifken her tick food/saturation'ı
    doldurur — vanilla'da yaygın bilinen "anında doyur" numarası."""
    return f"effect give {player} minecraft:saturation 1 255 true"


def hunger_command(player: str, duration_s: int) -> str:
    """YAKLAŞIK: vanilla'da açlığı "anında" belirli bir değere düşüren bir
    komut YOK — bu efekt sadece süre boyunca normalden daha hızlı
    acıktırır. GUI bunu kullanıcıya açıkça belirtmeli (yanıltmamak için)."""
    return f"effect give {player} minecraft:hunger {duration_s} 5 true"


# -- canlı süreç ------------------------------------------------------------


class _Waiter:
    def __init__(self, pattern: re.Pattern[str]) -> None:
        self.pattern = pattern
        self.event = threading.Event()
        self.result: str | None = None


class ServerProcess(QObject):
    """Çalışan bir sunucu subprocess'ini sarmalar: stdin'e komut yazma,
    stdout'u satır satır okuyup Qt sinyaliyle GUI thread'ine taşıma, ve
    GERÇEK Minecraft "stop" komutuyla düzgün kapatma (kill DEĞİL)."""

    output_line = Signal(str)
    process_exited = Signal(int)

    def __init__(self) -> None:
        super().__init__()
        self._process: subprocess.Popen | None = None
        self._reader_thread: threading.Thread | None = None
        self.buffer: deque[str] = deque(maxlen=CONSOLE_BUFFER_LINES)
        self._waiters_lock = threading.Lock()
        self._waiters: list[_Waiter] = []
        self._listeners_lock = threading.Lock()
        self._listeners: list[Callable[[str | None], None]] = []
        """Qt Signal'den BAĞIMSIZ, düz Python callback'ler — web paneli
        (bkz. webpanel/app.py) Qt event loop'una ihtiyaç duymadan canlı
        satır akışına böyle abone olur. output_line Signal'i ile AYNI
        anda, _read_output içinden çağrılır (bkz. aşağı)."""

    @property
    def is_running(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def start(self, cmd: list[str], *, cwd: Path) -> None:
        if self.is_running:
            raise ServerRuntimeError(t("runtime.error.already_running"))
        self._process = subprocess.Popen(
            cmd,
            cwd=str(cwd),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()

    def _read_output(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            line = line.rstrip("\n")
            self.buffer.append(line)
            self.output_line.emit(line)
            self._notify_waiters(line)
            self._notify_listeners(line)
        returncode = process.wait()
        self.process_exited.emit(returncode)
        self._notify_listeners(None)  # akışın bittiğini düz-Python dinleyicilere bildir

    def _notify_waiters(self, line: str) -> None:
        with self._waiters_lock:
            matched = [w for w in self._waiters if w.pattern.search(line)]
            for w in matched:
                self._waiters.remove(w)
        for w in matched:
            w.result = line
            w.event.set()

    def _notify_listeners(self, line: str | None) -> None:
        with self._listeners_lock:
            listeners = list(self._listeners)
        for callback in listeners:
            try:
                callback(line)
            except Exception:  # noqa: BLE001 - bir dinleyicinin hatası okuyucu thread'i düşürmesin
                pass

    def add_listener(self, callback: Callable[[str | None], None]) -> None:
        with self._listeners_lock:
            self._listeners.append(callback)

    def remove_listener(self, callback: Callable[[str | None], None]) -> None:
        with self._listeners_lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def send_command(self, text: str) -> None:
        if not self.is_running or self._process is None or self._process.stdin is None:
            raise ServerRuntimeError(t("runtime.error.not_running_cant_send"))
        self._process.stdin.write(text + "\n")
        self._process.stdin.flush()

    def send_command_and_wait(self, text: str, *, match: re.Pattern[str], timeout: float = 5.0) -> str | None:
        """Komutu gönderir ve arkaplan okuyucu thread'inin `match`'e uyan
        bir sonraki satırı bulmasını bekler — `/list`/`/data get entity`
        gibi "komut gönder, YANITI oku" akışları için (düz send_command
        tek yönlü, yanıt beklemiyordu). GUI thread'inde ÇAĞRILMAMALI
        (bloklar) — bkz. gui/main_window.py'nin bunu run_async ile
        sarmalaması."""
        waiter = _Waiter(match)
        with self._waiters_lock:
            self._waiters.append(waiter)
        try:
            self.send_command(text)
        except ServerRuntimeError:
            with self._waiters_lock:
                if waiter in self._waiters:
                    self._waiters.remove(waiter)
            raise
        if waiter.event.wait(timeout):
            return waiter.result
        with self._waiters_lock:
            if waiter in self._waiters:
                self._waiters.remove(waiter)
        return None

    def stop(self, timeout: float = 30.0) -> None:
        """GERÇEK Minecraft "stop" komutunu gönderir (temiz kapanış: dünya
        kaydedilir) — asla kill/terminate ile BAŞLAMAZ. Yalnızca süre
        dolarsa son çare olarak terminate() çağrılır."""
        if not self.is_running or self._process is None:
            return
        try:
            self.send_command("stop")
        except ServerRuntimeError:
            pass
        assert self._process is not None
        try:
            self._process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            self._process.terminate()


class ServerProcessRegistry:
    """pack.id -> ServerProcess eşlemesini thread-safe tutar — hem Qt
    (gui/main_window.py) hem web paneli (webpanel/app.py, ayrı bir
    thread'de uvicorn üzerinde çalışır) AYNI nesneyi paylaşır, böylece
    biri sunucuyu başlatınca diğeri de "çalışıyor" görür (tek kaynak,
    aynı process içinde — IPC gerekmez, bkz. main.py)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._processes: dict[str, ServerProcess] = {}

    def get(self, pack_id: str) -> ServerProcess | None:
        with self._lock:
            return self._processes.get(pack_id)

    def set(self, pack_id: str, process: ServerProcess) -> None:
        with self._lock:
            self._processes[pack_id] = process

    def pop(self, pack_id: str) -> ServerProcess | None:
        with self._lock:
            return self._processes.pop(pack_id, None)

    def is_running(self, pack_id: str) -> bool:
        process = self.get(pack_id)
        return process is not None and process.is_running

    def all_running_ids(self) -> list[str]:
        with self._lock:
            items = list(self._processes.items())
        return [pid for pid, p in items if p.is_running]
