"""Pack'teki mod ve indirilebilir içerik (shader/resourcepack/datapack)
için güncelleme kontrolü.

- Modrinth: dosya SHA-1'i bilinen tüm modlar TEK istekte sorgulanır
  (ModrinthClient.latest_versions_for_hashes); bilinmeyenler mod başına.
- CurseForge: mod başına (eşzamanlılık sınırlı); en yeni dosya, dosya
  kimliği (zamanla artar) en büyük olandır.
- Wurst/Meteor ve yerel dünyalar kontrol edilmez (kendi akışları var).

"Güncelleme" = pack'in Minecraft sürümü + loader'ı ile uyumlu en yeni
sürümün, pack'teki sürümden farklı olması.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from mcpack.logging_setup import get_logger
from mcpack.models import ContentKind, DownloadableFile, ModSourceType, Pack
from mcpack.sources.base import ModSource, ModVersion

log = get_logger(__name__)

CONCURRENCY = 6


@dataclass
class ModUpdate:
    project_id: str
    name: str
    source: ModSourceType
    kind: ContentKind | None
    """None = mod; aksi halde content_downloads türü."""
    current_version_id: str
    current_file: str
    latest: ModVersion

    @property
    def new_file(self) -> str:
        file = self.latest.primary_file
        return file.file_name if file else "?"


def _latest(versions: list[ModVersion], source: ModSourceType) -> ModVersion | None:
    if not versions:
        return None
    if source == ModSourceType.CURSEFORGE:
        def key(v: ModVersion) -> int:
            try:
                return int(v.version_id)
            except ValueError:
                return -1

        return max(versions, key=key)
    return versions[0]  # Modrinth en yeniden eskiye sıralı döndürür


def _entries(pack: Pack) -> list[tuple[DownloadableFile, ContentKind | None]]:
    items: list[tuple[DownloadableFile, ContentKind | None]] = [
        (m, None) for m in pack.mods if m.source in (ModSourceType.MODRINTH, ModSourceType.CURSEFORGE)
    ]
    items += [(c, c.kind) for c in pack.content_downloads if c.source in (ModSourceType.MODRINTH, ModSourceType.CURSEFORGE)]
    return items


async def check_updates(
    pack: Pack,
    *,
    modrinth: ModSource,
    curseforge: ModSource | None,
    progress_cb=None,
) -> tuple[list[ModUpdate], list[str]]:
    """(güncellemeler, kontrol edilemeyenlerin "ad: neden" listesi)."""
    entries = _entries(pack)
    updates: list[ModUpdate] = []
    errors: list[str] = []
    done = 0
    total = len(entries)

    def report() -> None:
        if progress_cb:
            progress_cb(done, total)

    def consider(entry: DownloadableFile, kind: ContentKind | None, latest: ModVersion | None) -> None:
        if latest is None or latest.version_id == entry.version_id:
            return
        updates.append(ModUpdate(
            project_id=entry.project_id, name=entry.name or entry.file_name, source=entry.source, kind=kind,
            current_version_id=entry.version_id, current_file=entry.file_name, latest=latest,
        ))

    # 1) Modrinth toplu sorgu (sadece modlar: loader filtresi modlar için anlamlı)
    bulk: dict[str, ModVersion] = {}
    bulk_candidates = [
        e for e, k in entries if k is None and e.source == ModSourceType.MODRINTH and e.hashes.sha1
    ]
    if bulk_candidates and hasattr(modrinth, "latest_versions_for_hashes"):
        try:
            bulk = await modrinth.latest_versions_for_hashes(
                [e.hashes.sha1 for e in bulk_candidates], game_version=pack.minecraft, loader=pack.loader
            )
        except Exception as exc:  # noqa: BLE001 - toplu sorgu başarısızsa tek tek denenir
            log.warning("Modrinth toplu güncelleme sorgusu başarısız, tek tek denenecek: %s", exc)

    remaining: list[tuple[DownloadableFile, ContentKind | None]] = []
    for entry, kind in entries:
        hit = bulk.get((entry.hashes.sha1 or "").lower()) if kind is None and entry.source == ModSourceType.MODRINTH else None
        if hit is not None and hit.project_id == entry.project_id:
            consider(entry, kind, hit)
            done += 1
        else:
            remaining.append((entry, kind))
    report()

    # 2) Kalanlar: mod başına, sınırlı eşzamanlılık
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def one(entry: DownloadableFile, kind: ContentKind | None) -> None:
        nonlocal done
        source = modrinth if entry.source == ModSourceType.MODRINTH else curseforge
        label = entry.name or entry.file_name
        try:
            if source is None:
                errors.append(f"{label}: CurseForge API anahtarı yok")
                return
            async with semaphore:
                versions = await source.get_versions(
                    entry.project_id, game_version=pack.minecraft, loader=pack.loader if kind is None else None
                )
            consider(entry, kind, _latest(versions, entry.source))
        except Exception as exc:  # noqa: BLE001 - bir modun hatası tüm kontrolü durdurmasın
            errors.append(f"{label}: {exc}")
        finally:
            done += 1
            report()

    await asyncio.gather(*(one(e, k) for e, k in remaining))
    updates.sort(key=lambda u: u.name.lower())
    log.info(
        "Güncelleme kontrolü %s: %d öğe, %d güncelleme, %d hata (toplu eşleşme: %d)",
        pack.name, total, len(updates), len(errors), len(bulk),
    )
    return updates, errors


@dataclass
class ApplyResult:
    applied: list[str]
    added_dependencies: list[str]
    unresolved_dependencies: list[str]
    failed: list[str]


async def apply_updates(
    manager,
    pack: Pack,
    updates: list[ModUpdate],
    *,
    modrinth: ModSource,
    curseforge: ModSource | None,
    progress_cb=None,
) -> ApplyResult:
    """Seçilen güncellemeleri uygular. Yeni sürüm pack'te olmayan YENİ bir
    zorunlu bağımlılık getirdiyse o da (mod eklemedeki aynı çözümleyiciyle)
    eklenir; çözülemeyenler raporlanır."""
    result = ApplyResult([], [], [], [])
    for i, update in enumerate(updates, start=1):
        try:
            if update.kind is None:
                manager.update_mod(pack, update.latest)
                source = modrinth if update.source == ModSourceType.MODRINTH else curseforge
                if source is not None:
                    deps, unresolved = await manager.resolve_dependencies(pack, source, update.latest)
                    for dep in deps:
                        detail = None
                        try:
                            detail = await source.get_project(dep.project_id)
                        except Exception:  # noqa: BLE001 - adsız da eklenebilir
                            pass
                        manager.add_mod(pack, dep, detail)
                        result.added_dependencies.append(detail.title if detail else dep.project_id)
                    result.unresolved_dependencies += unresolved
            else:
                manager.update_content_download(pack, update.kind, update.latest)
            result.applied.append(update.name)
        except Exception as exc:  # noqa: BLE001 - bir güncellemenin hatası diğerlerini durdurmasın
            log.warning("Güncelleme uygulanamadı %s: %s", update.name, exc)
            result.failed.append(f"{update.name}: {exc}")
        if progress_cb:
            progress_cb(i, len(updates))
    return result
