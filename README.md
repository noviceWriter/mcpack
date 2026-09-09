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

### CLI örnekleri

```bash
mcpack-cli create --name "Perf Pack" --minecraft 1.21.1 --loader fabric --loader-version 0.16.5
mcpack-cli list
mcpack-cli search sodium --source both --minecraft 1.21.1 --loader fabric   # Modrinth+CF birlikte, çakışanlarda tercih Settings.prefer_modrinth'e göre
mcpack-cli add-mod <pack_id> AANobbMI --source modrinth
mcpack-cli set-env <pack_id> <project_id> --client optional --server unsupported  # env bilgisi belirsizse elle düzelt
mcpack-cli export <pack_id> mrpack --output ./out/pack.mrpack
mcpack-cli export <pack_id> server --output ./out/pack-server.zip
```

## Testler

```bash
pytest
```

## Ayarlar

GUI'de **Ayarlar** menüsünden (CF API key, SKLauncher yolu, Modrinth tercihi,
export'ta hariç tutulacak logs/crash-reports/saves) ya da doğrudan
`~/.config/mcpack/settings.json` (Linux) / `%APPDATA%/mcpack/settings.json`
(Windows) dosyasından yapılandırılır. API key koda gömülmez, repo dışında kalır.

## Büyük pack'lerde iptal

Export / server pack / SKLauncher instance hazırlama sırasında GUI'deki
**İptal** butonu, devam eden indirmeleri chunk aralarında durdurur
(kısmi `.part` dosyaları temizlenir).

## Klasör Yapısı

```
src/mcpack/
  models.py          # Pack, ModEntry, enum'lar (dahili JSON şeması)
  config.py           # Ayarlar (CF API key, SKLauncher yolu)
  downloader.py        # Async indirme + hash doğrulama + rate limit
  launcher.py           # SKLauncher instance hazırlama + çalıştırma
  sources/              # Modrinth + CurseForge API client'ları + birleşik arama
  packs/                 # Pack yönetimi (oluştur/kaydet/mod ekle-çıkar/env düzelt)
  export/                 # mrpack / CurseForge / Prism / server pack export
  gui/                     # PySide6 arayüzü (3 panelli düzen + ayarlar penceresi)
  cli.py               # Basit komut satırı arayüzü
data/
  client_only_mods.json  # Server pack filtrelemesi için bilinen liste
tests/                    # pytest + respx ile API mock'ları
```
