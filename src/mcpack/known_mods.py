"""Bilinen client-only mod listesini (data/client_only_mods.json) yükler.

Hem packs/manager.py (mod eklenirken CurseForge gibi env bilgisi
vermeyen kaynaklar için ilk tahmini env atarken) hem export/server.py
(server pack filtrelemesi için) kullanır. Döngüsel import'u önlemek için
(export.base -> packs.storage, packs -> export olursa çakışır) bağımsız,
üst seviye bir modülde tutulur.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


def _data_dir() -> Path:
    """PyInstaller ile paketlenmişse sys._MEIPASS altındaki data/ (bkz.
    scripts/build.py --add-data), aksi halde kaynak kod deposundaki data/."""
    frozen_base = getattr(sys, "_MEIPASS", None)
    if frozen_base:
        return Path(frozen_base) / "data"
    return Path(__file__).resolve().parents[2] / "data"


def load_known_client_only_slugs() -> set[str]:
    path = _data_dir() / "client_only_mods.json"
    if not path.exists():
        return set()
    data = json.loads(path.read_text(encoding="utf-8"))
    return {s.lower() for s in data.get("client_only_slugs", [])}
