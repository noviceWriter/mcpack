import re
import zipfile

import pytest

from mcpack.backups import BackupError, create_backup, list_backups, prune, restore_backup, world_dirs


def _world(root, name="world", data=b"lvl"):
    w = root / name
    (w / "region").mkdir(parents=True)
    (w / "level.dat").write_bytes(data)
    (w / "region" / "r.0.0.mca").write_bytes(b"chunk")
    (w / "session.lock").write_bytes(b"lock")
    return w


def test_backup_includes_dimensions_and_skips_lock(tmp_path):
    root = tmp_path / "srv"
    _world(root)
    _world(root, "world_nether")
    info = create_backup(root, tmp_path / "b", label="manual test")
    names = set(zipfile.ZipFile(info.path).namelist())
    assert "world/level.dat" in names and "world_nether/region/r.0.0.mca" in names
    assert not any(n.endswith("session.lock") for n in names)
    assert info.label == "manual-test"
    assert list_backups(tmp_path / "b")[0].path == info.path


def test_level_name_from_properties(tmp_path):
    root = tmp_path / "srv"
    _world(root, "survival")
    (root / "server.properties").write_text("level-name=survival\n", encoding="utf-8")
    assert [p.name for p in world_dirs(root)] == ["survival"]


def test_no_world_raises(tmp_path):
    (tmp_path / "srv").mkdir()
    with pytest.raises(BackupError):
        create_backup(tmp_path / "srv", tmp_path / "b")


def test_running_server_save_off_flush_on(tmp_path):
    root = tmp_path / "srv"
    _world(root)
    sent = []

    class FakeProcess:
        is_running = True

        def send_command(self, text):
            sent.append(text)

        def send_command_and_wait(self, text, *, match, timeout):
            sent.append(text)
            assert match.search("[Server thread/INFO]: Saved the game")
            return "Saved the game"

    create_backup(root, tmp_path / "b", process=FakeProcess())
    assert sent == ["save-off", "save-all flush", "save-on"]


def test_save_on_sent_even_if_zip_fails(tmp_path):
    sent = []

    class FakeProcess:
        is_running = True

        def send_command(self, text):
            sent.append(text)

        def send_command_and_wait(self, text, *, match, timeout):
            sent.append(text)
            return "Saved the game"

    (tmp_path / "srv").mkdir()
    with pytest.raises(BackupError):
        create_backup(tmp_path / "srv", tmp_path / "b", process=FakeProcess())
    assert sent[-1] == "save-on"


def test_prune_keeps_newest(tmp_path):
    d = tmp_path / "b"
    d.mkdir()
    for i in range(5):
        (d / f"backup-2026010{i + 1}-120000.zip").write_bytes(b"x")
    removed = prune(d, 2)
    assert len(removed) == 3
    assert [b.name for b in list_backups(d)] == ["backup-20260105-120000.zip", "backup-20260104-120000.zip"]
    assert prune(d, 0) == []


def test_restore_moves_current_world_aside(tmp_path):
    root = tmp_path / "srv"
    _world(root, data=b"old")
    info = create_backup(root, tmp_path / "b")
    (root / "world" / "level.dat").write_bytes(b"newer-but-broken")
    moved = restore_backup(info.path, root)
    assert (root / "world" / "level.dat").read_bytes() == b"old"
    assert len(moved) == 1 and re.match(r"world\.before-restore-\d{8}-\d{6}", moved[0].name)
    assert (moved[0] / "level.dat").read_bytes() == b"newer-but-broken"


def test_restore_rejects_traversal(tmp_path):
    root = tmp_path / "srv"
    root.mkdir()
    evil = tmp_path / "evil.zip"
    with zipfile.ZipFile(evil, "w") as zf:
        zf.writestr("world/level.dat", "ok")
        zf.writestr("../../escape.txt", "no")
    restore_backup(evil, root)
    assert (root / "world" / "level.dat").exists()
    assert not (tmp_path / "escape.txt").exists()


