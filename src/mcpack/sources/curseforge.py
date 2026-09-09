"""CurseForge API v1 client.

Base: https://api.curseforge.com
Dokümantasyon: https://docs.curseforge.com/rest-api/
- `x-api-key` header ZORUNLU (kullanıcı ayarlarından okunur, koda gömülmez).
- Minecraft gameId = 432, mod classId = 6.
- CurseForge, Modrinth'in aksine client/server "env" bilgisini standart
  olarak vermez; bu yüzden server pack filtrelemesinde CF modları için
  data/client_only_mods.json'daki bilinen liste devreye girer.
"""

from __future__ import annotations

import httpx

from mcpack.downloader import make_client
from mcpack.models import Loader, ModSourceType
from mcpack.sources.base import (
    ModDetail,
    ModSource,
    ModVersion,
    SearchResult,
    VersionDependency,
    VersionFile,
)

BASE_URL = "https://api.curseforge.com"
MINECRAFT_GAME_ID = 432
MOD_CLASS_ID = 6

_LOADER_TO_CF = {
    Loader.FORGE: 1,
    Loader.FABRIC: 4,
    Loader.QUILT: 5,
    Loader.NEOFORGE: 6,
}

_RELATION_TYPE_MAP = {
    1: "embedded",
    2: "optional",
    3: "required",
    4: "tool",
    5: "incompatible",
    6: "embedded",
}


class CurseForgeConfigError(Exception):
    """API key ayarlanmamışsa fırlatılır."""


class CurseForgeClient(ModSource):
    name = ModSourceType.CURSEFORGE

    def __init__(self, api_key: str, client: httpx.AsyncClient | None = None) -> None:
        if not api_key:
            raise CurseForgeConfigError(
                "CurseForge API key ayarlanmamış. Ayarlar'dan girmelisiniz."
            )
        self._client = client or make_client(extra_headers={"x-api-key": api_key})
        self._owns_client = client is None

    async def aclose(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str, params: dict | None = None) -> httpx.Response:
        response = await self._client.get(f"{BASE_URL}{path}", params=params)
        response.raise_for_status()
        return response

    async def search(
        self,
        query: str,
        *,
        game_version: str | None = None,
        loader: Loader | None = None,
        limit: int = 20,
    ) -> list[SearchResult]:
        params: dict[str, str | int] = {
            "gameId": MINECRAFT_GAME_ID,
            "classId": MOD_CLASS_ID,
            "searchFilter": query,
            "pageSize": limit,
        }
        if game_version:
            params["gameVersion"] = game_version
        if loader and loader in _LOADER_TO_CF:
            params["modLoaderType"] = _LOADER_TO_CF[loader]

        response = await self._get("/v1/mods/search", params=params)
        data = response.json().get("data", [])

        return [
            SearchResult(
                source=self.name,
                project_id=str(mod["id"]),
                slug=mod.get("slug", ""),
                title=mod["name"],
                description=mod.get("summary", ""),
                icon_url=(mod.get("logo") or {}).get("thumbnailUrl"),
                downloads=int(mod.get("downloadCount", 0)),
                categories=[c.get("name", "") for c in mod.get("categories", [])],
            )
            for mod in data
        ]

    async def get_project(self, project_id: str) -> ModDetail:
        response = await self._get(f"/v1/mods/{project_id}")
        mod = response.json()["data"]
        return ModDetail(
            source=self.name,
            project_id=str(mod["id"]),
            slug=mod.get("slug", ""),
            title=mod["name"],
            description=mod.get("summary", ""),
            categories=[c.get("name", "") for c in mod.get("categories", [])],
        )

    async def get_versions(
        self,
        project_id: str,
        *,
        game_version: str | None = None,
        loader: Loader | None = None,
    ) -> list[ModVersion]:
        params: dict[str, str | int] = {}
        if game_version:
            params["gameVersion"] = game_version
        if loader and loader in _LOADER_TO_CF:
            params["modLoaderType"] = _LOADER_TO_CF[loader]

        response = await self._get(f"/v1/mods/{project_id}/files", params=params)
        data = response.json().get("data", [])

        versions = []
        for f in data:
            sha1 = next(
                (h["value"] for h in f.get("hashes", []) if h.get("algo") == 1), None
            )
            download_url = f.get("downloadUrl")
            if not download_url:
                # Bazı modlarda yayıncı "3rd party download" iznini kapatmıştır;
                # bu durumda downloadUrl None gelir ve indirme mümkün olmaz.
                continue

            deps = [
                VersionDependency(
                    project_id=str(d["modId"]),
                    dependency_type=_RELATION_TYPE_MAP.get(d.get("relationType", 3), "required"),
                )
                for d in f.get("dependencies", [])
            ]

            versions.append(
                ModVersion(
                    source=self.name,
                    version_id=str(f["id"]),
                    project_id=str(f["modId"]),
                    name=f.get("displayName", f.get("fileName", "")),
                    game_versions=[gv for gv in f.get("gameVersions", [])],
                    loaders=[loader.value] if loader else [],
                    dependencies=deps,
                    files=[
                        VersionFile(
                            file_name=f["fileName"],
                            url=download_url,
                            sha1=sha1,
                            size=f.get("fileLength"),
                            primary=True,
                        )
                    ],
                )
            )
        return versions

    async def get_download_url(self, project_id: str, file_id: str) -> str:
        """downloadUrl None gelen dosyalar için ayrı endpoint (bazı durumlarda hâlâ boş dönebilir)."""
        response = await self._get(f"/v1/mods/{project_id}/files/{file_id}/download-url")
        return response.json()["data"]
