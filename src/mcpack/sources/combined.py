"""Modrinth + CurseForge birleşik arama.

proje-amacı.md §2.1: "Aynı mod her iki sitede de varsa tercihen Modrinth
kullanılsın (ayarlanabilir)". Bu modül iki kaynağı paralel arar ve aynı
modu (normalize edilmiş başlığa göre) tekilleştirir.
"""

from __future__ import annotations

import asyncio
import re

from mcpack.models import Loader
from mcpack.sources.base import SearchResult
from mcpack.sources.curseforge import CurseForgeClient
from mcpack.sources.modrinth import ModrinthClient


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]", "", title.lower())


async def search_all(
    query: str,
    *,
    modrinth: ModrinthClient,
    curseforge: CurseForgeClient | None,
    game_version: str | None = None,
    loader: Loader | None = None,
    limit: int = 20,
    offset: int = 0,
    prefer_modrinth: bool = True,
) -> list[SearchResult]:
    """İki kaynakta paralel arar, çakışan modlarda `prefer_modrinth`'e göre
    Modrinth veya CurseForge sonucunu tutar.

    Bir kaynak hata verirse (örn. CF anahtarı geçersiz/engelli) o kaynak
    sessizce atlanır — ikisi de başarısız olursa hata yükseltilir.
    """
    tasks = [modrinth.search(query, game_version=game_version, loader=loader, limit=limit, offset=offset)]
    if curseforge is not None:
        tasks.append(
            curseforge.search(query, game_version=game_version, loader=loader, limit=limit, offset=offset)
        )

    outcomes = await asyncio.gather(*tasks, return_exceptions=True)

    if all(isinstance(o, Exception) for o in outcomes):
        raise outcomes[0]

    modrinth_results: list[SearchResult] = outcomes[0] if not isinstance(outcomes[0], Exception) else []
    cf_results: list[SearchResult] = (
        outcomes[1] if len(outcomes) > 1 and not isinstance(outcomes[1], Exception) else []
    )

    primary, secondary = (
        (modrinth_results, cf_results) if prefer_modrinth else (cf_results, modrinth_results)
    )

    merged: dict[str, SearchResult] = {}
    order: list[str] = []
    for r in (*primary, *secondary):
        key = _normalize_title(r.title)
        if key not in merged:
            merged[key] = r
            order.append(key)

    return [merged[k] for k in order]
