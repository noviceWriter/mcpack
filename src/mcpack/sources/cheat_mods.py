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

import httpx

WURST_RELEASES_API = "https://api.github.com/repos/Wurst-Imperium/Wurst-MCX2/releases"
METEOR_DOWNLOAD_API = "https://meteorclient.com/api/download"


class CheatModUnavailableError(Exception):
    """Bu Minecraft versiyonu için resmi bir build bulunamadığında (ya da
    ağ/API hatası durumunda) fırlatılır — çağıran taraf (main_window.py)
    bunu doğrudan kullanıcıya gösterir."""


async def find_wurst_download(client: httpx.AsyncClient, minecraft_version: str) -> tuple[str, str]:
    """(dosya_adı, indirme_url) döner. GitHub Releases'i en yeniden eskiye
    tarayıp bu MC versiyonu için bir .jar asset'i arar (kaynak kodu jar'ı
    "-sources.jar" ile bitiyor, suffix eşleşmesi bunu doğal olarak eler)."""
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
                    return name, asset["browser_download_url"]
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
