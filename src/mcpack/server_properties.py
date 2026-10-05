"""server.properties okuma/yazma + en sık değiştirilen alanlar için küçük
bir "bilinen alanlar" listesi (bkz. gui/server_section.py'nin bunu bir
forma çevirmesi).

Yorumları/sırayı koruma gibi bir hedefi YOK — basit bir key=value
parse/yaz. Minecraft sunucusu dosya eksikse zaten kendi varsayılanlarıyla
yeniden üretiyor, bu yüzden tam biçim-koruma gereksiz bir karmaşıklık
(bilinçli basitleştirme)."""

from __future__ import annotations

from pathlib import Path
from typing import Literal

PropertyType = Literal["str", "int", "bool", "choice"]


class KnownProperty:
    def __init__(
        self,
        key: str,
        label: str,
        type: PropertyType,
        default: str,
        choices: list[str] | None = None,
    ) -> None:
        self.key = key
        self.label = label
        self.type = type
        self.default = default
        self.choices = choices or []


KNOWN_PROPERTIES: list[KnownProperty] = [
    KnownProperty("motd", "Sunucu Mesajı (MOTD)", "str", "A Minecraft Server"),
    KnownProperty("difficulty", "Zorluk", "choice", "easy", ["peaceful", "easy", "normal", "hard"]),
    KnownProperty(
        "gamemode", "Oyun Modu", "choice", "survival", ["survival", "creative", "adventure", "spectator"]
    ),
    KnownProperty("max-players", "Maks. Oyuncu", "int", "20"),
    KnownProperty("server-port", "Port", "int", "25565"),
    KnownProperty("pvp", "PVP", "bool", "true"),
    KnownProperty("online-mode", "Online Mode (Mojang hesap doğrulama)", "bool", "true"),
    KnownProperty("white-list", "Beyaz Liste", "bool", "false"),
    KnownProperty("level-seed", "Dünya Tohumu (seed, sadece yeni dünyada etkili)", "str", ""),
    KnownProperty("view-distance", "Görüş Mesafesi (chunk)", "int", "10"),
]

KNOWN_KEYS = {p.key for p in KNOWN_PROPERTIES}


def read_properties(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()
    return values


def write_properties(path: Path, values: dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{key}={value}" for key, value in values.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def merged_with_defaults(values: dict[str, str]) -> dict[str, str]:
    """Bilinen alanlardan values'ta olmayanları varsayılanla doldurur —
    GUI formunu ilk kez dolu göstermek için (var olan server.properties
    değerlerini ASLA ezmez, sadece eksikleri tamamlar)."""
    merged = dict(values)
    for prop in KNOWN_PROPERTIES:
        merged.setdefault(prop.key, prop.default)
    return merged
