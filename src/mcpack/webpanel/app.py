"""Yerel web paneli: sunucu yönetimi (başlat/durdur/konsol/oyuncular) için
Qt'ye EK bir arayüz — Qt'nin yerini almaz, aynı `server_runtime.py`
mantığını kullanır, hiçbir iş mantığı burada tekrar yazılmaz.

Kapsam (kullanıcı isteğiyle netleştirildi): SADECE zaten var olan bir
pack'in YEREL sunucu çalışma zamanı — hazırla/kur/başlat/durdur/konsol/
oyuncular/server.properties/bellek+performans ayarları. Pack oluşturma,
mod arama/ekleme/çıkarma, fork, mrpack/CurseForge/Prism export, "Sunucu
Paketi" zip export, SKLauncher çalıştırma, cheat modları — bunların
HİÇBİRİ burada YOK, hepsi Qt'de kalıyor.

GÜVENLİK (kullanıcı isteğiyle `0.0.0.0` üzerinden yayınlanıyor — ör.
telefondan erişim için): `Settings.web_panel_password` BOŞSA panel
`0.0.0.0`'a HİÇ AÇILMAZ, otomatik olarak sadece `127.0.0.1`'e düşer (bkz.
start_web_panel). Şifre girilmişse `0.0.0.0`'a açılır VE `require_auth`
dependency'si login/static/favicon DIŞINDAKİ her REST/WebSocket uç
noktasında zorunlu bir oturum cookie'si ister — aksi halde aynı ağdaki
HERKES kimlik doğrulamadan sunucuyu durdurabilir/oyuncu öldürebilir.
Oturumlar bellekte tutulur (kalıcı kullanıcı/şifre veritabanı gerekmiyor,
tek paylaşılan şifre yeterli — proje kişisel/küçük ölçekte).
"""

from __future__ import annotations

import asyncio
import queue
import re
import secrets
import socket
import sys
import threading
import time
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from mcpack.config import Settings
from mcpack.downloader import make_client
from mcpack.export.server import filter_server_mods
from mcpack.i18n import get_language, strings_with_prefix, t
from mcpack.models import ContentKind, Pack
from mcpack.packs.manager import PackManager
from mcpack.server_properties import KNOWN_PROPERTIES, merged_with_defaults, read_properties, write_properties
from mcpack.server_runtime import (
    ServerProcess,
    ServerProcessRegistry,
    ServerRuntimeError,
    build_launch_command,
    categorize_inventory_slot,
    damage_command,
    ender_chest_query_command,
    feed_command,
    find_installer_jar,
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
    run_installer,
    server_state,
)

def _static_dir() -> Path:
    """PyInstaller ile paketlenmişse sys._MEIPASS altındaki webpanel_static/
    (bkz. scripts/build.py --add-data), aksi halde paketin kendi static/
    klasörü (known_mods.py:_data_dir, main.py:_icon_path ile aynı desen)."""
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        return Path(frozen_base) / "webpanel_static"
    return Path(__file__).parent / "static"


STATIC_DIR = _static_dir()
SESSION_COOKIE = "mcpack_session"
_PLAYER_RESPONSE_PATTERN = re.compile(r"has the following entity data:")


# -- istek gövdeleri ------------------------------------------------------


class LoginRequest(BaseModel):
    password: str


class CommandRequest(BaseModel):
    text: str


class DamageRequest(BaseModel):
    amount: int = 4


class HungerRequest(BaseModel):
    duration_s: int = 30


class PropertiesUpdate(BaseModel):
    values: dict[str, str]


class SettingsUpdate(BaseModel):
    memory_mb: int
    selected_world: str | None = None
    eula_accepted: bool
    use_optimized_flags: bool


# -- yardımcılar ------------------------------------------------------------


def _load_pack_or_404(manager: PackManager, pack_id: str) -> Pack:
    try:
        return manager.load(pack_id)
    except Exception as exc:  # noqa: BLE001 - bozuk/eksik pack.json da 404 sayılır
        raise HTTPException(status_code=404, detail=t("webpanel.error.pack_not_found")) from exc


def _running_process_or_400(registry: ServerProcessRegistry, pack_id: str) -> ServerProcess:
    process = registry.get(pack_id)
    if process is None or not process.is_running:
        raise HTTPException(status_code=400, detail=t("webpanel.error.server_not_running"))
    return process


async def require_auth(request: Request) -> None:
    """Settings.web_panel_password BOŞSA (panel zaten sadece 127.0.0.1'e
    bağlı) hiçbir şey kontrol etmez. Doluysa geçerli bir oturum cookie'si
    ister."""
    password: str = request.app.state.password
    if not password:
        return
    token = request.cookies.get(SESSION_COOKIE)
    if not token or token not in request.app.state.sessions:
        raise HTTPException(status_code=401, detail=t("webpanel.error.login_required"))


# -- FastAPI app --------------------------------------------------------------


def create_app(*, manager: PackManager, registry: ServerProcessRegistry, settings: Settings) -> FastAPI:
    app = FastAPI(title="mcpack Web Paneli")
    app.state.manager = manager
    app.state.registry = registry
    app.state.settings = settings
    app.state.password = settings.web_panel_password
    app.state.sessions: set[str] = set()

    auth_dep = Depends(require_auth)

    # -- dil / çeviri ---------------------------------------------------------

    @app.get("/api/strings")
    async def strings() -> dict:
        """Kimlik doğrulama GEREKTİRMEZ (login ekranı da çevrilmeli) — frontend
        kendi çeviri tablosunu TUTMAZ, mcpack.i18n.STRINGS'in webpanel.*
        alt kümesini burada alır (bkz. mcpack/i18n.py:strings_with_prefix)."""
        return {"lang": get_language(), "strings": strings_with_prefix("webpanel.")}

    # -- kimlik doğrulama ---------------------------------------------------

    @app.get("/api/auth/status")
    async def auth_status(request: Request) -> dict:
        password = request.app.state.password
        token = request.cookies.get(SESSION_COOKIE)
        authenticated = not password or token in request.app.state.sessions
        return {"auth_required": bool(password), "authenticated": authenticated}

    @app.post("/api/auth/login")
    async def login(body: LoginRequest, request: Request, response: Response) -> dict:
        password = request.app.state.password
        if not password or not secrets.compare_digest(body.password, password):
            raise HTTPException(status_code=401, detail=t("webpanel.error.wrong_password"))
        token = secrets.token_urlsafe(32)
        request.app.state.sessions.add(token)
        response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
        return {"ok": True}

    @app.post("/api/auth/logout")
    async def logout(request: Request, response: Response) -> dict:
        token = request.cookies.get(SESSION_COOKIE)
        if token:
            request.app.state.sessions.discard(token)
        response.delete_cookie(SESSION_COOKIE)
        return {"ok": True}

    # -- sunucu listesi / durumu ---------------------------------------------

    @app.get("/api/servers", dependencies=[auth_dep])
    async def list_servers(request: Request) -> list[dict]:
        mgr: PackManager = request.app.state.manager
        reg: ServerProcessRegistry = request.app.state.registry
        result = []
        for pack in mgr.list_packs():
            result.append({
                "id": pack.id,
                "name": pack.name,
                "minecraft": pack.minecraft,
                "loader": pack.loader.value,
                "loader_version": pack.loader_version,
                "state": server_state(mgr.server_root(pack)),
                "running": reg.is_running(pack.id),
            })
        return result

    @app.get("/api/servers/{pack_id}", dependencies=[auth_dep])
    async def get_server(pack_id: str, request: Request) -> dict:
        mgr: PackManager = request.app.state.manager
        reg: ServerProcessRegistry = request.app.state.registry
        pack = _load_pack_or_404(mgr, pack_id)
        total_mb = get_system_memory_mb()
        # Kullanıcı isteği: "server kısmında mod falan var ise onları da
        # göstersin" — Hazırla'nın server_root'a kopyalayacağı modların
        # AYNISI (export/server.py:filter_server_mods, zip export'uyla
        # birebir aynı eleme mantığı).
        server_mods = filter_server_mods(pack)
        return {
            "id": pack.id,
            "name": pack.name,
            "minecraft": pack.minecraft,
            "loader": pack.loader.value,
            "loader_version": pack.loader_version,
            "state": server_state(mgr.server_root(pack)),
            "running": reg.is_running(pack.id),
            "memory_mb": pack.server.memory_mb,
            "selected_world": pack.server.selected_world,
            "eula_accepted": pack.server.eula_accepted,
            "use_optimized_flags": pack.server.use_optimized_flags,
            "worlds": [e.name for e in pack.content_of(ContentKind.WORLD)],
            "system_memory_mb": total_mb,
            "max_safe_memory_mb": max_safe_server_memory_mb(total_mb),
            "mods": [
                {"name": m.name or m.file_name, "source": m.source.value, "file_name": m.file_name}
                for m in server_mods
            ],
            "mods_excluded_count": len(pack.mods) - len(server_mods),
        }

    # -- hazırla / kur / başlat / durdur / komut -----------------------------

    @app.post("/api/servers/{pack_id}/prepare", dependencies=[auth_dep])
    async def prepare(pack_id: str, request: Request) -> dict:
        mgr: PackManager = request.app.state.manager
        pack = _load_pack_or_404(mgr, pack_id)
        server_root = mgr.server_root(pack)
        try:
            async with make_client() as client:
                await prepare_server(
                    pack,
                    server_root=server_root,
                    cache_dir=mgr.packs_dir / ".cache" / pack.id,
                    content_root=mgr.content_root(pack),
                    client=client,
                )
        except ServerRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"state": server_state(server_root)}

    @app.post("/api/servers/{pack_id}/install", dependencies=[auth_dep])
    async def install(pack_id: str, request: Request) -> dict:
        mgr: PackManager = request.app.state.manager
        settings_obj: Settings = request.app.state.settings
        pack = _load_pack_or_404(mgr, pack_id)
        server_root = mgr.server_root(pack)
        installer = find_installer_jar(server_root)
        if installer is None:
            raise HTTPException(status_code=400, detail=t("webpanel.error.installer_not_found"))
        java_path = find_java(settings_obj.java_path)
        if java_path is None:
            raise HTTPException(status_code=400, detail=t("webpanel.error.java_not_found"))
        try:
            lines = await run_installer(installer, server_root, java_path)
        except ServerRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"state": server_state(server_root), "output": lines[-50:]}

    @app.post("/api/servers/{pack_id}/start", dependencies=[auth_dep])
    async def start(pack_id: str, request: Request) -> dict:
        mgr: PackManager = request.app.state.manager
        settings_obj: Settings = request.app.state.settings
        reg: ServerProcessRegistry = request.app.state.registry
        pack = _load_pack_or_404(mgr, pack_id)

        if not pack.server.eula_accepted:
            raise HTTPException(status_code=400, detail=t("webpanel.error.eula_required"))
        if reg.is_running(pack.id):
            raise HTTPException(status_code=400, detail=t("webpanel.error.server_already_running"))

        server_root = mgr.server_root(pack)
        if server_state(server_root) != "ready":
            raise HTTPException(status_code=400, detail=t("webpanel.error.server_not_ready"))
        java_path = find_java(settings_obj.java_path)
        if java_path is None:
            raise HTTPException(status_code=400, detail=t("webpanel.error.java_not_found"))

        try:
            cmd = build_launch_command(
                server_root, pack.server.memory_mb, optimized=pack.server.use_optimized_flags
            )
        except ServerRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        if cmd[0] == "java":
            cmd[0] = java_path

        # eula.txt SADECE burada, pack.server.eula_accepted (kullanıcının
        # Qt ya da web panelinde açıkça verdiği onay) True olduğu için yazılır.
        (server_root / "eula.txt").write_text("eula=true\n", encoding="utf-8")

        process = ServerProcess()
        reg.set(pack.id, process)
        try:
            process.start(cmd, cwd=server_root)
        except ServerRuntimeError as exc:
            reg.pop(pack.id)
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"running": True}

    @app.post("/api/servers/{pack_id}/stop", dependencies=[auth_dep])
    async def stop(pack_id: str, request: Request) -> dict:
        reg: ServerProcessRegistry = request.app.state.registry
        process = reg.get(pack_id)
        if process is None or not process.is_running:
            return {"running": False}
        await asyncio.to_thread(process.stop, 30)
        return {"running": process.is_running}

    @app.post("/api/servers/{pack_id}/command", dependencies=[auth_dep])
    async def send_command(pack_id: str, body: CommandRequest, request: Request) -> dict:
        process = _running_process_or_400(request.app.state.registry, pack_id)
        try:
            process.send_command(body.text)
        except ServerRuntimeError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"ok": True}

    # -- server.properties / ayarlar -----------------------------------------

    @app.get("/api/servers/{pack_id}/properties", dependencies=[auth_dep])
    async def get_properties(pack_id: str, request: Request) -> dict:
        mgr: PackManager = request.app.state.manager
        pack = _load_pack_or_404(mgr, pack_id)
        path = mgr.server_root(pack) / "server.properties"
        return {
            "values": merged_with_defaults(read_properties(path)),
            "known": [
                # p.label (server_properties.py) KASITLI yok sayılıyor —
                # Qt tarafındaki gui/server_section.py ile AYNI anahtar
                # deseni (bkz. i18n.py:serverprop.{key}.label).
                {"key": p.key, "label": t(f"serverprop.{p.key}.label"), "type": p.type, "default": p.default, "choices": p.choices}
                for p in KNOWN_PROPERTIES
            ],
        }

    @app.put("/api/servers/{pack_id}/properties", dependencies=[auth_dep])
    async def put_properties(pack_id: str, body: PropertiesUpdate, request: Request) -> dict:
        mgr: PackManager = request.app.state.manager
        pack = _load_pack_or_404(mgr, pack_id)
        path = mgr.server_root(pack) / "server.properties"
        # Sunucunun kendi ürettiği, burada hiç gösterilmeyen diğer tüm
        # anahtarları KORUYARAK sadece bilinen alanları günceller.
        current = read_properties(path)
        current.update(body.values)
        write_properties(path, current)
        return {"ok": True}

    @app.put("/api/servers/{pack_id}/settings", dependencies=[auth_dep])
    async def put_settings(pack_id: str, body: SettingsUpdate, request: Request) -> dict:
        mgr: PackManager = request.app.state.manager
        pack = _load_pack_or_404(mgr, pack_id)
        mgr.update_server_config(
            pack,
            memory_mb=body.memory_mb,
            selected_world=body.selected_world,
            eula_accepted=body.eula_accepted,
            use_optimized_flags=body.use_optimized_flags,
        )
        return {"ok": True}

    # -- oyuncular -------------------------------------------------------------

    @app.get("/api/servers/{pack_id}/players", dependencies=[auth_dep])
    async def list_players(pack_id: str, request: Request) -> dict:
        process = _running_process_or_400(request.app.state.registry, pack_id)
        line = await asyncio.to_thread(
            process.send_command_and_wait,
            list_players_command(),
            match=re.compile(r"players online:"),
            timeout=5,
        )
        if line is None:
            raise HTTPException(status_code=504, detail=t("webpanel.error.timeout"))
        return {"players": parse_list_response(line) or []}

    @app.post("/api/servers/{pack_id}/players/{player}/heal", dependencies=[auth_dep])
    async def player_heal(pack_id: str, player: str, request: Request) -> dict:
        process = _running_process_or_400(request.app.state.registry, pack_id)
        process.send_command(heal_command(player))
        return {"ok": True}

    @app.post("/api/servers/{pack_id}/players/{player}/kill", dependencies=[auth_dep])
    async def player_kill(pack_id: str, player: str, request: Request) -> dict:
        process = _running_process_or_400(request.app.state.registry, pack_id)
        process.send_command(kill_command(player))
        return {"ok": True}

    @app.post("/api/servers/{pack_id}/players/{player}/feed", dependencies=[auth_dep])
    async def player_feed(pack_id: str, player: str, request: Request) -> dict:
        process = _running_process_or_400(request.app.state.registry, pack_id)
        process.send_command(feed_command(player))
        return {"ok": True}

    @app.post("/api/servers/{pack_id}/players/{player}/damage", dependencies=[auth_dep])
    async def player_damage(pack_id: str, player: str, body: DamageRequest, request: Request) -> dict:
        process = _running_process_or_400(request.app.state.registry, pack_id)
        pack = _load_pack_or_404(request.app.state.manager, pack_id)
        process.send_command(damage_command(player, body.amount, pack.minecraft))
        return {"ok": True}

    @app.post("/api/servers/{pack_id}/players/{player}/hunger", dependencies=[auth_dep])
    async def player_hunger(pack_id: str, player: str, body: HungerRequest, request: Request) -> dict:
        process = _running_process_or_400(request.app.state.registry, pack_id)
        process.send_command(hunger_command(player, body.duration_s))
        return {"ok": True}

    @app.get("/api/servers/{pack_id}/players/{player}/inventory", dependencies=[auth_dep])
    async def player_inventory(pack_id: str, player: str, request: Request) -> dict:
        process = _running_process_or_400(request.app.state.registry, pack_id)
        line = await asyncio.to_thread(
            process.send_command_and_wait, inventory_query_command(player), match=_PLAYER_RESPONSE_PATTERN, timeout=5
        )
        if line is None:
            raise HTTPException(status_code=504, detail=t("webpanel.error.timeout"))
        items = parse_item_list_response(line) or []
        return {
            "items": [
                {"slot": i.slot, "item_id": i.item_id, "count": i.count, "category": categorize_inventory_slot(i.slot)}
                for i in items
            ]
        }

    @app.get("/api/servers/{pack_id}/players/{player}/ender-chest", dependencies=[auth_dep])
    async def player_ender_chest(pack_id: str, player: str, request: Request) -> dict:
        process = _running_process_or_400(request.app.state.registry, pack_id)
        line = await asyncio.to_thread(
            process.send_command_and_wait,
            ender_chest_query_command(player),
            match=_PLAYER_RESPONSE_PATTERN,
            timeout=5,
        )
        if line is None:
            raise HTTPException(status_code=504, detail=t("webpanel.error.timeout"))
        items = parse_item_list_response(line) or []
        return {"items": [{"slot": i.slot, "item_id": i.item_id, "count": i.count} for i in items]}

    # -- canlı konsol (WebSocket, SADECE sunucu->istemci) --------------------

    @app.websocket("/ws/servers/{pack_id}/console")
    async def console_ws(websocket: WebSocket, pack_id: str) -> None:
        password = websocket.app.state.password
        if password:
            token = websocket.cookies.get(SESSION_COOKIE)
            if not token or token not in websocket.app.state.sessions:
                await websocket.close(code=4401)
                return

        reg: ServerProcessRegistry = websocket.app.state.registry
        process = reg.get(pack_id)
        await websocket.accept()
        if process is None:
            await websocket.send_json({"type": "error", "text": t("webpanel.error.server_not_found_ws")})
            await websocket.close()
            return

        for line in list(process.buffer):
            await websocket.send_json({"type": "line", "text": line})

        line_queue: queue.Queue[str | None] = queue.Queue()
        process.add_listener(line_queue.put)

        async def forward_lines() -> None:
            # queue.Queue.get SÜRESİZ bloklayan senkron bir çağrı — asyncio
            # iptali bunu kesemez (alttaki thread askıda kalır). 1sn'lik
            # zaman aşımıyla döngüye alıp queue.Empty'de tekrar denemek,
            # bu task iptal edilince thread'in makul sürede (en geç ~1sn)
            # serbest kalmasını sağlar.
            while True:
                try:
                    line = await asyncio.to_thread(line_queue.get, True, 1.0)
                except queue.Empty:
                    continue
                if line is None:
                    await websocket.send_json({"type": "exited"})
                    return
                await websocket.send_json({"type": "line", "text": line})

        async def watch_disconnect() -> None:
            # Handler SADECE gönderiyor (istemciden bir şey beklemiyoruz) —
            # istemci bağlantıyı kapatınca bunu fark edebilmek için AYRICA
            # receive() çağıran bir task gerekiyor, yoksa yukarıdaki
            # forward_lines sonsuza dek bekler (gerçek hata: bu olmadan
            # testte deadlock oluştu).
            try:
                while True:
                    await websocket.receive_text()
            except WebSocketDisconnect:
                pass

        forward_task = asyncio.create_task(forward_lines())
        disconnect_task = asyncio.create_task(watch_disconnect())
        try:
            await asyncio.wait({forward_task, disconnect_task}, return_when=asyncio.FIRST_COMPLETED)
        finally:
            forward_task.cancel()
            disconnect_task.cancel()
            process.remove_listener(line_queue.put)

    # -- statik dosyalar / ana sayfa -------------------------------------------

    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    return app


# -- gömülü sunucuyu başlatma/durdurma (Qt event loop'uyla ÇAKIŞMAZ) ----------


def _guess_local_ip() -> str | None:
    """UDP "connect" gerçek bir paket göndermez, sadece işletim sistemine
    bu hedefe giden arayüzü sorar — ağdaki diğer cihazlara (ör. telefon)
    gösterilecek adresi tahmin etmek için yaygın, zararsız bir numara."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("8.8.8.8", 80))
            return s.getsockname()[0]
    except OSError:
        return None


class WebPanelHandle:
    def __init__(
        self, server: uvicorn.Server, thread: threading.Thread, *, host: str, port: int, display_host: str
    ) -> None:
        self._server = server
        self._thread = thread
        self.host = host
        self.port = port
        self.display_host = display_host

    @property
    def url(self) -> str:
        return f"http://{self.display_host}:{self.port}"

    @property
    def network_exposed(self) -> bool:
        return self.host == "0.0.0.0"

    def stop(self) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=5)


def start_web_panel(*, manager: PackManager, registry: ServerProcessRegistry, settings: Settings) -> WebPanelHandle:
    """Embedded web sunucusunu arka plan thread'inde başlatır — Qt'nin
    kendi event loop'uyla (QApplication.exec()) ÇAKIŞMAZ, ayrı bir thread,
    kendi asyncio event loop'u.

    GÜVENLİK: settings.web_panel_password BOŞSA host HER ZAMAN 127.0.0.1
    olur (ağa açılmaz) — bu, çağıran tarafın (gui/main_window.py) elle
    kontrol etmesi gereken bir şey DEĞİL, burada zorunlu kılınıyor."""
    app = create_app(manager=manager, registry=registry, settings=settings)
    host = "0.0.0.0" if settings.web_panel_password else "127.0.0.1"
    display_host = (_guess_local_ip() or host) if host == "0.0.0.0" else "127.0.0.1"
    port = settings.web_panel_port

    config = uvicorn.Config(app, host=host, port=port, log_level="warning")
    server = uvicorn.Server(config)

    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    deadline = time.time() + 5
    while time.time() < deadline and not server.started:
        time.sleep(0.05)

    return WebPanelHandle(server, thread, host=host, port=port, display_host=display_host)
