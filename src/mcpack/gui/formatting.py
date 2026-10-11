"""Qt'den bağımsız, saf biçimlendirme yardımcıları (birim testli — bkz.
tests/test_gui_formatting.py). Widget'lar bu fonksiyonları kullanır;
burada hiçbir PySide6 import'u yoktur."""

from __future__ import annotations

from datetime import datetime, timezone

from mcpack.i18n import t

SOURCE_LABELS = {
    "modrinth": "Modrinth",
    "curseforge": "CurseForge",
    "wurst": "Wurst Client",
    "meteor": "Meteor Client",
}

LOADER_LABELS = {
    "vanilla": "Vanilla",
    "fabric": "Fabric",
    "quilt": "Quilt",
    "forge": "Forge",
    "neoforge": "NeoForge",
}

LOADER_GLYPHS = {
    "vanilla": "🌱",
    "fabric": "🧵",
    "quilt": "🧶",
    "forge": "🔨",
    "neoforge": "🔥",
}


def source_label(value: str) -> str:
    return SOURCE_LABELS.get(value, value)


def loader_label(value: str) -> str:
    return LOADER_LABELS.get(value, value.capitalize())


def environment_label(client: str, server: str) -> str:
    """Tek, birleşik ortam etiketi: sadece istemci ya da sadece sunucu ile
    çalışabiliyorsa ayrı ayrı gösterilir; ikisiyle de çalışıyorsa tek bir
    "İstemci + Sunucu" etiketi."""
    client_ok = client != "unsupported"
    server_ok = server != "unsupported"
    if client_ok and server_ok:
        return t("env.client_server")
    if client_ok:
        return t("env.client")
    if server_ok:
        return t("env.server")
    return t("env.unknown")


def format_count(n: int) -> str:
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def format_size(num_bytes: int | None) -> str:
    if num_bytes is None:
        return "—"
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024 or unit == "GB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} GB"


def format_duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = max(0, int(seconds))
    hours, rem = divmod(seconds, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"


def format_relative(dt: datetime | None, *, now: datetime | None = None) -> str:
    """"3 dk önce" / "2 saat önce" / "5 gün önce" — kütüphane kartlarında."""
    if dt is None:
        return "—"
    now = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = (now - dt).total_seconds()
    if delta < 60:
        return t("time.just_now")
    if delta < 3600:
        return t("time.minutes_ago", n=int(delta // 60))
    if delta < 86400:
        return t("time.hours_ago", n=int(delta // 3600))
    if delta < 86400 * 30:
        return t("time.days_ago", n=int(delta // 86400))
    return dt.astimezone().strftime("%Y-%m-%d")


def fuzzy_score(query: str, text: str) -> int | None:
    """Komut paleti için basit alt-dizi eşleştirme: query'nin harfleri text'te
    SIRAYLA geçiyorsa bir skor (küçük = daha iyi), geçmiyorsa None. Bitişik
    eşleşmeler ve kelime başı eşleşmeleri ödüllendirilir."""
    if not query:
        return 0
    q = query.lower()
    s = text.lower()
    if q in s:
        return s.index(q)
    score = 0
    pos = -1
    for ch in q:
        nxt = s.find(ch, pos + 1)
        if nxt < 0:
            return None
        gap = nxt - pos - 1
        score += gap * 2
        if nxt > 0 and s[nxt - 1] not in " -_./":
            score += 1
        pos = nxt
    return 100 + score


def project_url(source: str, project_id: str, slug: str | None = None) -> str | None:
    """Mod/içerik için tarayıcıda açılabilecek proje sayfası."""
    if source == "modrinth":
        return f"https://modrinth.com/project/{slug or project_id}"
    if source == "curseforge":
        return f"https://www.curseforge.com/projects/{project_id}"
    if source == "wurst":
        return "https://www.wurstclient.net/"
    if source == "meteor":
        return "https://meteorclient.com/"
    return None
