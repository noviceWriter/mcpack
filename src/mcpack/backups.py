"""Yerel sunucu dünyası yedekleri.

- Yedekler `<packs_dir>/backups/<pack_id>/backup-<zaman>[-etiket].zip`.
- Sunucu ÇALIŞIRKEN alınan yedekte tutarlılık için önce `save-off` +
  `save-all flush` gönderilir, "Saved the game" yanıtı beklenir, kopya
  alınır, sonra `save-on` — Minecraft dünyayı yazarken kopyalanan bir
  klasör bozuk chunk'larla sonuçlanabilir.
- Hangi klasörlerin dünya olduğu server.properties'teki `level-name`'den
  (varsayılan "world") okunur; Bukkit tarzı `<ad>_nether`/`<ad>_the_end`
  da dahil edilir. `session.lock` (Windows'ta kilitli olabilir) atlanır.
- Geri yükleme sadece sunucu dururken yapılır ve mevcut dünyayı SİLMEZ:
  önce `<ad>.before-restore-<zaman>` olarak kenara taşır.
"""

from __future__ import annotations

import re
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path, PurePosixPath

from mcpack.logging_setup import get_logger
from mcpack.packs.storage import PathTraversalError, safe_join
from mcpack.server_properties import read_properties

log = get_logger(__name__)

BACKUP_PREFIX = "backup-"
_SKIP_FILES = {"session.lock"}
_SAVED_RE = re.compile(r"Saved the (game|world)|Saved the worlds", re.IGNORECASE)
SAVE_TIMEOUT_S = 60


class BackupError(Exception):
    pass


@dataclass(frozen=True)
class BackupInfo:
    path: Path
    created: datetime
    size: int
    label: str

    @property
    def name(self) -> str:
        return self.path.name


def backups_dir(packs_dir: Path, pack_id: str) -> Path:
    return packs_dir / "backups" / pack_id


def world_dirs(server_root: Path) -> list[Path]:
    level = read_properties(server_root / "server.properties").get("level-name") or "world"
    level = Path(level).name or "world"  # yol bileşenlerine izin verme
    candidates = [level, f"{level}_nether", f"{level}_the_end"]
    return [server_root / c for c in candidates if (server_root / c).is_dir()]


def has_world(server_root: Path) -> bool:
    return bool(world_dirs(server_root))


def list_backups(directory: Path) -> list[BackupInfo]:
    if not directory.exists():
        return []
    items = []
    for path in directory.glob(f"{BACKUP_PREFIX}*.zip"):
        stem = path.stem[len(BACKUP_PREFIX):]
        stamp, _, label = stem.partition("_")
        try:
            created = datetime.strptime(stamp, "%Y%m%d-%H%M%S")
        except ValueError:
            created = datetime.fromtimestamp(path.stat().st_mtime)
        items.append(BackupInfo(path=path, created=created, size=path.stat().st_size, label=label))
    return sorted(items, key=lambda b: b.created, reverse=True)


def _safe_label(label: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "-", label).strip("-")[:40]


def _zip_worlds(server_root: Path, dest: Path) -> int:
    dirs = world_dirs(server_root)
    if not dirs:
        raise BackupError("Yedeklenecek dünya yok (sunucu henüz hiç çalıştırılmamış olabilir).")
    tmp = dest.with_suffix(".zip.part")
    count = 0
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for world in dirs:
            for path in world.rglob("*"):
                if path.is_file() and path.name not in _SKIP_FILES:
                    zf.write(path, path.relative_to(server_root).as_posix())
                    count += 1
    tmp.replace(dest)
    return count


def create_backup(server_root: Path, directory: Path, *, label: str = "", process=None) -> BackupInfo:
    """Dünya(lar)ı zip'ler. process (çalışan ServerProcess) verilirse kayıt
    geçici olarak durdurulup diske boşaltılır. Bloklar — GUI thread'inde
    çağrılmamalı."""
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    name = f"{BACKUP_PREFIX}{stamp}" + (f"_{_safe_label(label)}" if label else "") + ".zip"
    dest = directory / name
    paused = False
    try:
        if process is not None and process.is_running:
            process.send_command("save-off")
            paused = True
            line = process.send_command_and_wait("save-all flush", match=_SAVED_RE, timeout=SAVE_TIMEOUT_S)
            if line is None:
                log.warning("save-all flush yanıtı %ss içinde gelmedi; yine de yedekleniyor", SAVE_TIMEOUT_S)
        count = _zip_worlds(server_root, dest)
    finally:
        if paused:
            try:
                process.send_command("save-on")
            except Exception as exc:  # noqa: BLE001
                log.error("save-on gönderilemedi — sunucuda otomatik kayıt KAPALI kalmış olabilir: %s", exc)
    info = BackupInfo(path=dest, created=datetime.strptime(stamp, "%Y%m%d-%H%M%S"), size=dest.stat().st_size, label=_safe_label(label))
    log.info("Dünya yedeği alındı: %s (%d dosya, %.1f MB)", dest, count, info.size / 1024**2)
    return info


def prune(directory: Path, keep: int) -> list[Path]:
    """En yeni `keep` yedek dışındakileri siler (keep <= 0: hiçbirini silme).
    Etiketli yedekler (ör. "before-prepare", "manual") da sayılır."""
    if keep <= 0:
        return []
    removed = []
    for b in list_backups(directory)[keep:]:
        b.path.unlink(missing_ok=True)
        removed.append(b.path)
    if removed:
        log.info("%d eski yedek silindi (%s)", len(removed), directory)
    return removed


def restore_backup(backup: Path, server_root: Path) -> list[Path]:
    """Yedeği geri yükler. Mevcut dünya klasörleri silinmez, kenara taşınır;
    taşınan klasörlerin listesi döner. Çağıran taraf sunucunun DURDUĞUNDAN
    emin olmalı."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    with zipfile.ZipFile(backup) as zf:
        tops = {PurePosixPath(n).parts[0] for n in zf.namelist() if PurePosixPath(n).parts}
        # Sadece düz klasör adları ("world", "world_nether"); "..", "/" vb.
        # kenara taşıma adımında sunucu klasörünün KENDİSİNİ hedefleyebilirdi.
        tops = {t for t in tops if t not in {".", ".."} and t == Path(t).name and "\\" not in t and ":" not in t}
        moved = []
        for top in sorted(tops):
            current = server_root / top
            if current.exists():
                aside = server_root / f"{current.name}.before-restore-{stamp}"
                current.rename(aside)
                moved.append(aside)
        for info in zf.infolist():
            if info.is_dir():
                continue
            try:
                target = safe_join(server_root, *PurePosixPath(info.filename).parts)
            except PathTraversalError:
                log.warning("Yedekte güvensiz yol atlandı: %s", info.filename)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(info) as src, target.open("wb") as out:
                shutil.copyfileobj(src, out)
    log.info("Yedek geri yüklendi: %s -> %s (kenara alınan: %s)", backup.name, server_root, [m.name for m in moved])
    return moved
