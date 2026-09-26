"""SKLauncher entegrasyonu (proje-amacı.md §2.5).

SKLauncher, MultiMC tabanlı bir launcher olduğu için instance formatı
export/prism.py ile ürettiğimiz Prism/MultiMC yapısıyla birebir aynıdır —
burada sadece o yapıyı ZİP'lemek yerine doğrudan SKLauncher'ın instances/
klasörüne yazıyoruz.

NOT: SKLauncher'ı belirli bir instance ile otomatik açacak resmi/belgelenmiş
bir CLI parametresi yok (3.x ve 4.x arasında da değişebilir). Bu yüzden
"çalıştır" akışı: (1) instance klasörünü hazırla/güncelle, (2) launcher'ı
başlat — kullanıcı instance'ı launcher içinden seçer. Bu, versiyon
farklılıklarına karşı en güvenli yaklaşımdır.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import httpx

from mcpack.export.base import (
    EXCLUDED_OVERRIDE_DIR_NAMES,
    collect_content_download_files,
    collect_override_files,
    collect_world_files,
    ensure_mods_downloaded,
)
from mcpack.export.prism import build_instance_cfg, build_mmc_pack
from mcpack.models import Pack


class SKLauncherError(Exception):
    pass


def instances_dir_for(sklauncher_path: str) -> Path:
    """Portable SKLauncher yürütülebilir dosyasının yanındaki instances/ klasörü.

    Portable modda MultiMC-tabanlı launcher'lar veriyi genelde exe ile aynı
    dizinde tutar; bu bizim en iyi varsayımımız.
    """
    exe = Path(sklauncher_path)
    if not exe.exists():
        raise SKLauncherError(f"SKLauncher yolu bulunamadı: {sklauncher_path}")
    return exe.parent / "instances"


def instance_dir_name(pack: Pack) -> str:
    return pack.name.strip().replace("/", "-") or pack.id


async def prepare_instance(
    pack: Pack,
    *,
    source_dir: Path,
    instances_dir: Path,
    cache_dir: Path,
    content_root: Path,
    client: httpx.AsyncClient,
    exclude_dirs: set[str] | None = None,
    progress_cb=None,
    cancel_event=None,
) -> Path:
    """Pack için bir SKLauncher instance klasörü oluşturur/günceller, yolunu döner."""
    instance_dir = instances_dir / instance_dir_name(pack)
    minecraft_dir = instance_dir / ".minecraft"
    mods_dir = minecraft_dir / "mods"
    mods_dir.mkdir(parents=True, exist_ok=True)

    (instance_dir / "instance.cfg").write_text(build_instance_cfg(pack), encoding="utf-8")
    (instance_dir / "mmc-pack.json").write_text(
        json.dumps(build_mmc_pack(pack), indent=2), encoding="utf-8"
    )

    # Instance'ta artık pack'te olmayan eski mod jar'larını temizle.
    current_names = set()
    mod_files = await ensure_mods_downloaded(
        pack.mods, cache_dir, client, progress_cb=progress_cb, cancel_event=cancel_event
    )
    for path in mod_files.values():
        dest = mods_dir / path.name
        shutil.copyfile(path, dest)
        current_names.add(path.name)
    for existing in mods_dir.glob("*.jar"):
        if existing.name not in current_names:
            existing.unlink()

    content_files = collect_override_files(
        source_dir,
        pack.overrides.include,
        exclude_dirs=exclude_dirs if exclude_dirs is not None else EXCLUDED_OVERRIDE_DIR_NAMES,
    )
    content_files += collect_world_files(pack, content_root)
    downloaded_content = await ensure_mods_downloaded(
        pack.content_downloads, cache_dir, client, cancel_event=cancel_event
    )
    content_files += collect_content_download_files(pack.content_downloads, downloaded_content)
    for real_path, rel in content_files:
        dest = minecraft_dir / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(real_path, dest)

    return instance_dir


def launch(sklauncher_path: str) -> subprocess.Popen:
    """Portable SKLauncher'ı başlatır (Windows .exe, Linux AppImage/.jar)."""
    exe = Path(sklauncher_path)
    if not exe.exists():
        raise SKLauncherError(f"SKLauncher yolu bulunamadı: {sklauncher_path}")

    if exe.suffix.lower() == ".jar":
        return subprocess.Popen(["java", "-jar", str(exe)], cwd=str(exe.parent))
    if sys.platform != "win32" and exe.suffix == "":
        # Linux AppImage genelde çalıştırılabilir bit ister.
        exe.chmod(exe.stat().st_mode | 0o111)
    return subprocess.Popen([str(exe)], cwd=str(exe.parent))
