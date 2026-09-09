"""Pack'lerin diskte JSON olarak saklanması.

proje-amacı.md §6: "Path traversal koruması (overrides içinde .. olmasın)"
kuralı burada `safe_join` ile merkezi olarak uygulanır; export katmanı da
overrides dosyalarını arşive eklerken bu fonksiyonu kullanır.
"""

from __future__ import annotations

from pathlib import Path

from mcpack.models import Pack


class PathTraversalError(Exception):
    pass


def safe_join(base: Path, *parts: str) -> Path:
    """base dizini dışına çıkan (örn. `..` içeren) yolları reddeder."""
    base = base.resolve()
    target = base.joinpath(*parts).resolve()
    if base not in target.parents and target != base:
        raise PathTraversalError(f"Güvensiz yol: {Path(*parts)}")
    return target


def pack_file_path(packs_dir: Path, pack_id: str) -> Path:
    return packs_dir / f"{pack_id}.json"


def list_pack_files(packs_dir: Path) -> list[Path]:
    if not packs_dir.exists():
        return []
    return sorted(packs_dir.glob("*.json"))


def load_pack(path: Path) -> Pack:
    return Pack.model_validate_json(path.read_text(encoding="utf-8"))


def save_pack(pack: Pack, packs_dir: Path) -> Path:
    packs_dir.mkdir(parents=True, exist_ok=True)
    path = pack_file_path(packs_dir, pack.id)
    path.write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    return path


def delete_pack(pack_id: str, packs_dir: Path) -> None:
    pack_file_path(packs_dir, pack_id).unlink(missing_ok=True)
