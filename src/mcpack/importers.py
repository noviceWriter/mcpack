"""Hazır modpack dosyalarını içe aktarma: Modrinth `.mrpack` ve CurseForge
modpack `.zip` (manifest.json).

Önceden program sadece dışa aktarabiliyordu; başkasının paylaştığı bir
paketi açıp düzenlemenin yolu yoktu.

Akış (her iki format):
1. Manifest okunur → Minecraft sürümü, loader, loader sürümü, ad.
2. Dosyalar kaynaklarında tanınır:
   - .mrpack: tüm dosyalar SHA-1 ile Modrinth'e TEK istekte sorulur
     (/version_files), proje ayrıntıları TEK istekte alınır (/projects).
     Tanınmayanlar (GitHub vb.) hash'leriyle "Doğrudan URL" kaynağı olur.
     Pack'teki istemci/sunucu (env) bilgisi korunur.
   - CurseForge: her projectID/fileID CurseForge API'sinden çözülür
     (API anahtarı gerekir); proje sınıfına göre mod / kaynak paketi /
     shader / datapack ayrılır.
3. `overrides/` (ve .mrpack'te `client-overrides/`) güvenli şekilde
   (path traversal korumasıyla) pack'in kendi `overrides` klasörüne
   açılır; içindeki dünyalar (saves/<ad>/level.dat) Dünyalar'a, Modrinth'te
   tanınan shader/kaynak paketleri kendi bölümlerine taşınır. Kalan üst
   seviye klasörler (config, kubejs, …) pack.overrides.include'a yazılır.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import zipfile
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath

from mcpack.logging_setup import get_logger
from mcpack.models import (
    ContentDownload,
    ContentKind,
    EnvRequirement,
    Loader,
    ModEntry,
    ModEnv,
    ModHashes,
    ModSourceType,
    Pack,
)
from mcpack.packs.storage import PathTraversalError, safe_join
from mcpack.sources.base import ModDetail, ModVersion

log = get_logger(__name__)

MRPACK_INDEX = "modrinth.index.json"
CF_MANIFEST = "manifest.json"
OVERRIDES_DIR = "overrides"
MAX_UNCOMPRESSED_BYTES = 8 * 1024**3
"""Zip bombasına karşı üst sınır (açılmış toplam boyut)."""

_MRPACK_LOADERS = {
    "fabric-loader": Loader.FABRIC,
    "quilt-loader": Loader.QUILT,
    "forge": Loader.FORGE,
    "neoforge": Loader.NEOFORGE,
}
_CF_LOADER_PREFIX = {"fabric": Loader.FABRIC, "quilt": Loader.QUILT, "forge": Loader.FORGE, "neoforge": Loader.NEOFORGE}
_DIR_KIND = {"shaderpacks": ContentKind.SHADERPACK, "resourcepacks": ContentKind.RESOURCEPACK}
_CF_CLASS_KIND = {12: ContentKind.RESOURCEPACK, 6552: ContentKind.SHADERPACK, 6945: ContentKind.DATAPACK}


class ModpackImportError(Exception):
    """Dosya geçerli bir modpack değilse ya da içe aktarılamıyorsa."""


@dataclass
class ImportResult:
    pack: Pack
    format: str
    mods: int = 0
    content: int = 0
    worlds: int = 0
    url_sourced: list[str] = field(default_factory=list)
    """Modrinth/CurseForge'ta tanınmayıp doğrudan URL olarak eklenenler."""
    skipped: list[str] = field(default_factory=list)
    """Hiç eklenemeyenler ("ad: neden")."""
    overrides_dir: Path | None = None


def detect_format(path: Path) -> str | None:
    try:
        with zipfile.ZipFile(path) as zf:
            names = set(zf.namelist())
    except (zipfile.BadZipFile, OSError):
        return None
    if MRPACK_INDEX in names:
        return "mrpack"
    if CF_MANIFEST in names:
        return "curseforge"
    return None


def _env(value: str | None, default: EnvRequirement) -> EnvRequirement:
    try:
        return EnvRequirement(value) if value else default
    except ValueError:
        return default


def _safe_extract_prefix(zf: zipfile.ZipFile, prefixes: list[str], dest: Path) -> int:
    """Zip içindeki prefixes altındaki dosyaları dest'e (prefix'siz) açar.
    `..`/mutlak yol içeren girdiler reddedilir; toplam boyut sınırlanır."""
    total = 0
    count = 0
    for info in zf.infolist():
        name = info.filename
        prefix = next((p for p in prefixes if name.startswith(p + "/")), None)
        if prefix is None or info.is_dir():
            continue
        rel = name[len(prefix) + 1 :]
        if not rel:
            continue
        total += info.file_size
        if total > MAX_UNCOMPRESSED_BYTES:
            raise ModpackImportError("Arşiv açıldığında çok büyük (olası zip bombası) — içe aktarma durduruldu.")
        try:
            target = safe_join(dest, *PurePosixPath(rel).parts)
        except PathTraversalError:
            log.warning("Güvensiz yol atlandı: %s", name)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        with zf.open(info) as src, target.open("wb") as out:
            shutil.copyfileobj(src, out)
        count += 1
    return count


def _sha1(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


async def _absorb_overrides(manager, pack: Pack, overrides: Path, result: ImportResult, modrinth) -> None:
    """overrides içindeki dünyaları ve (Modrinth'te tanınan) shader/kaynak
    paketlerini pack'in kendi bölümlerine taşır; geriye kalanları
    pack.overrides.include'a yazar."""
    saves = overrides / "saves"
    if saves.is_dir():
        for world in sorted(p for p in saves.iterdir() if p.is_dir()):
            try:
                manager.add_content(pack, ContentKind.WORLD, world)
                result.worlds += 1
            except (ValueError, OSError) as exc:
                result.skipped.append(f"{world.name}: {exc}")
        shutil.rmtree(saves, ignore_errors=True)

    loose: list[tuple[Path, ContentKind]] = []
    for dirname, kind in _DIR_KIND.items():
        folder = overrides / dirname
        if folder.is_dir():
            loose += [(p, kind) for p in folder.iterdir() if p.is_file()]
    if loose and modrinth is not None:
        by_hash = {_sha1(p): (p, k) for p, k in loose}
        try:
            found = await modrinth.versions_for_hashes(list(by_hash))
            details = await modrinth.get_projects([v.project_id for v in found.values()]) if found else {}
        except Exception as exc:  # noqa: BLE001 - tanınamazsa overrides olarak kalır
            log.warning("overrides içeriği Modrinth'te sorgulanamadı: %s", exc)
            found, details = {}, {}
        for sha1, version in found.items():
            path, kind = by_hash[sha1]
            file = next((f for f in version.files if (f.sha1 or "").lower() == sha1), version.primary_file)
            if file is None:
                continue
            detail = details.get(version.project_id)
            pack.content_downloads = [c for c in pack.content_downloads if not (c.kind == kind and c.project_id == version.project_id)]
            pack.content_downloads.append(ContentDownload(
                kind=kind, source=ModSourceType.MODRINTH, project_id=version.project_id,
                slug=detail.slug if detail else None, name=detail.title if detail else None,
                version_id=version.version_id, file_name=file.file_name, file_size=file.size,
                hashes=ModHashes(sha1=file.sha1, sha512=file.sha512), download_url=file.url,
            ))
            path.unlink(missing_ok=True)
            result.content += 1
    for dirname in _DIR_KIND:
        folder = overrides / dirname
        if folder.is_dir() and not any(folder.iterdir()):
            folder.rmdir()

    remaining = sorted(p.name for p in overrides.iterdir()) if overrides.exists() else []
    pack.overrides.include = remaining
    result.overrides_dir = overrides if remaining else None
    if not remaining:
        shutil.rmtree(overrides, ignore_errors=True)


async def import_mrpack(manager, path: Path, *, modrinth, name: str | None = None, progress_cb=None) -> ImportResult:
    with zipfile.ZipFile(path) as zf:
        try:
            index = json.loads(zf.read(MRPACK_INDEX).decode("utf-8"))
        except (KeyError, ValueError) as exc:
            raise ModpackImportError(f"{MRPACK_INDEX} okunamadı: {exc}") from exc
        if index.get("game") != "minecraft":
            raise ModpackImportError("Bu .mrpack bir Minecraft paketi değil.")
        deps = index.get("dependencies", {})
        minecraft = deps.get("minecraft")
        if not minecraft:
            raise ModpackImportError("Paket Minecraft sürümünü belirtmiyor.")
        loader, loader_version = Loader.VANILLA, ""
        for key, value in deps.items():
            if key in _MRPACK_LOADERS:
                loader, loader_version = _MRPACK_LOADERS[key], value
                break

        pack = manager.create_pack(
            name=name or index.get("name") or path.stem, minecraft=minecraft, loader=loader,
            loader_version=loader_version, summary=index.get("summary", ""),
        )
        pack.version = str(index.get("versionId") or pack.version)
        result = ImportResult(pack=pack, format="mrpack")
        files = index.get("files", [])

        sha1s = [f.get("hashes", {}).get("sha1", "").lower() for f in files if f.get("hashes", {}).get("sha1")]
        found: dict[str, ModVersion] = {}
        details: dict[str, ModDetail] = {}
        try:
            found = await modrinth.versions_for_hashes(sha1s)
            details = await modrinth.get_projects([v.project_id for v in found.values()]) if found else {}
        except Exception as exc:  # noqa: BLE001 - Modrinth'e ulaşılamazsa hepsi URL kaynaklı eklenir
            log.warning("Modrinth hash sorgusu başarısız, dosyalar doğrudan URL olarak eklenecek: %s", exc)

        for i, f in enumerate(files, start=1):
            if progress_cb:
                progress_cb(i, len(files))
            rel = PurePosixPath(f.get("path", ""))
            if not rel.parts or ".." in rel.parts or rel.is_absolute():
                result.skipped.append(f"{f.get('path')}: güvensiz yol")
                continue
            top = rel.parts[0]
            kind = None if top == "mods" else _DIR_KIND.get(top)
            if top != "mods" and kind is None:
                result.skipped.append(f"{rel}: desteklenmeyen konum ({top}/)")
                continue
            hashes = f.get("hashes", {})
            sha1 = (hashes.get("sha1") or "").lower()
            downloads = f.get("downloads") or []
            if not downloads:
                result.skipped.append(f"{rel.name}: indirme adresi yok")
                continue
            env = f.get("env") or {}
            version = found.get(sha1)
            detail = details.get(version.project_id) if version else None
            common = dict(
                version_id=version.version_id if version else sha1[:12] or rel.name,
                file_name=rel.name, file_size=f.get("fileSize") or None,
                hashes=ModHashes(sha1=hashes.get("sha1"), sha512=hashes.get("sha512")),
                download_url=downloads[0],
            )
            if version is not None:
                ident = dict(source=ModSourceType.MODRINTH, project_id=version.project_id,
                             slug=detail.slug if detail else None, name=detail.title if detail else None)
            else:
                ident = dict(source=ModSourceType.URL, project_id=f"url:{sha1 or rel.name}", slug=None, name=rel.stem)
                result.url_sourced.append(rel.name)
            if kind is None:
                default_client = detail.client_side if detail else EnvRequirement.REQUIRED
                default_server = detail.server_side if detail else EnvRequirement.REQUIRED
                entry = ModEntry(
                    **ident, **common,
                    env=ModEnv(client=_env(env.get("client"), default_client), server=_env(env.get("server"), default_server)),
                    dependencies=[d.project_id for d in (version.dependencies if version else []) if d.dependency_type == "required" and d.project_id],
                )
                pack.mods = [m for m in pack.mods if m.project_id != entry.project_id] + [entry]
                result.mods += 1
            else:
                pack.content_downloads.append(ContentDownload(kind=kind, **ident, **common))
                result.content += 1

        overrides = manager.content_root(pack) / OVERRIDES_DIR
        _safe_extract_prefix(zf, ["overrides", "client-overrides"], overrides)
        if any(n.startswith("server-overrides/") for n in zf.namelist()):
            result.skipped.append("server-overrides/: sadece sunucuya özel dosyalar içe aktarılmadı")
    await _absorb_overrides(manager, pack, overrides, result, modrinth)
    manager.save(pack)
    log.info("mrpack içe aktarıldı: %s (%d mod, %d içerik, %d dünya, %d URL, %d atlandı)",
             pack.name, result.mods, result.content, result.worlds, len(result.url_sourced), len(result.skipped))
    return result


async def import_curseforge(manager, path: Path, *, curseforge, modrinth=None, name: str | None = None, progress_cb=None) -> ImportResult:
    if curseforge is None:
        raise ModpackImportError("CurseForge paketlerini içe aktarmak için Ayarlar'dan CurseForge API anahtarı girmelisiniz.")
    with zipfile.ZipFile(path) as zf:
        try:
            manifest = json.loads(zf.read(CF_MANIFEST).decode("utf-8"))
        except (KeyError, ValueError) as exc:
            raise ModpackImportError(f"{CF_MANIFEST} okunamadı: {exc}") from exc
        mc = manifest.get("minecraft", {})
        minecraft = mc.get("version")
        if not minecraft:
            raise ModpackImportError("Paket Minecraft sürümünü belirtmiyor.")
        loader, loader_version = Loader.VANILLA, ""
        loaders = mc.get("modLoaders", [])
        primary = next((x for x in loaders if x.get("primary")), loaders[0] if loaders else None)
        if primary:
            prefix, _, ver = primary.get("id", "").partition("-")
            if prefix in _CF_LOADER_PREFIX:
                loader, loader_version = _CF_LOADER_PREFIX[prefix], ver

        pack = manager.create_pack(
            name=name or manifest.get("name") or path.stem, minecraft=minecraft, loader=loader,
            loader_version=loader_version, author=manifest.get("author", ""),
        )
        pack.version = str(manifest.get("version") or pack.version)
        result = ImportResult(pack=pack, format="curseforge")
        files = manifest.get("files", [])
        for i, f in enumerate(files, start=1):
            if progress_cb:
                progress_cb(i, len(files))
            pid, fid = str(f.get("projectID", "")), str(f.get("fileID", ""))
            label = f"{pid}/{fid}"
            try:
                version = await curseforge.get_file(pid, fid)
                detail = await curseforge.get_project(pid)
            except Exception as exc:  # noqa: BLE001 - bir dosyanın hatası tüm içe aktarmayı durdurmasın
                result.skipped.append(f"{label}: {exc}")
                continue
            kind = _CF_CLASS_KIND.get(detail.class_id or 6)
            if kind is None:
                manager.add_mod(pack, version, detail)
                result.mods += 1
            else:
                manager.add_content_download(pack, kind, version, detail)
                result.content += 1

        overrides = manager.content_root(pack) / OVERRIDES_DIR
        _safe_extract_prefix(zf, [manifest.get("overrides") or "overrides"], overrides)
    await _absorb_overrides(manager, pack, overrides, result, modrinth)
    manager.save(pack)
    log.info("CurseForge paketi içe aktarıldı: %s (%d mod, %d içerik, %d dünya, %d atlandı)",
             pack.name, result.mods, result.content, result.worlds, len(result.skipped))
    return result


async def import_modpack(manager, path: Path, *, modrinth, curseforge, name: str | None = None, progress_cb=None) -> ImportResult:
    """Formatı otomatik algılar. Hata olursa yarım oluşturulmuş pack (ve
    açılmış overrides/dünyaları) geri silinir — kütüphanede yarım bir pack
    kalmaz."""
    fmt = detect_format(path)
    if fmt is None:
        raise ModpackImportError(f"{path.name}: tanınan bir modpack değil (modrinth.index.json ya da manifest.json yok).")
    before = {p.id for p in manager.list_packs()}
    try:
        if fmt == "mrpack":
            return await import_mrpack(manager, path, modrinth=modrinth, name=name, progress_cb=progress_cb)
        return await import_curseforge(manager, path, curseforge=curseforge, modrinth=modrinth, name=name, progress_cb=progress_cb)
    except BaseException:
        for pack in manager.list_packs():
            if pack.id not in before:
                log.warning("İçe aktarma başarısız, yarım pack siliniyor: %s", pack.name)
                manager.delete(pack.id)
        raise


