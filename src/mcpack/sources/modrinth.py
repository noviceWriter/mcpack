"""Modrinth API v2 client.

Base: https://api.modrinth.com/v2
Dokümantasyon: https://docs.modrinth.com/api/
- Çoğu okuma endpoint'i (search, project, version) API key istemez.
- User-Agent zorunlu ve tanımlayıcı olmalı (bkz. downloader.USER_AGENT).
"""

from __future__ import annotations

import json

import httpx

from mcpack.downloader import RateLimiter, make_client
from mcpack.models import ContentKind, EnvRequirement, Loader, ModSourceType
from mcpack.sources.base import (
    ModDetail,
    ModSource,
    ModVersion,
    SearchResult,
    SourceAPIError,
    VersionDependency,
    VersionFile,
)

BASE_URL = "https://api.modrinth.com/v2"

_PROJECT_TYPE = {
    ContentKind.SHADERPACK: "shader",
    ContentKind.RESOURCEPACK: "resourcepack",
    ContentKind.DATAPACK: "datapack",
}
"""Modrinth'in search facet'lerindeki project_type değerleri (bkz.
https://docs.modrinth.com/api/operations/searchprojects/)."""

_DEPENDENCY_TYPE_MAP = {
    "required": "required",
    "optional": "optional",
    "incompatible": "incompatible",
    "embedded": "embedded",
}


class ModrinthClient(ModSource):
    name = ModSourceType.MODRINTH

    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self._client = client or make_client()
        self._owns_client = client is None
        self._rate_limiter = RateLimiter()

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        try:
            response = await self._client.get(f"{BASE_URL}{path}", params=params)
            await self._rate_limiter.observe(response)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 404:
                raise SourceAPIError(f"Modrinth'te bulunamadı: {path}") from exc
            if status == 429:
                raise SourceAPIError("Modrinth rate limit'ine takıldı, birazdan tekrar deneyin.") from exc
            raise SourceAPIError(f"Modrinth API hatası ({status}): {path}") from exc
        except httpx.RequestError as exc:
            raise SourceAPIError(f"Modrinth API'sine ulaşılamadı (ağ hatası): {exc}") from exc
        return response

    async def search(
        self,
        query: str,
        *,
        game_version: str | None = None,
        loader: Loader | None = None,
        content_kind: ContentKind | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[SearchResult]:
        if content_kind is not None and content_kind not in _PROJECT_TYPE:
            # Modrinth'te karşılığı olmayan içerik türü (ör. ContentKind.WORLD
            # — Modrinth'te "dünya/harita" diye bir proje türü yok, sadece
            # CurseForge'ta var). Hata fırlatmak yerine sessizce boş dönülür.
            return []
        project_type = _PROJECT_TYPE.get(content_kind, "mod") if content_kind else "mod"
        facets: list[list[str]] = [[f"project_type:{project_type}"]]
        if game_version:
            facets.append([f"versions:{game_version}"])
        # Loader facet'i (fabric/forge/...) sadece mod kategorisi olarak
        # anlamlı — shader/resourcepack/datapack'te loader kavramı yok.
        if project_type == "mod" and loader and loader != Loader.VANILLA:
            facets.append([f"categories:{loader.value}"])

        params = {
            "query": query,
            "limit": limit,
            "offset": offset,
            "facets": json.dumps(facets),
        }
        response = await self._get("/search", params=params)
        data = response.json()

        return [
            SearchResult(
                source=self.name,
                project_id=hit["project_id"],
                slug=hit["slug"],
                title=hit["title"],
                description=hit.get("description", ""),
                icon_url=hit.get("icon_url"),
                downloads=hit.get("downloads", 0),
                categories=hit.get("categories", []),
            )
            for hit in data.get("hits", [])
        ]

    async def get_project(self, project_id: str) -> ModDetail:
        response = await self._get(f"/project/{project_id}")
        data = response.json()
        return ModDetail(
            source=self.name,
            project_id=data["id"],
            slug=data["slug"],
            title=data["title"],
            description=data.get("description", ""),
            client_side=EnvRequirement(data.get("client_side", "required")),
            server_side=EnvRequirement(data.get("server_side", "required")),
            categories=data.get("categories", []),
        )

    async def get_versions(
        self,
        project_id: str,
        *,
        game_version: str | None = None,
        loader: Loader | None = None,
    ) -> list[ModVersion]:
        params: dict[str, str] = {}
        if game_version:
            params["game_versions"] = json.dumps([game_version])
        if loader and loader != Loader.VANILLA:
            params["loaders"] = json.dumps([loader.value])

        response = await self._get(f"/project/{project_id}/version", params=params)
        data = response.json()

        versions = []
        for v in data:
            files = [
                VersionFile(
                    file_name=f["filename"],
                    url=f["url"],
                    sha1=f.get("hashes", {}).get("sha1"),
                    sha512=f.get("hashes", {}).get("sha512"),
                    size=f.get("size"),
                    primary=f.get("primary", False),
                )
                for f in v.get("files", [])
            ]
            deps = [
                VersionDependency(
                    project_id=d.get("project_id"),
                    version_id=d.get("version_id"),
                    dependency_type=_DEPENDENCY_TYPE_MAP.get(
                        d.get("dependency_type", "required"), "required"
                    ),
                )
                for d in v.get("dependencies", [])
            ]
            versions.append(
                ModVersion(
                    source=self.name,
                    version_id=v["id"],
                    project_id=v["project_id"],
                    name=v.get("name", v.get("version_number", "")),
                    game_versions=v.get("game_versions", []),
                    loaders=v.get("loaders", []),
                    dependencies=deps,
                    files=files,
                )
            )
        return versions
