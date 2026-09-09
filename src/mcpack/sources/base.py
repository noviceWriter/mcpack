"""Modrinth ve CurseForge client'larının uyduğu ortak arayüz.

İleride başka bir mod kaynağı eklenmek istenirse sadece bu ABC'den
türeyen yeni bir sınıf yazmak yeterli olur; packs/export katmanları
kaynağın somut tipini bilmek zorunda kalmaz.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from pydantic import BaseModel, Field

from mcpack.models import EnvRequirement, Loader, ModSourceType


class SearchResult(BaseModel):
    source: ModSourceType
    project_id: str
    slug: str
    title: str
    description: str
    icon_url: str | None = None
    downloads: int = 0
    categories: list[str] = Field(default_factory=list)


class VersionFile(BaseModel):
    file_name: str
    url: str
    sha1: str | None = None
    sha512: str | None = None
    size: int | None = None
    primary: bool = True


class VersionDependency(BaseModel):
    project_id: str | None = None
    version_id: str | None = None
    dependency_type: str = "required"
    """required / optional / incompatible / embedded"""


class ModVersion(BaseModel):
    source: ModSourceType
    version_id: str
    project_id: str
    name: str
    game_versions: list[str] = Field(default_factory=list)
    loaders: list[str] = Field(default_factory=list)
    dependencies: list[VersionDependency] = Field(default_factory=list)
    files: list[VersionFile] = Field(default_factory=list)

    @property
    def primary_file(self) -> VersionFile | None:
        return next((f for f in self.files if f.primary), self.files[0] if self.files else None)


class ModDetail(BaseModel):
    source: ModSourceType
    project_id: str
    slug: str
    title: str
    description: str
    client_side: EnvRequirement = EnvRequirement.REQUIRED
    server_side: EnvRequirement = EnvRequirement.REQUIRED
    categories: list[str] = Field(default_factory=list)


class ModSource(ABC):
    """Bir mod kaynağının (Modrinth, CurseForge, ...) uyması gereken arayüz."""

    name: ModSourceType

    @abstractmethod
    async def search(
        self,
        query: str,
        *,
        game_version: str | None = None,
        loader: Loader | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        ...

    @abstractmethod
    async def get_project(self, project_id: str) -> ModDetail:
        ...

    @abstractmethod
    async def get_versions(
        self,
        project_id: str,
        *,
        game_version: str | None = None,
        loader: Loader | None = None,
    ) -> list[ModVersion]:
        ...
