import os

import pytest

from mcpack.fsutil import atomic_write_text
from mcpack.models import Loader, Pack
from mcpack.packs import storage


def test_writes_and_overwrites(tmp_path):
    target = tmp_path / "sub" / "a.json"
    atomic_write_text(target, "one")
    atomic_write_text(target, "two")
    assert target.read_text(encoding="utf-8") == "two"
    assert [p.name for p in target.parent.iterdir()] == ["a.json"]  # geçici dosya kalmadı


def test_failed_replace_keeps_original_and_cleans_tmp(tmp_path, monkeypatch):
    target = tmp_path / "pack.json"
    atomic_write_text(target, "original")

    def boom(*_a, **_k):
        raise OSError("disk dolu")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        atomic_write_text(target, "yarım kalacak")
    assert target.read_text(encoding="utf-8") == "original"
    assert [p.name for p in tmp_path.iterdir()] == ["pack.json"]


def test_leftover_tmp_is_not_listed_as_pack(tmp_path):
    pack = Pack(name="x", minecraft="1.21.1", loader=Loader.FABRIC)
    storage.save_pack(pack, tmp_path)
    (tmp_path / f".{pack.id}.json.abc123.tmp").write_text("{yarım", encoding="utf-8")
    assert storage.list_pack_files(tmp_path) == [tmp_path / f"{pack.id}.json"]
