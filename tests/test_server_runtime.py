"""server_runtime.py testleri: saf fonksiyonlar (build_launch_command,
server_state, required_java_major) + gerçek Java/Minecraft'a ihtiyaç
duymadan ServerProcess'in stdin/stdout/stop akışı (trivial bir Python
script'i "sahte sunucu" olarak kullanılır) + prepare_server'ın gerçek ağ
yerine respx-mock'lu entegrasyonu."""

import re
import shutil
import sys
import time
from pathlib import Path

import httpx
import pytest
import respx
from PySide6.QtCore import QCoreApplication, Qt

from mcpack.models import Loader, Pack
from mcpack.server_jar import VERSION_MANIFEST_URL
from mcpack.server_runtime import (
    AIKARS_FLAGS,
    InventoryItem,
    ServerProcess,
    ServerRuntimeError,
    build_launch_command,
    categorize_inventory_slot,
    damage_command,
    ender_chest_query_command,
    feed_command,
    find_java,
    get_system_memory_mb,
    heal_command,
    hunger_command,
    inventory_query_command,
    kill_command,
    list_players_command,
    max_safe_server_memory_mb,
    parse_item_list_response,
    parse_list_response,
    prepare_server,
    required_java_major,
    server_state,
)

if QCoreApplication.instance() is None:
    QCoreApplication([])


# -- required_java_major -----------------------------------------------------


@pytest.mark.parametrize(
    "mc_version,expected",
    [
        ("1.21.1", 21),
        ("1.20.6", 21),
        ("1.20.4", 17),
        ("1.18.2", 17),
        ("1.17", 16),
        ("1.16.5", 8),
        ("1.7.10", 8),
    ],
)
def test_required_java_major(mc_version: str, expected: int):
    assert required_java_major(mc_version) == expected


# -- server_state -------------------------------------------------------------


def test_server_state_not_prepared_when_dir_missing(tmp_path: Path):
    assert server_state(tmp_path / "does-not-exist") == "not_prepared"


def test_server_state_needs_install_when_only_installer_present(tmp_path: Path):
    (tmp_path / "forge-1.20.1-47.4.10-installer.jar").write_bytes(b"fake")
    assert server_state(tmp_path) == "needs_install"


def test_server_state_ready_when_server_jar_present(tmp_path: Path):
    (tmp_path / "server.jar").write_bytes(b"fake")
    assert server_state(tmp_path) == "ready"


def test_server_state_ready_when_run_sh_present(tmp_path: Path):
    (tmp_path / "run.sh").write_text("#!/bin/sh\n")
    assert server_state(tmp_path) == "ready"


# -- build_launch_command ------------------------------------------------------


def test_build_launch_command_uses_server_jar(tmp_path: Path):
    (tmp_path / "server.jar").write_bytes(b"fake")
    cmd = build_launch_command(tmp_path, 2048)
    assert cmd == ["java", "-Xmx2048M", "-Xms1024M", "-jar", "server.jar", "nogui"]


def test_build_launch_command_prefers_run_sh_on_non_windows(tmp_path: Path):
    (tmp_path / "server.jar").write_bytes(b"fake")  # modern Forge sonrası ikisi de olabilir
    (tmp_path / "run.sh").write_text("#!/bin/sh\n")
    if sys.platform != "win32":
        cmd = build_launch_command(tmp_path, 2048)
        assert cmd == ["bash", str(tmp_path / "run.sh"), "nogui"]


def test_build_launch_command_raises_when_nothing_ready(tmp_path: Path):
    with pytest.raises(ServerRuntimeError):
        build_launch_command(tmp_path, 2048)


def test_build_launch_command_optimized_adds_aikars_flags(tmp_path: Path):
    (tmp_path / "server.jar").write_bytes(b"fake")
    cmd = build_launch_command(tmp_path, 4096, optimized=True)
    assert cmd[:3] == ["java", "-Xmx4096M", "-Xms2048M"]
    for flag in AIKARS_FLAGS:
        assert flag in cmd
    assert cmd[-3:] == ["-jar", "server.jar", "nogui"]


def test_build_launch_command_run_sh_ignores_optimized_flag(tmp_path: Path):
    """run.sh zaten kendi JVM argümanlarını belirliyor — optimized=True
    burada hiçbir şey eklemez, run.sh'in kendi haline karışmaz."""
    (tmp_path / "run.sh").write_text("#!/bin/sh\n")
    if sys.platform != "win32":
        cmd = build_launch_command(tmp_path, 2048, optimized=True)
        assert cmd == ["bash", str(tmp_path / "run.sh"), "nogui"]


# -- oyuncu listesi / envanter / aksiyon komutları -----------------------------


def test_parse_list_response_with_players():
    line = '[12:00:00] [Server thread/INFO]: There are 2 of a max of 20 players online: Steve, Alex'
    assert parse_list_response(line) == ["Steve", "Alex"]


def test_parse_list_response_empty():
    line = "There are 0 of a max of 20 players online:"
    assert parse_list_response(line) == []


def test_parse_list_response_returns_none_for_unrelated_line():
    assert parse_list_response("[Server thread/INFO]: Done (1.0s)! For help, type help") is None


def test_parse_item_list_response_extracts_slot_id_count():
    line = (
        'Steve has the following entity data: [{Slot: 0b, id: "minecraft:diamond_sword", Count: 1b}, '
        '{Slot: 100b, id: "minecraft:diamond_boots", Count: 1b, tag: {Damage: 0}}]'
    )
    items = parse_item_list_response(line)
    assert items == [
        InventoryItem(slot=0, item_id="minecraft:diamond_sword", count=1),
        InventoryItem(slot=100, item_id="minecraft:diamond_boots", count=1),
    ]


def test_parse_item_list_response_empty_inventory():
    assert parse_item_list_response("Steve has the following entity data: []") == []


def test_parse_item_list_response_returns_none_for_unrelated_line():
    assert parse_item_list_response("[Server thread/INFO]: Done!") is None


@pytest.mark.parametrize(
    "slot,expected",
    [
        (100, "Zırh: Çizme"), (101, "Zırh: Pantolon"), (102, "Zırh: Göğüslük"), (103, "Zırh: Kask"),
        (-106, "İkinci El"), (0, "Sıcak Çubuk"), (8, "Sıcak Çubuk"), (9, "Envanter"), (35, "Envanter"),
        (40, "Slot 40"),
    ],
)
def test_categorize_inventory_slot(slot: int, expected: str):
    assert categorize_inventory_slot(slot) == expected


def test_inventory_and_ender_chest_query_commands():
    assert inventory_query_command("Steve") == "data get entity Steve Inventory"
    assert ender_chest_query_command("Steve") == "data get entity Steve EnderItems"


def test_heal_kill_feed_commands_are_well_formed():
    assert heal_command("Steve") == "effect give Steve minecraft:instant_health 1 10 true"
    assert kill_command("Steve") == "kill Steve"
    assert feed_command("Steve") == "effect give Steve minecraft:saturation 1 255 true"
    assert hunger_command("Steve", 30) == "effect give Steve minecraft:hunger 30 5 true"


def test_damage_command_uses_real_damage_command_on_modern_versions():
    assert damage_command("Steve", 10, "1.20.1") == "damage Steve 10"
    assert damage_command("Steve", 10, "1.19.4") == "damage Steve 10"


def test_damage_command_falls_back_to_effect_on_old_versions():
    cmd = damage_command("Steve", 10, "1.18.2")
    assert cmd.startswith("effect give Steve minecraft:instant_damage 1 ")
    assert cmd.endswith(" true")


# -- find_java ------------------------------------------------------------------


def test_find_java_uses_settings_path_when_valid(tmp_path: Path):
    fake_java = tmp_path / "java"
    fake_java.write_text("")
    assert find_java(str(fake_java)) == str(fake_java)


def test_find_java_returns_none_when_settings_path_invalid():
    assert find_java("/does/not/exist/java") is None


def test_find_java_falls_back_to_path():
    # Bu ortamda gerçekten Java kurulu (CI/geliştirme makinesi) — PATH'ten bulunmalı.
    found = find_java("")
    assert found is None or Path(found).name.startswith("java")


# -- RAM üst sınırı: kullanıcı isteği "sistemine en az 2 GB bırak" -------------


def test_get_system_memory_mb_detects_real_ram_on_this_machine():
    # Bu ortamda gerçekten RAM var (CI/geliştirme makinesi) — None DEĞİL,
    # makul bir pozitif değer dönmeli (ör. en az 1 GB).
    total = get_system_memory_mb()
    assert total is None or total > 1024


def test_max_safe_server_memory_mb_reserves_default_2gb():
    assert max_safe_server_memory_mb(16384) == 16384 - 2048


def test_max_safe_server_memory_mb_returns_none_when_total_unknown():
    assert max_safe_server_memory_mb(None) is None


def test_max_safe_server_memory_mb_never_goes_below_floor_on_low_ram_systems():
    assert max_safe_server_memory_mb(1500) == 512  # 1500-2048 negatif olurdu, floor'a düşer


def test_max_safe_server_memory_mb_custom_reserve():
    assert max_safe_server_memory_mb(8192, reserve_mb=1024) == 7168


# -- ServerProcess (gerçek Java yerine trivial bir echo script'i) --------------

_FAKE_SERVER_SCRIPT = """
import sys
print("[fake-server] starting...", flush=True)
print("Done! For help, type help", flush=True)
for line in sys.stdin:
    cmd = line.strip()
    print(f"> {cmd}", flush=True)
    if cmd == "list":
        print("There are 2 of a max of 20 players online: Steve, Alex", flush=True)
    if cmd == "stop":
        print("[fake-server] stopping...", flush=True)
        break
sys.exit(0)
"""


def _wait_until(predicate, timeout: float = 5.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.02)
    raise AssertionError("timeout waiting for condition")


def test_server_process_start_send_command_and_stop(tmp_path: Path):
    script = tmp_path / "fake_server.py"
    script.write_text(_FAKE_SERVER_SCRIPT, encoding="utf-8")

    process = ServerProcess()
    received: list[str] = []
    # DirectConnection: testte gerçek bir Qt event loop (app.exec()) çalışmıyor,
    # bu yüzden varsayılan Queued teslimat hiç işlenmez. Gerçek GUI'de
    # (gui/server_section.py) MainWindow'un event loop'u zaten çalıştığı
    # için orada varsayılan (Queued) bağlantı kullanılır.
    process.output_line.connect(received.append, Qt.ConnectionType.DirectConnection)

    process.start([sys.executable, str(script)], cwd=tmp_path)
    assert process.is_running

    _wait_until(lambda: any("Done!" in line for line in received))

    process.send_command("say hello")
    _wait_until(lambda: any(line == "> say hello" for line in received))

    process.stop(timeout=5)
    assert not process.is_running
    assert any("stopping" in line for line in received)


def test_server_process_start_twice_raises(tmp_path: Path):
    script = tmp_path / "fake_server.py"
    script.write_text(_FAKE_SERVER_SCRIPT, encoding="utf-8")

    process = ServerProcess()
    process.start([sys.executable, str(script)], cwd=tmp_path)
    try:
        with pytest.raises(ServerRuntimeError):
            process.start([sys.executable, str(script)], cwd=tmp_path)
    finally:
        process.stop(timeout=5)


def test_server_process_send_command_when_not_running_raises(tmp_path: Path):
    process = ServerProcess()
    with pytest.raises(ServerRuntimeError):
        process.send_command("say hi")


def test_server_process_send_command_and_wait_returns_matching_line(tmp_path: Path):
    """Gerçek ama oyuncusuz doğrulama (bkz. plan): gerçek bir Python
    subprocess'i, gerçek stdin/stdout, sadece gerçek Minecraft değil —
    send_command_and_wait'in gönder+eşleşen-yanıtı-bekle akışını kanıtlar."""
    script = tmp_path / "fake_server.py"
    script.write_text(_FAKE_SERVER_SCRIPT, encoding="utf-8")

    process = ServerProcess()
    process.start([sys.executable, str(script)], cwd=tmp_path)
    try:
        _wait_until(lambda: process.is_running)
        result = process.send_command_and_wait(
            list_players_command(), match=re.compile(r"players online:"), timeout=5
        )
        assert result is not None
        assert parse_list_response(result) == ["Steve", "Alex"]
    finally:
        process.stop(timeout=5)


def test_server_process_send_command_and_wait_times_out_when_no_match(tmp_path: Path):
    script = tmp_path / "fake_server.py"
    script.write_text(_FAKE_SERVER_SCRIPT, encoding="utf-8")

    process = ServerProcess()
    process.start([sys.executable, str(script)], cwd=tmp_path)
    try:
        _wait_until(lambda: process.is_running)
        result = process.send_command_and_wait(
            "say hi", match=re.compile(r"THIS_NEVER_MATCHES"), timeout=0.5
        )
        assert result is None
    finally:
        process.stop(timeout=5)


# -- prepare_server (respx-mocked ağ, gerçek dosya işlemleri) ------------------


def _make_pack(**kwargs) -> Pack:
    defaults = dict(name="Test", minecraft="1.20.1", loader=Loader.VANILLA, loader_version="")
    defaults.update(kwargs)
    return Pack(**defaults)


@pytest.mark.asyncio
async def test_prepare_server_downloads_real_vanilla_server_jar(tmp_path: Path):
    pack = _make_pack()
    manifest = {"versions": [{"id": "1.20.1", "url": "https://x/1.20.1.json"}]}
    version_meta = {"downloads": {"server": {"url": "https://x/server.jar", "sha1": None, "size": None}}}
    server_root = tmp_path / "server_root"

    with respx.mock:
        respx.get(VERSION_MANIFEST_URL).mock(return_value=httpx.Response(200, json=manifest))
        respx.get("https://x/1.20.1.json").mock(return_value=httpx.Response(200, json=version_meta))
        respx.get("https://x/server.jar").mock(return_value=httpx.Response(200, content=b"fake-server-bytes"))
        async with httpx.AsyncClient() as client:
            await prepare_server(
                pack,
                server_root=server_root,
                cache_dir=tmp_path / "cache",
                content_root=tmp_path / "content",
                client=client,
            )

    assert (server_root / "server.jar").read_bytes() == b"fake-server-bytes"
    assert server_state(server_root) == "ready"


@pytest.mark.asyncio
async def test_prepare_server_raises_server_runtime_error_when_download_fails(tmp_path: Path):
    """export/server.py'nin aksine (export'u bozmadan notice dosyasına
    düşer) prepare_server HATA FIRLATIR — burada "elle indirip klasöre
    koyun" diye bir zip akışı yok, kullanıcıya anında açık bir hata
    gösterilmeli (bkz. gui/server_section.py)."""
    pack = _make_pack(minecraft="99.99")
    server_root = tmp_path / "server_root"

    with respx.mock:
        respx.get(VERSION_MANIFEST_URL).mock(return_value=httpx.Response(200, json={"versions": []}))
        async with httpx.AsyncClient() as client:
            with pytest.raises(ServerRuntimeError):
                await prepare_server(
                    pack,
                    server_root=server_root,
                    cache_dir=tmp_path / "cache",
                    content_root=tmp_path / "content",
                    client=client,
                )
