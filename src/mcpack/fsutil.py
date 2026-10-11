"""Dosya sistemi yardımcıları.

`atomic_write_text`: önce aynı dizinde geçici bir dosyaya yazar, diske
zorlar (fsync) ve `os.replace` ile hedefin yerine koyar. `os.replace` aynı
dosya sistemi içinde atomiktir — yazma ortasında çökme, elektrik kesintisi
ya da disk dolması hedef dosyayı yarım/boş bırakamaz; ya eski içerik ya da
yeni içerik kalır. Önceden pack JSON'ları ve settings.json doğrudan
`write_text` ile yazılıyordu: yarıda kesilen bir yazma pack'i okunamaz
hale getiriyordu (list_packs onu sessizce atlıyordu, kullanıcı pack'ini
"kaybolmuş" görüyordu).
"""

from __future__ import annotations

import contextlib
import os
import tempfile
from pathlib import Path


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8", mode: int | None = None) -> None:
    """mode verilirse (ör. 0o600) dosya bu izinle oluşturulur — gizli bilgi
    içerebilen dosyalar için."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Geçici ad ".json" ile BİTMEZ — list_pack_files'ın *.json taraması
    # yarım kalmış bir geçici dosyayı pack sanmasın.
    fd, tmp_name = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding=encoding, newline="") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        if mode is not None:
            with contextlib.suppress(OSError):
                os.chmod(tmp, mode)
        elif path.exists():
            with contextlib.suppress(OSError):
                os.chmod(tmp, path.stat().st_mode & 0o7777)
        os.replace(tmp, path)
    except BaseException:
        tmp.unlink(missing_ok=True)
        raise
    _fsync_dir(path.parent)


def _fsync_dir(directory: Path) -> None:
    """rename'in kendisinin de kalıcı olması için dizini fsync'ler (POSIX;
    Windows'ta dizin açılamaz, sessizce atlanır)."""
    if os.name == "nt":
        return
    with contextlib.suppress(OSError):
        fd = os.open(directory, os.O_RDONLY)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
