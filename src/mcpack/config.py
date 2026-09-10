"""Kullanıcı ayarları: CurseForge API key, SKLauncher yolu, tercihler.

Ayarlar diskte JSON olarak saklanır. CurseForge API key ASLA koda gömülmez,
sadece kullanıcının kendi ayar dosyasında tutulur (bkz. proje-amacı.md §6).
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from pydantic import BaseModel


def config_dir() -> Path:
    """İşletim sistemine göre kullanıcı ayar dizini."""
    if os.name == "nt":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    path = base / "mcpack"
    path.mkdir(parents=True, exist_ok=True)
    return path


def default_packs_dir() -> Path:
    path = config_dir() / "packs"
    path.mkdir(parents=True, exist_ok=True)
    return path


SETTINGS_FILE = "settings.json"


class Settings(BaseModel):
    curseforge_api_key: str = ""
    prefer_modrinth: bool = True
    """Aynı mod her iki sitede de varsa Modrinth tercih edilsin mi."""
    sklauncher_path: str = ""
    """Portable SKLauncher yolu (Windows .exe, Linux AppImage veya .jar)."""
    packs_dir: str = ""
    """Boşsa default_packs_dir() kullanılır."""
    exclude_logs: bool = True
    exclude_crash_reports: bool = True
    exclude_saves: bool = True
    theme: str = "dark"
    """"dark" ya da "light" — bkz. gui/theme.py."""

    def resolved_packs_dir(self) -> Path:
        return Path(self.packs_dir) if self.packs_dir else default_packs_dir()

    def excluded_override_dirs(self) -> set[str]:
        """Export sırasında overrides'tan hariç tutulacak dizin adları
        (proje-amacı.md §2.3 — "saves opsiyonel" hariç tutulabilmeli)."""
        excluded = set()
        if self.exclude_logs:
            excluded.add("logs")
        if self.exclude_crash_reports:
            excluded.add("crash-reports")
        if self.exclude_saves:
            excluded.add("saves")
        return excluded

    @classmethod
    def load(cls) -> Settings:
        path = config_dir() / SETTINGS_FILE
        if not path.exists():
            return cls()
        try:
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, ValueError):
            return cls()

    def save(self) -> None:
        path = config_dir() / SETTINGS_FILE
        path.write_text(
            json.dumps(self.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
