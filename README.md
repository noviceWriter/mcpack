# mcpack — Minecraft Mod Paket Yöneticisi

Modrinth/CurseForge'tan mod arama, pack oluşturma, `.mrpack` / CurseForge /
Prism formatlarında export, server pack üretimi ve SKLauncher entegrasyonu.
Detaylı brief için `proje-amacı.md` dosyasına bakın.

## Kurulum

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Çalıştırma

```bash
mcpack            # GUI
mcpack-cli --help # CLI
```

## Testler

```bash
pytest
```

## Ayarlar

CurseForge API key ve SKLauncher yolu, GUI'de **Ayarlar** menüsünden veya
`~/.config/mcpack/settings.json` (Linux) / `%APPDATA%/mcpack/settings.json`
(Windows) dosyasından yapılandırılır. API key koda gömülmez.

## Klasör Yapısı

```
src/mcpack/
  models.py          # Pack, ModEntry, enum'lar (dahili JSON şeması)
  config.py           # Ayarlar (CF API key, SKLauncher yolu)
  downloader.py        # Async indirme + hash doğrulama + rate limit
  launcher.py           # SKLauncher instance hazırlama + çalıştırma
  sources/              # Modrinth + CurseForge API client'ları
  packs/                 # Pack yönetimi (oluştur/kaydet/mod ekle-çıkar)
  export/                 # mrpack / CurseForge / Prism / server pack export
  gui/                     # PySide6 arayüzü (3 panelli düzen)
  cli.py               # Basit komut satırı arayüzü
data/
  client_only_mods.json  # Server pack filtrelemesi için bilinen liste
tests/                    # pytest + respx ile API mock'ları
```
