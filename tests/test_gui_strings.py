"""Arayüzde kullanılan her çeviri anahtarı iki dilde de tanımlı olmalı.

Sabit anahtarlar (t("a.b")) kaynak koddan taranır; f-string ile üretilen
dinamik anahtarlar (t(f"pack.section.{key}") vb.) aşağıda açıkça genişletilir.
"""

from __future__ import annotations

import re
from pathlib import Path

import mcpack.gui  # noqa: F401  (gui/strings.py'yi STRINGS'e kaydeder)
from mcpack.i18n import STRINGS

GUI_DIR = Path(__file__).resolve().parents[1] / "src" / "mcpack" / "gui"
_KEY_RE = re.compile(r"""\bt\(\s*(f?)["']([^"']+)["']""")

DYNAMIC = {
    "content.{key}.empty_title": [f"content.{k}.empty_title" for k in ("shaderpack", "resourcepack", "datapack", "world")],
    "content.{key}.empty_sub": [f"content.{k}.empty_sub" for k in ("shaderpack", "resourcepack", "datapack", "world")],
    "debug.log.col.{self.HEADERS[section]}": [f"debug.log.col.{k}" for k in ("time", "level", "logger", "thread", "message")],
    "debug.tab.{key}": [f"debug.tab.{k}" for k in ("logs", "tasks", "network", "exceptions", "system", "python")],
    "debug.tasks.status.{task.status}": [f"debug.tasks.status.{k}" for k in ("queued", "running", "done", "failed", "cancelled")],
    "discover.kind.{key}": [f"discover.kind.{k}" for k in ("mods", "shaderpack", "resourcepack", "datapack", "world")],
    "env.editor_{side}": ["env.editor_client", "env.editor_server"],
    "env.req.{req.value}": ["env.req.required", "env.req.optional", "env.req.unsupported"],
    "mods.col.{COLS[section]}": [f"mods.col.{k}" for k in ("name", "source", "env", "file", "size", "deps")],
    "nav.{key}": [f"nav.{k}" for k in ("home", "library", "pack", "settings", "debug")],
    "pack.section.{key}": [f"pack.section.{k}" for k in ("overview", "mods", "discover", "shaderpack", "resourcepack", "datapack", "world", "server", "cheats")],
    "pack.section.{section}": [],
    "player.action.{action}": [f"player.action.{k}" for k in ("heal", "feed", "kill", "damage", "hunger")],
    "player.action.{key}": [],
    "players.{which}_title": ["players.inventory_title", "players.ender_title"],
    "server.state.{self.state}": [f"server.state.{k}" for k in ("not_prepared", "needs_install", "ready")],
    "serverprop.{prop.key}.label": [],
    "updates.kind.{u.kind.value}": [f"updates.kind.{k}" for k in ("shaderpack", "resourcepack", "datapack", "world")],
    "status.task_{task.status}": ["status.task_done", "status.task_failed", "status.task_cancelled"],
}


def _used_keys() -> set[str]:
    keys: set[str] = set()
    for path in GUI_DIR.rglob("*.py"):
        if path.name == "strings.py":
            continue
        for is_f, key in _KEY_RE.findall(path.read_text(encoding="utf-8")):
            if is_f and "{" in key:
                assert key in DYNAMIC, f"{path.name}: dinamik anahtar test listesinde yok: {key}"
                keys.update(DYNAMIC[key])
            else:
                keys.add(key)
    return keys


def test_all_gui_keys_exist_in_both_languages():
    missing = sorted(k for k in _used_keys() if k not in STRINGS)
    assert not missing, f"Tanımsız çeviri anahtarları: {missing}"
    incomplete = sorted(k for k in _used_keys() if not (STRINGS[k].get("tr") and STRINGS[k].get("en")) and k != "server.empty_sub")
    assert not incomplete, f"Eksik dil: {incomplete}"


def test_format_placeholders_match_between_languages():
    field = re.compile(r"{(\w+)}")
    for key, entry in STRINGS.items():
        tr, en = entry.get("tr", ""), entry.get("en", "")
        assert set(field.findall(tr)) == set(field.findall(en)), key
