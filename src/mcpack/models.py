"""Dahili pack formatının veri modelleri (bkz. proje-amacı.md §4).

Bu modüldeki Pydantic modelleri hem export motoru hem de GUI tarafından
kullanılır; pack'lerin diskte JSON olarak saklanan tek doğruluk kaynağıdır.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import StrEnum

from pydantic import BaseModel, Field


class Loader(StrEnum):
    VANILLA = "vanilla"
    """Mod loader yok — sadece vanilla Minecraft (+ opsiyonel resourcepack/datapack)."""
    FABRIC = "fabric"
    QUILT = "quilt"
    FORGE = "forge"
    NEOFORGE = "neoforge"


class ModSourceType(StrEnum):
    MODRINTH = "modrinth"
    CURSEFORGE = "curseforge"


class EnvRequirement(StrEnum):
    """Modrinth'in env sözleşmesiyle birebir uyumlu (required/optional/unsupported)."""

    REQUIRED = "required"
    OPTIONAL = "optional"
    UNSUPPORTED = "unsupported"


class ModEnv(BaseModel):
    """Bir modun client ve server tarafında nasıl davrandığı.

    Bu alan HER PACK'İN KENDİ JSON'UNDA tutulur (kullanıcı isteği) — server
    pack üretimi bu alana bakarak client-only modları eler.
    """

    client: EnvRequirement = EnvRequirement.REQUIRED
    server: EnvRequirement = EnvRequirement.REQUIRED

    @property
    def is_server_compatible(self) -> bool:
        return self.server != EnvRequirement.UNSUPPORTED

    @property
    def is_client_only(self) -> bool:
        return self.server == EnvRequirement.UNSUPPORTED


class ModHashes(BaseModel):
    sha1: str | None = None
    sha512: str | None = None


class ModEntry(BaseModel):
    source: ModSourceType
    project_id: str
    slug: str | None = None
    """Bilinen client-only listesiyle eşleştirme için (bkz. export/server.py)."""
    name: str | None = None
    """Modun kullanıcı dostu adı (ör. "Just Enough Items (JEI)") — sadece
    UI'de gösterim için, export'ta hâlâ file_name kullanılır."""
    version_id: str
    file_name: str
    file_size: int | None = None
    hashes: ModHashes = Field(default_factory=ModHashes)
    download_url: str
    env: ModEnv = Field(default_factory=ModEnv)
    dependencies: list[str] = Field(default_factory=list)
    """Bağımlı olunan diğer mod'ların project_id listesi."""


class Overrides(BaseModel):
    include: list[str] = Field(default_factory=lambda: ["config"])
    """overrides klasörüne dahil edilecek dizin/dosya adları (config, kubejs, defaultconfigs...)."""


class Pack(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    version: str = "1.0.0"
    author: str = ""
    summary: str = ""
    minecraft: str
    loader: Loader
    loader_version: str = ""
    """Loader.VANILLA için boş bırakılır."""
    mods: list[ModEntry] = Field(default_factory=list)
    overrides: Overrides = Field(default_factory=Overrides)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def find_mod(self, project_id: str) -> ModEntry | None:
        return next((m for m in self.mods if m.project_id == project_id), None)

    @property
    def server_mods(self) -> list[ModEntry]:
        """Server pack üretiminde tutulacak modlar (client-only olmayanlar)."""
        return [m for m in self.mods if m.env.is_server_compatible]

    @property
    def client_only_mods(self) -> list[ModEntry]:
        return [m for m in self.mods if m.env.is_client_only]
