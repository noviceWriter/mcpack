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
    java_path: str = ""
    """Yerel sunucu başlatmak için kullanılacak java yürütülebilir dosyası
    (bkz. server_runtime.py:find_java) — boşsa PATH'teki `java` kullanılır."""
    web_panel_port: int = 8765
    web_panel_password: str = ""
    """Web paneli (bkz. webpanel/app.py) BOŞSA ağa (0.0.0.0) AÇILMAZ,
    otomatik olarak sadece 127.0.0.1'e düşer — kullanıcı şifre koymadan
    ağdaki herkese açık, korumasız bir panel YAYINLANAMAZ (bkz.
    webpanel/app.py docstring'i)."""
    packs_dir: str = ""
    """Boşsa default_packs_dir() kullanılır."""
    exclude_logs: bool = True
    exclude_crash_reports: bool = True
    exclude_saves: bool = True
    theme: str = "dark"
    """Tek desteklenen tema koyudur."""
    debug_mode: bool = False
    """Açıksa uygulama DEBUG log seviyesiyle başlar (bkz. logging_setup.py)
    — Geliştirici sayfasından çalışma anında da açılıp kapatılabilir."""
    language: str = "tr"
    """Arayüz dili ("tr" veya "en") — bkz. mcpack.i18n. Değişiklik
    sadece uygulama yeniden başlatılınca etkili olur."""

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
            settings = cls.model_validate_json(path.read_text(encoding="utf-8"))
            settings.theme = "dark"
            return settings
        except (json.JSONDecodeError, ValueError) as exc:
            from mcpack.logging_setup import get_logger

            get_logger(__name__).warning("Ayar dosyası bozuk, varsayılanlar kullanılıyor: %s (%s)", path, exc)
            return cls()

    def backup_file(self) -> Path | None:
        """Mevcut settings.json'u settings.backup-<zaman>.json olarak kopyalar
        (ayarlar sıfırlanmadan önce — işlem geri alınabilsin diye)."""
        import shutil
        from datetime import datetime

        path = config_dir() / SETTINGS_FILE
        if not path.exists():
            return None
        backup = config_dir() / f"settings.backup-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
        shutil.copy2(path, backup)
        return backup

    @classmethod
    def defaults(cls, *, keep_secrets_from: Settings | None = None) -> Settings:
        """Varsayılan ayarlar. keep_secrets_from verilirse CurseForge API
        anahtarı ve web paneli şifresi oradan korunur."""
        fresh = cls()
        if keep_secrets_from is not None:
            fresh.curseforge_api_key = keep_secrets_from.curseforge_api_key
            fresh.web_panel_password = keep_secrets_from.web_panel_password
        return fresh

    def save(self) -> None:
        path = config_dir() / SETTINGS_FILE
        path.write_text(
            json.dumps(self.model_dump(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
