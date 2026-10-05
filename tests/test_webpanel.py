"""webpanel/app.py testleri: FastAPI TestClient ile REST uç noktaları
(gerçek PackManager + tmp_path, respx-mock'lu ağ — test_server_jar.py/
test_server_runtime.py ile aynı desen) ve websocket_connect ile konsol
akışı. Çalışan bir süreç gerektiren testler (komut/oyuncu/WS), test_
server_runtime.py'deki AYNI fake-server script tekniğiyle registry'ye
DOĞRUDAN bir ServerProcess enjekte eder — /start route'unun gerçek java
bulma mantığına bağımlı olmadan, temiz bir sınırda test eder."""

from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from mcpack.config import Settings
from mcpack.models import Loader
from mcpack.packs.manager import PackManager
from mcpack.server_jar import VERSION_MANIFEST_URL
from mcpack.server_runtime import ServerProcess, ServerProcessRegistry
from mcpack.webpanel.app import create_app

_FAKE_SERVER_SCRIPT = """
import sys
print("Done! For help, type help", flush=True)
for line in sys.stdin:
    cmd = line.strip()
    print(f"> {cmd}", flush=True)
    if cmd == "list":
        print("There are 1 of a max of 20 players online: Steve", flush=True)
    if cmd.startswith("data get entity"):
        print('Steve has the following entity data: [{Slot: 0b, id: "minecraft:bread", Count: 3b}]', flush=True)
    if cmd == "stop":
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


@pytest.fixture
def manager(tmp_path: Path) -> PackManager:
    return PackManager(tmp_path / "packs")


@pytest.fixture
def pack(manager: PackManager):
    return manager.create_pack(name="Test", minecraft="1.20.1", loader=Loader.VANILLA, loader_version="")


def _make_client(manager: PackManager, *, password: str = "") -> tuple[TestClient, ServerProcessRegistry]:
    registry = ServerProcessRegistry()
    settings = Settings(web_panel_password=password)
    app = create_app(manager=manager, registry=registry, settings=settings)
    return TestClient(app), registry


# -- auth ---------------------------------------------------------------


def test_auth_not_required_when_no_password(manager: PackManager):
    client, _ = _make_client(manager)
    status = client.get("/api/auth/status").json()
    assert status == {"auth_required": False, "authenticated": True}
    assert client.get("/api/servers").status_code == 200


def test_auth_required_endpoints_reject_without_cookie(manager: PackManager):
    client, _ = _make_client(manager, password="secret")
    status = client.get("/api/auth/status").json()
    assert status == {"auth_required": True, "authenticated": False}
    assert client.get("/api/servers").status_code == 401


def test_login_with_wrong_password_rejected(manager: PackManager):
    client, _ = _make_client(manager, password="secret")
    resp = client.post("/api/auth/login", json={"password": "yanlis"})
    assert resp.status_code == 401
    assert client.get("/api/servers").status_code == 401


def test_login_with_correct_password_grants_access(manager: PackManager):
    client, _ = _make_client(manager, password="secret")
    resp = client.post("/api/auth/login", json={"password": "secret"})
    assert resp.status_code == 200
    assert client.get("/api/servers").status_code == 200

    status = client.get("/api/auth/status").json()
    assert status == {"auth_required": True, "authenticated": True}

    client.post("/api/auth/logout")
    assert client.get("/api/servers").status_code == 401


# -- sunucu listesi / detay ----------------------------------------------


def test_list_servers_includes_created_pack(manager: PackManager, pack):
    client, _ = _make_client(manager)
    servers = client.get("/api/servers").json()
    assert len(servers) == 1
    assert servers[0]["id"] == pack.id
    assert servers[0]["name"] == "Test"
    assert servers[0]["state"] == "not_prepared"
    assert servers[0]["running"] is False


def test_get_server_detail_includes_memory_and_worlds(manager: PackManager, pack):
    client, _ = _make_client(manager)
    detail = client.get(f"/api/servers/{pack.id}").json()
    assert detail["memory_mb"] == 2048
    assert detail["worlds"] == []
    assert detail["max_safe_memory_mb"] is None or detail["max_safe_memory_mb"] > 0
    assert detail["mods"] == []
    assert detail["mods_excluded_count"] == 0


def test_get_server_detail_lists_server_mods_and_excludes_client_only(manager: PackManager, pack):
    """Kullanıcı isteği: "server kısmında mod falan var ise onları da
    göstersin" — /api/servers/{id} server-compatible modları (zip
    export'uyla AYNI filter_server_mods mantığıyla) döner, istemci-only
    modları sayıp hariç tutar, eklemez."""
    from mcpack.models import EnvRequirement, ModEnv, ModEntry, ModHashes, ModSourceType

    pack.mods.append(
        ModEntry(
            source=ModSourceType.MODRINTH, project_id="fabric-api", name="Fabric API",
            version_id="v1", file_name="fabric-api.jar", download_url="https://x/fabric-api.jar",
            hashes=ModHashes(), env=ModEnv(client=EnvRequirement.REQUIRED, server=EnvRequirement.REQUIRED),
        )
    )
    pack.mods.append(
        ModEntry(
            source=ModSourceType.MODRINTH, project_id="sodium", name="Sodium",
            version_id="v1", file_name="sodium.jar", download_url="https://x/sodium.jar",
            hashes=ModHashes(), env=ModEnv(client=EnvRequirement.REQUIRED, server=EnvRequirement.UNSUPPORTED),
        )
    )
    manager.save(pack)

    client, _ = _make_client(manager)
    detail = client.get(f"/api/servers/{pack.id}").json()
    assert [m["name"] for m in detail["mods"]] == ["Fabric API"]
    assert detail["mods_excluded_count"] == 1


def test_get_unknown_server_404(manager: PackManager):
    client, _ = _make_client(manager)
    assert client.get("/api/servers/does-not-exist").status_code == 404


# -- prepare (respx-mock'lu gerçek ağ akışı) ----------------------------


def test_prepare_downloads_real_vanilla_server_jar(manager: PackManager, pack):
    client, _ = _make_client(manager)
    manifest = {"versions": [{"id": "1.20.1", "url": "https://x/1.20.1.json"}]}
    version_meta = {"downloads": {"server": {"url": "https://x/server.jar", "sha1": None, "size": None}}}

    with respx.mock:
        respx.get(VERSION_MANIFEST_URL).mock(return_value=httpx.Response(200, json=manifest))
        respx.get("https://x/1.20.1.json").mock(return_value=httpx.Response(200, json=version_meta))
        respx.get("https://x/server.jar").mock(return_value=httpx.Response(200, content=b"fake-bytes"))
        resp = client.post(f"/api/servers/{pack.id}/prepare")

    assert resp.status_code == 200
    assert resp.json()["state"] == "ready"
    assert (manager.server_root(pack) / "server.jar").read_bytes() == b"fake-bytes"


# -- ayarlar / server.properties -----------------------------------------


def test_put_settings_persists(manager: PackManager, pack):
    client, _ = _make_client(manager)
    resp = client.put(
        f"/api/servers/{pack.id}/settings",
        json={"memory_mb": 4096, "selected_world": None, "eula_accepted": True, "use_optimized_flags": True},
    )
    assert resp.status_code == 200
    reloaded = manager.load(pack.id)
    assert reloaded.server.memory_mb == 4096
    assert reloaded.server.eula_accepted is True
    assert reloaded.server.use_optimized_flags is True


def test_properties_roundtrip_preserves_unknown_keys(manager: PackManager, pack):
    client, _ = _make_client(manager)
    properties_path = manager.server_root(pack) / "server.properties"
    properties_path.parent.mkdir(parents=True, exist_ok=True)
    properties_path.write_text("spawn-protection=16\nmotd=Eski Mesaj\n", encoding="utf-8")

    resp = client.put(f"/api/servers/{pack.id}/properties", json={"values": {"motd": "Yeni Mesaj"}})
    assert resp.status_code == 200

    content = properties_path.read_text(encoding="utf-8")
    assert "spawn-protection=16" in content  # bilinmeyen anahtar KORUNDU
    assert "motd=Yeni Mesaj" in content

    data = client.get(f"/api/servers/{pack.id}/properties").json()
    assert data["values"]["motd"] == "Yeni Mesaj"
    assert any(p["key"] == "motd" for p in data["known"])


# -- çalışan süreç gerektiren uç noktalar (fake-server script) ------------


def test_command_endpoint_requires_running_server(manager: PackManager, pack):
    client, _ = _make_client(manager)
    resp = client.post(f"/api/servers/{pack.id}/command", json={"text": "say hi"})
    assert resp.status_code == 400


def test_command_and_players_against_fake_running_process(manager: PackManager, pack, tmp_path: Path):
    client, registry = _make_client(manager)
    script = tmp_path / "fake_server.py"
    script.write_text(_FAKE_SERVER_SCRIPT, encoding="utf-8")

    process = ServerProcess()
    process.start([sys.executable, str(script)], cwd=tmp_path)
    registry.set(pack.id, process)
    try:
        _wait_until(lambda: process.is_running)

        resp = client.post(f"/api/servers/{pack.id}/command", json={"text": "say hello"})
        assert resp.status_code == 200
        _wait_until(lambda: any("> say hello" in line for line in process.buffer))

        players = client.get(f"/api/servers/{pack.id}/players").json()
        assert players["players"] == ["Steve"]

        inv = client.get(f"/api/servers/{pack.id}/players/Steve/inventory").json()
        assert inv["items"] == [{"slot": 0, "item_id": "minecraft:bread", "count": 3, "category": "Sıcak Çubuk"}]

        assert client.post(f"/api/servers/{pack.id}/players/Steve/heal").status_code == 200
        _wait_until(lambda: any("effect give Steve minecraft:instant_health" in line for line in process.buffer))
    finally:
        process.stop(timeout=5)


def test_console_websocket_streams_buffered_and_live_lines(manager: PackManager, pack, tmp_path: Path):
    client, registry = _make_client(manager)
    script = tmp_path / "fake_server.py"
    script.write_text(_FAKE_SERVER_SCRIPT, encoding="utf-8")

    process = ServerProcess()
    process.start([sys.executable, str(script)], cwd=tmp_path)
    registry.set(pack.id, process)
    try:
        _wait_until(lambda: any("Done!" in line for line in process.buffer))

        with client.websocket_connect(f"/ws/servers/{pack.id}/console") as ws:
            messages = []
            while True:
                msg = ws.receive_json()
                messages.append(msg)
                if any(m.get("type") == "line" and "Done!" in m.get("text", "") for m in messages):
                    break
            assert any("Done!" in m["text"] for m in messages if m["type"] == "line")

            process.send_command("say canli satir")
            while True:
                msg = ws.receive_json()
                if msg.get("type") == "line" and "say canli satir" in msg.get("text", ""):
                    break
    finally:
        process.stop(timeout=5)
