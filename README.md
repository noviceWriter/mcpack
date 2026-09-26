# MC Pack Manager (mcpack)

[![License: AGPL v3](https://img.shields.io/badge/License-AGPL%20v3-blue.svg)](LICENSE)

> **Bu bir Minecraft başlatıcısı (launcher) DEĞİLDİR — bir mod paketi
> (modpack) yöneticisidir.** Minecraft'ı çalıştırmaz, hesap girişi yapmaz.
> Modları arayıp bir pack'te toplar, `.mrpack` / CurseForge `.zip` / Prism
> `.zip` / Sunucu Paketi olarak dışa aktarır — oyunu asıl çalıştıran her
> zaman CurseForge App, Prism Launcher, Modrinth App gibi gerçek bir
> başlatıcı (ya da ayarladığınız SKLauncher) olur. Ayrıntılı kullanım için
> **[KULLANIM-KILAVUZU.md](KULLANIM-KILAVUZU.md)**'ya bakın.
>
> Bağımsız, topluluk kaynaklı bir araçtır; Mojang/Microsoft, Overwolf
> (CurseForge) ya da Modrinth ile bir bağlantısı/onayı yoktur.

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
  gui/                     # PySide6 arayüzü (Kütüphane sayfası + Instance sayfası)
  cli.py               # Basit komut satırı arayüzü
data/
  client_only_mods.json  # Server pack filtrelemesi için bilinen liste
tests/                    # pytest + respx ile API mock'ları
```

## Katkıda Bulunma

Katkı, hata bildirimi ve özellik önerileri için bkz. [CONTRIBUTING.md](CONTRIBUTING.md).
Topluluk davranış kuralları için [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md),
güvenlik açığı bildirimi için [SECURITY.md](SECURITY.md).

## Lisans

Bu proje **[AGPL-3.0](LICENSE)** ile lisanslanmıştır: kaynağı özgürce
kullanabilir, değiştirebilir ve dağıtabilirsiniz — ama değiştirilmiş bir
sürümü dağıtırsanız ya da bir ağ servisi olarak sunarsanız, o değiştirilmiş
kaynağı da aynı lisansla paylaşmanız gerekir. Ticari kullanım serbesttir,
kapalı kaynak olarak yeniden dağıtım değildir. Sade Türkçe açıklama için
[LISANS-SSS.md](LISANS-SSS.md)'ye bakın (bu bir hukuki tavsiye değildir).
