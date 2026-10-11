"""Wurst Client / Meteor Client indirme.

CurseForge ve Modrinth bu tür "hile" (cheat/utility) istemcilerini platform
kurallarına aykırı bularak barındırmıyor — bu yüzden ikisi de kendi resmi
altyapılarından indiriliyor. Kullanıcı isteği: "kendi indirme API'leri
vardır, bunları programa entegre edip 2. bir programa/tarayıcıya gitmeden
indirebilmeliyiz." İkisi de kimlik doğrulama GEREKTİRMEYEN, gerçek kaynaklar:

- Wurst: GitHub Releases (Wurst-Imperium/Wurst-MCX2). Resmi web sitesinin
  (wurstclient.net, kaynağı github.com/Wurst-Imperium/wurstclient.net'te
  açık) kendi Jekyll "_updates" koleksiyonundaki gerçek indirme linklerine
  bakılarak teyit edildi — asset adları "Wurst-Client-v<sürüm>-MC<mc
  versiyonu>.jar" formatında.
- Meteor: https://meteorclient.com/api/download?version=<mc versiyonu>.
  Resmi backend'in (github.com/MeteorDevelopment/meteor-server,
  pkg/web/api/download.go) açık kaynak koduna bakılarak teyit edildi.
  ÖNEMLİ: bu endpoint desteklenmeyen bir MC versiyonunda HTTP 200 ile
  küçük bir JSON hata gövdesi döner (asıl jar değil) — Content-Type
  kontrol edilmezse bu sessizce ".jar" gibi indirilip export'u bozar,
  bu yüzden burada özellikle doğrulanıyor.

İkisi de SADECE Fabric'te çalışır (Fabric-only mod) — GUI tarafı bu bölümü
sadece Fabric pack'lerinde gösterir (bkz. gui/instance_page.py)."""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path

import httpx

from mcpack.downloader import DownloadError, compute_hash, download_file
from mcpack.models import ModSourceType

WURST_RELEASES_API = "https://api.github.com/repos/Wurst-Imperium/Wurst-MCX2/releases"
METEOR_DOWNLOAD_API = "https://meteorclient.com/api/download"


class CheatModUnavailableError(Exception):
    """Bu Minecraft versiyonu için resmi bir build bulunamadığında (ya da
    ağ/API hatası durumunda) fırlatılır — çağıran taraf (main_window.py)
    bunu doğrudan kullanıcıya gösterir."""


@dataclass(frozen=True)
class CheatModFile:
    """İndirilip doğrulanmış bir hile modu dosyası — pack'e bu hash'lerle
    kaydedilir, sonraki her indirme (export/sunucu/SKLauncher) bunlarla
    doğrulanır."""

    file_name: str
    url: str
    sha1: str
    sha512: str
    size: int
    sha256: str | None = None


async def find_wurst_download(client: httpx.AsyncClient, minecraft_version: str) -> tuple[str, str]:
    """(dosya_adı, indirme_url) döner — bkz. find_wurst_asset."""
    name, url, _sha256 = await find_wurst_asset(client, minecraft_version)
    return name, url


async def find_wurst_asset(client: httpx.AsyncClient, minecraft_version: str) -> tuple[str, str, str | None]:
    """(dosya_adı, indirme_url, sha256 | None) döner. GitHub Releases'i en
    yeniden eskiye tarayıp bu MC versiyonu için bir .jar asset'i arar
    (kaynak kodu jar'ı "-sources.jar" ile bitiyor, suffix eşleşmesi bunu
    doğal olarak eler). GitHub asset'leri için "digest": "sha256:…" alanı
    yayınlar — varsa ilk indirme buna karşı doğrulanır."""
    suffix = f"-MC{minecraft_version}.jar"
    for page in range(1, 6):  # ~150 release - eski MC versiyonları için de yeterli derinlik
        try:
            response = await client.get(WURST_RELEASES_API, params={"per_page": 30, "page": page})
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise CheatModUnavailableError(f"Wurst Client sürüm listesi alınamadı: {exc}") from exc
        releases = response.json()
        if not releases:
            break
        for release in releases:
            for asset in release.get("assets", []):
                name = asset.get("name", "")
                if name.endswith(suffix):
                    digest = asset.get("digest") or ""
                    sha256 = digest.split(":", 1)[1] if digest.startswith("sha256:") else None
                    return name, asset["browser_download_url"], sha256
    raise CheatModUnavailableError(f"Wurst Client, Minecraft {minecraft_version} için bir build sunmuyor.")


async def find_meteor_download(client: httpx.AsyncClient, minecraft_version: str) -> tuple[str, str]:
    """(dosya_adı, indirme_url) döner. Bu MC versiyonu desteklenmiyorsa
    CheatModUnavailableError fırlatır (bkz. modül docstring'i — 200 + JSON
    hata gövdesi durumu)."""
    url = f"{METEOR_DOWNLOAD_API}?version={minecraft_version}"
    try:
        response = await client.get(url)
    except httpx.HTTPError as exc:
        raise CheatModUnavailableError(f"Meteor Client sunucusuna ulaşılamadı: {exc}") from exc

    content_type = response.headers.get("content-type", "")
    if response.status_code != 200 or "json" in content_type.lower():
        raise CheatModUnavailableError(f"Meteor Client, Minecraft {minecraft_version} için bir build sunmuyor.")

    disposition = response.headers.get("content-disposition", "")
    file_name = "meteor-client.jar"
    if "filename=" in disposition:
        file_name = disposition.split("filename=", 1)[1].strip('"; ')
    return file_name, url


async def download_cheat_mod(
    client: httpx.AsyncClient,
    source: ModSourceType,
    minecraft_version: str,
    *,
    cache_dir: Path | None = None,
) -> CheatModFile:
    """Uygun build'i bulur, İNDİRİR ve hash'lerini hesaplar.

    Önceden sadece (dosya_adı, url) kaydediliyordu, hiçbir hash yoktu — her
    export'ta ne indirildiği doğrulanmıyordu. Wurst'te GitHub'ın SHA-256'sı
    ile ilk indirme doğrulanır; her iki modda da SHA-1/SHA-512/boyut
    hesaplanıp pack'e kaydedilir (trust-on-first-use). cache_dir verilirse
    dosya orada kalır (export aynı dosyayı tekrar indirmez)."""
    sha256 = None
    if source == ModSourceType.WURST:
        file_name, url, sha256 = await find_wurst_asset(client, minecraft_version)
    elif source == ModSourceType.METEOR:
        file_name, url = await find_meteor_download(client, minecraft_version)
    else:
        raise ValueError(f"Hile modu kaynağı değil: {source}")
    file_name = Path(file_name).name  # sunucudan gelen ad — yol bileşenlerini at

    async def _fetch(directory: Path) -> CheatModFile:
        dest = directory / file_name
        try:
            await download_file(client, url, dest, sha256=sha256)
        except DownloadError as exc:
            raise CheatModUnavailableError(f"{file_name} indirilemedi/doğrulanamadı: {exc}") from exc
        return CheatModFile(
            file_name=file_name,
            url=url,
            sha1=compute_hash(dest, "sha1"),
            sha512=compute_hash(dest, "sha512"),
            size=dest.stat().st_size,
            sha256=sha256,
        )

    if cache_dir is not None:
        cache_dir.mkdir(parents=True, exist_ok=True)
        return await _fetch(cache_dir)
    with tempfile.TemporaryDirectory(prefix="mcpack-cheat-") as tmp:
        return await _fetch(Path(tmp))
