# Proje Brief: Minecraft Mod Paket Yöneticisi

## 1. Projenin Amacı

Kullanıcıların kolayca:

- Modrinth ve CurseForge'tan mod arayıp indirmesini
- Kendi mod paketlerini oluşturmasını / yönetmesini
- Bu paketlerden hızlıca **client** ve **server** paketleri üretmesini
- Paketleri **Prism Launcher**, **CurseForge** ve **Modrinth** formatlarında dışa aktarmasını
- **SKLauncher** (portable exe / AppImage) ile tek tıkla çalıştırabilmesini

sağlayan bir masaüstü uygulaması / araç yazılacak.

Program hem client oyuncular hem de sunucu kuranlar için hızlı iş akışı sunmalı.

---

## 2. Temel Özellikler (MVP)

### 2.1 Mod Kaynakları

- **Modrinth API** ve **CurseForge API** desteği
- Arama (isim, kategori, loader, Minecraft versiyonu)
- Mod detayı, versiyon listesi, bağımlılık çözme
- Dosya indirme + SHA1/SHA512 hash doğrulama
- Aynı mod her iki sitede de varsa tercihen Modrinth kullanılsın (ayarlanabilir)

### 2.2 Mod Paketi Yönetimi

- Yeni pack oluşturma:
  - İsim, versiyon, yazar, açıklama
  - Minecraft versiyonu
  - Loader (Fabric / Quilt / Forge / NeoForge)
- Pack'e mod ekleme / çıkarma
- Bağımlılıkları otomatik ekleme
- Client-only / Server-only / Both ayrımı (mümkün olduğunca)
- Pack'i kendi dahili formatında kaydetme (JSON tabanlı)

### 2.3 Dışa Aktarma (Export)

Aşağıdaki formatları destekle:

| Format | Dosya | Açıklama |
|--------|-------|----------|
| Modrinth | `.mrpack` | `modrinth.index.json` + overrides |
| CurseForge | `.zip` | `manifest.json` + overrides |
| Prism / MultiMC | `.zip` | instance yapısı (`instance.cfg`, `mmc-pack.json` benzeri) |
| Server Pack | `.zip` | Sadece server-side modlar + config + gerekli dosyalar |

Export sırasında:

- Gereksiz dosyalar (logs, crash-reports, saves opsiyonel) hariç tutulabilmeli
- Overrides (config, kubejs, scripts, defaultconfigs vb.) dahil edilebilmeli

### 2.4 Server Paketi Üretimi

- Client pack'ten server paketi türetme
- Client-only modları otomatik eleme (Sodium, Iris, Mod Menu, REI client vb. bilinen listeler + API env bilgisi)
- Server-side / both modları tutma
- Config ve script klasörlerini kopyalama
- İsteğe bağlı basit start script (`start.bat` / `start.sh`) ekleme

### 2.5 SKLauncher Entegrasyonu

- Kullanıcının belirlediği **portable SKLauncher** yolu (Windows `.exe`, Linux AppImage, veya `.jar`)
- Pack'i SKLauncher'ın kullanabileceği bir **instance klasörü** olarak hazırlama
- "SKLauncher ile Çalıştır" butonu:
  1. Instance klasörünü oluştur / güncelle
  2. Portable launcher'ı bu instance ile başlatmaya çalış
- SKLauncher 3.x ve 4.x yapılarına mümkün olduğunca uyumlu ol

### 2.6 Kullanıcı Arayüzü (Öneri)

- Sol panel: Pack listesi
- Orta: Pack içeriği (mod listesi, loader, versiyon)
- Sağ / alt: Arama, export, server üret, launcher çalıştır
- Basit, hızlı, karışık olmayan arayüz
- Karanlık tema destekli olsun

---

## 3. Teknik Gereksinimler

### 3.1 API'ler

**Modrinth**

- Base: `https://api.modrinth.com/v2`
- User-Agent zorunlu ve tanımlayıcı olmalı
- Çoğu okuma işlemi için API key gerekmez
- Önemli endpoint'ler: search, project, versions, file download URL + hash

**CurseForge**

- Base: `https://api.curseforge.com`
- `x-api-key` header zorunlu
- Minecraft `gameId = 432`
- Mods classId genellikle 6, modpacks 4471
- Download URL ve fingerprint / file bilgileri kullanılacak

### 3.2 Format Detayları

**Modrinth `.mrpack`**

- ZIP arşivi
- Kökte `modrinth.index.json`
- `files[]` içinde path, hashes (sha1 + sha512), downloads[], fileSize, env (client/server)
- `dependencies` içinde minecraft + loader versiyonu
- Overrides klasörü

**CurseForge export**

- Kökte `manifest.json`
- `files[]` → projectID + fileID + required
- `minecraft.version` + `modLoaders`
- `overrides/` klasörü

**Prism tarzı**

- Instance klasörü veya zip
- Minecraft dosyaları `.minecraft` veya instance root altında
- Loader bilgisi ve metadata mümkün olduğunca doğru yazılsın

### 3.3 Önerilen Teknoloji Yığını

(Claude'un seçimine bırakılabilir, ama tercih sırası:)

1. **Python + PySide6 / NiceGUI / Textual** → hızlı geliştirme
2. **TypeScript + Tauri** → modern, hafif, cross-platform
3. **C# + Avalonia** → Windows odaklıysa çok iyi

Önemli kütüphane ihtiyaçları:

- Async HTTP
- ZIP oluşturma / okuma
- Hash hesaplama
- JSON
- Basit ayar dosyası (JSON/TOML/YAML)

---

## 4. Dahili Pack Formatı (Öneri)

Program kendi pack'lerini şu tarz bir JSON ile saklasın:

```json
{
  "id": "uuid",
  "name": "My Performance Pack",
  "version": "1.0.0",
  "author": "Kullanıcı",
  "summary": "Açıklama",
  "minecraft": "1.21.1",
  "loader": "fabric",
  "loader_version": "0.16.5",
  "mods": [
    {
      "source": "modrinth",
      "project_id": "AANobbMI",
      "version_id": "...",
      "file_name": "sodium-....jar",
      "hashes": { "sha1": "...", "sha512": "..." },
      "download_url": "...",
      "env": { "client": "required", "server": "unsupported" },
      "dependencies": []
    }
  ],
  "overrides": {
    "include": ["config", "kubejs", "defaultconfigs"]
  },
  "created_at": "...",
  "updated_at": "..."
}
Bu format hem export motoruna hem UI’ye beslenecek.

5. Kullanıcı Akışları
Akış A – Yeni Pack

Yeni pack oluştur → MC versiyonu + loader seç
Mod ara (Modrinth / CF)
Mod ekle → bağımlılıklar gelsin
Kaydet
Export et (mrpack / CF / Prism)
İstersen Server Pack üret
İstersen SKLauncher ile çalıştır

Akış B – Mevcut Pack’ten Server

Pack’i aç
“Server Pack Oluştur”
Client-only’ler elensin
Zip olarak kaydet

Akış C – SKLauncher

Ayarlardan portable SKLauncher yolunu belirle
Pack seç → “SKLauncher ile Çalıştır”
Instance hazırlanır ve launcher açılır


6. Önemli Kurallar / Dikkat Edilecekler

Her indirmede hash doğrula
Rate limit’lere saygı göster (özellikle Modrinth)
CurseForge API key kullanıcıdan alınsın (ayarlarda saklansın, asla koda gömülmesin)
Path traversal koruması (overrides içinde .. olmasın)
Client/Server ayrımında emin olunamayan modlar için kullanıcıya seçenek sun
Büyük pack’lerde progress bar / iptal desteği olsun
Hata mesajları anlaşılır olsun (Türkçe arayüz tercih edilir)


7. İleride Eklenebilecekler (MVP dışı)

Pack güncelleme kontrolü
Toplu mod güncelleme
Modrinth / CurseForge’a upload (ileri seviye)
World / resource pack / shader desteği
Otomatik Java indirme
Çoklu dil


8. Claude’dan İstenen Çıktı
Lütfen şu sırayla ilerle:

Proje klasör yapısını öner
Dahili pack JSON şemasını netleştir
Modrinth + CurseForge client sınıflarını yaz (arama, versiyon, indirme)
.mrpack export fonksiyonunu yaz
CurseForge zip export fonksiyonunu yaz
Server pack filtreleme mantığını yaz
Basit bir CLI veya GUI iskeleti kur
SKLauncher “çalıştır” akışı için taslak ekle

Kod temiz, okunabilir, yorumlu ve genişletilebilir olsun.

Mümkün olduğunca gerçek API endpoint’lerini ve gerçek format kurallarını kullan.