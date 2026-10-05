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
    WURST = "wurst"
    """Wurst Client — CurseForge/Modrinth'ten platform kurallarına aykırı
    bulunduğu için yasaklı, kendi API'sinden indirilir (bkz.
    sources/cheat_mods.py). Normal ModSource arayüzünü (search/get_versions)
    UYGULAMAZ — sadece PackManager.add_cheat_mod ile doğrudan eklenir."""
    METEOR = "meteor"
    """Meteor Client — aynı sebeple (bkz. WURST) kendi API'sinden indirilir."""


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


class DownloadableFile(BaseModel):
    """Modrinth/CurseForge'tan indirilecek bir dosyanın ortak alanları.

    Mod, shader, resourcepack ve datapack indirmelerinin hepsi bu şekle sahiptir
    — export sırasında tek bir indirme fonksiyonuyla (bkz.
    export/base.py:ensure_mods_downloaded) işlenebilirler."""

    source: ModSourceType
    project_id: str
    slug: str | None = None
    """Bilinen client-only listesiyle eşleştirme için (bkz. export/server.py)."""
    name: str | None = None
    """Kullanıcı dostu ad (ör. "Just Enough Items (JEI)") — sadece UI'de
    gösterim için, export'ta hâlâ file_name kullanılır."""
    version_id: str
    file_name: str
    file_size: int | None = None
    hashes: ModHashes = Field(default_factory=ModHashes)
    download_url: str


class ModEntry(DownloadableFile):
    env: ModEnv = Field(default_factory=ModEnv)
    dependencies: list[str] = Field(default_factory=list)
    """Bağımlı olunan diğer mod'ların project_id listesi."""


class Overrides(BaseModel):
    include: list[str] = Field(default_factory=lambda: ["config"])
    """overrides klasörüne dahil edilecek dizin/dosya adları (config, kubejs, defaultconfigs...)."""


class ContentKind(StrEnum):
    """Mod dışı ama pack'e eklenebilen içerik türleri.

    SHADERPACK/RESOURCEPACK/DATAPACK Modrinth/CurseForge'tan aranıp indirilir
    (bkz. ContentDownload, mod eklemeyle birebir aynı akış — kullanıcı isteği).
    WORLD indirilebilir bir kaynak değildir (kullanıcının kendi dünyası),
    diskten seçilip pack'in kendi deposuna kopyalanır (bkz. ContentEntry,
    PackManager.add_content)."""

    SHADERPACK = "shaderpack"
    RESOURCEPACK = "resourcepack"
    DATAPACK = "datapack"
    WORLD = "world"


class ContentDownload(DownloadableFile):
    kind: ContentKind


class ContentEntry(BaseModel):
    kind: ContentKind
    name: str
    """Kullanıcıya gösterilen ad — orijinal dosya/klasör adı (uzantısıyla)."""
    stored_path: str
    """PackManager.content_root(pack)'e göre saklandığı göreli yol."""
    is_dir: bool = False


class ServerRuntimeConfig(BaseModel):
    """Yerel sunucu çalıştırma ayarları (bkz. server_runtime.py,
    gui/server_section.py). Port/zorluk/motd gibi Minecraft'ın kendi
    kavramları BURADA TEKRARLANMAZ — tek doğruluk kaynağı server.properties
    dosyasının kendisidir (bkz. server_properties.py); burada sadece
    server.properties'te karşılığı olmayan, mcpack'e özgü ayarlar tutulur."""

    memory_mb: int = 2048
    selected_world: str | None = None
    """pack.content'teki (ContentKind.WORLD) bir ContentEntry.name — sunucu
    hazırlanırken server_root/world/ altına kopyalanacak dünya."""
    eula_accepted: bool = False
    """SADECE kullanıcı GUI'de EULA onay penceresinde açıkça kabul edince
    True olur — bu alan True olmadan eula.txt asla yazılmaz."""
    use_optimized_flags: bool = False
    """Açıksa başlatma komutuna topluluğun bilinen "Aikar's flags" G1GC
    JVM bayrakları eklenir (bkz. server_runtime.build_launch_command) —
    Minecraft sunucusunun GC duraklamalarını azaltmak için, yıllardır
    bilinen/belgeli bir bayrak seti, bu projeye özgü değil."""


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
    content_downloads: list[ContentDownload] = Field(default_factory=list)
    """Modrinth/CurseForge'tan aranıp eklenmiş shader/resourcepack/datapack."""
    content: list[ContentEntry] = Field(default_factory=list)
    """Yerelden yüklenmiş dünya(lar) (bkz. ContentKind.WORLD)."""
    server: ServerRuntimeConfig = Field(default_factory=ServerRuntimeConfig)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def touch(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    def find_mod(self, project_id: str) -> ModEntry | None:
        return next((m for m in self.mods if m.project_id == project_id), None)

    def content_of(self, kind: ContentKind) -> list[ContentEntry]:
        return [c for c in self.content if c.kind == kind]

    def content_downloads_of(self, kind: ContentKind) -> list[ContentDownload]:
        return [c for c in self.content_downloads if c.kind == kind]

    def find_content_download(self, kind: ContentKind, project_id: str) -> ContentDownload | None:
        return next(
            (c for c in self.content_downloads if c.kind == kind and c.project_id == project_id), None
        )

    @property
    def server_mods(self) -> list[ModEntry]:
        """Server pack üretiminde tutulacak modlar (client-only olmayanlar)."""
        return [m for m in self.mods if m.env.is_server_compatible]

    @property
    def client_only_mods(self) -> list[ModEntry]:
        return [m for m in self.mods if m.env.is_client_only]
