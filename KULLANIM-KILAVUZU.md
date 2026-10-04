# MC Pack Manager — Kullanım Kılavuzu

> **⚠️ ÖNEMLİ — NET BİR ŞEKİLDE OKUYUN:**
> **MC Pack Manager bir Minecraft başlatıcısı (launcher) DEĞİLDİR.**
> Bu program Minecraft'ı **çalıştırmaz**, hesap girişi yapmaz, sürüm indirmez.
> Bu bir **mod paketi (modpack) yöneticisidir** — modları arayıp bir araya
> getirir, düzenler ve **CurseForge App**, **Prism Launcher**, **Modrinth
> App** gibi *gerçek* başlatıcıların anlayacağı formatlarda dışa aktarır.
> Oyunu asıl çalıştıran her zaman sizin zaten kullandığınız başlatıcıdır
> (ya da ayarlarda yol gösterdiğiniz **SKLauncher**, ki o da ayrı bir
> programdır — MC Pack Manager sadece ona bir "instance" hazırlayıp yolunu
> gösterir, kendisi Minecraft çalıştırmaz).

Bu kılavuz, programı ilk kez açan birinin baştan sona nasıl kullanacağını
anlatır. Teknik/geliştirici dokümantasyonu için `README.md`'ye bakın.

---

## 1. Program Nedir, Ne Değildir

| MC Pack Manager YAPAR | MC Pack Manager YAPMAZ |
|---|---|
| Modrinth ve CurseForge'ta mod/shader/görüntü paketi/datapack arar | Minecraft'ı başlatmaz |
| Bunları bir "pack" (mod paketi) altında toplar | Mojang/Microsoft hesabıyla giriş yapmaz |
| Bağımlılıkları otomatik çözer | Java/Minecraft sürümü indirmez |
| İstemci ↔ sunucu modlarını ayırır | Sunucu barındırmaz (sadece sunucu *dosyalarını* hazırlar) |
| `.mrpack` / CurseForge `.zip` / Prism `.zip` / Sunucu Paketi olarak **dışa aktarır** | Kendi başına bir oyun deneyimi sunmaz |
| Var olan bir SKLauncher kurulumuna instance hazırlayıp onu açar | SKLauncher'ın yerini almaz |

Kısacası: **modları toplayıp paketleyen, gerçek başlatıcıların/import
araçlarının kullanacağı dosyayı üreten bir "hazırlık" programıdır.**

Bağımsız, topluluk kaynaklı bir araçtır; Mojang/Microsoft (Minecraft),
Overwolf (CurseForge) ya da Modrinth ile bir bağlantısı ya da onayı yoktur.

---

## 2. İlk Açılış

Program açıldığında karşınıza **Kütüphane** sayfası çıkar — buradaki her
satır sizin oluşturduğunuz bir "pack"tir (mod paketi). İlk açılışta liste
boştur.

- **+ Yeni Pack**: yeni bir mod paketi oluşturur. İsim, Minecraft
  versiyonu, loader (Fabric/Quilt/Forge/NeoForge — mod eklemek istemiyorsanız
  "Vanilla" seçin) ve isteğe bağlı yazar/açıklama istenir.
- Arama kutusu: çok sayıda pack biriktiyse isme göre filtreler.
- Her satırdaki **Aç** butonu o pack'in detay sayfasını açar, **Sil** kalıcı
  olarak siler (onay ister).

## 3. Pack Detay Sayfası (Instance Sayfası)

Bir pack'i açtığınızda solda dikey bir bölüm listesi görürsünüz:

### 3.1 Modlar
- **+ Mod Ekle** ile Modrinth/CurseForge'ta arama yapıp pack'e mod
  eklersiniz. Arama penceresi ayrı bir pencere olarak açılır, ana pencereyle
  birlikte açık tutup art arda mod ekleyebilirsiniz.
- Bir mod eklendiğinde, o modun opsiyonel bağımlılıkları varsa "Önerilen
  Modlar" penceresi açılır — istediklerinizi işaretleyip ekleyebilirsiniz.
- Tablodaki **Ortam** sütunu modun istemci/sunucu gereksinimini gösterir
  (İstemci / Sunucu / İstemci + Sunucu). CurseForge bu bilgiyi her zaman
  doğru vermeyebilir — yanlışsa satırı seçip **İstemci/Sunucu Düzelt** ile
  elle düzeltebilirsiniz.
- Sütun başlıklarına tıklayarak sıralayabilir, arama kutusuyla filtreleyebilirsiniz.
- **Vanilla** pack'lerde bu bölüm boştur (loader olmadığı için mod eklenemez)
  — shader/görüntü paketi/datapack/dünya ise loader gerektirmediğinden vanilla
  pack'lere de eklenebilir.

### 3.2 Shader Paketleri / Görüntü Paketleri / Datapack'ler
Üçü de aynı akışla çalışır: **+ Ekle** ile Modrinth/CurseForge'ta arayıp
pack'e eklersiniz (gerçek dosya, export anında indirilir). Kaldırmak için
tablodan seçip **Seçiliyi Kaldır**.

> Not: Minecraft datapack'leri sadece bir dünya kaydının içinden çalışır.
> Eklediğiniz bir datapack'in export'ta işe yaraması için pack'inize
> **bir dünya da eklemiş olmanız** gerekir (bkz. 3.3).

### 3.3 Dünyalar
İki yol vardır:
- **+ Dünya Klasörü Seç**: diskinizdeki hazır bir dünya kaydını (içinde
  `level.dat` olan klasör, genelde `.minecraft/saves/<dünya adı>`) seçip
  pack'e kopyalar.
- **+ CurseForge'ta Dünya Ara**: CurseForge'ta hazır bir harita/dünya arayıp
  indirir (Modrinth'te "dünya" diye bir proje türü olmadığı için bu yol
  sadece CurseForge'ta çalışır).

Birden fazla dünya yükleyebilirsiniz; hangisinin sunucu paketine
ekleneceği export sırasında ayrıca sorulur (bkz. 4.2).

## 4. Dışa Aktarma

Sağ üstteki format kutusundan birini seçip **Dışa Aktar**'a basın:

| Format | Nereye import edilir |
|---|---|
| Modrinth (`.mrpack`) | Modrinth App, Prism Launcher, ATLauncher |
| CurseForge (`.zip`) | CurseForge App |
| Prism / MultiMC (`.zip`) | Prism Launcher, MultiMC |

Export sırasında bir "overrides kaynak klasörü" seçmeniz istenir — bu,
`config/`, `kubejs/`, `defaultconfigs/` gibi dosyalarınızın bulunduğu
klasördür (varsa). Yoksa boş bir klasör seçip geçebilirsiniz.

### 4.1 Sunucu Paketi
**Sunucu Paketi** butonu, pack'inizden sunucuda çalışmayan (istemci-only)
modları otomatik eleyerek bir sunucu kurulumu üretir.

Gerçek sunucu çalıştırılabilir dosyası da artık **otomatik indirilip pakete
eklenir** — ayrıca bir siteye gidip indirmenize gerek yok:
- **Vanilla/Fabric/Quilt:** hazır, çalıştırılabilir `server.jar` doğrudan
  pakete konur; `start.sh`/`start.bat` ile direkt başlatabilirsiniz.
- **Forge/NeoForge:** resmi olarak sadece bir *kurulum programı*
  (installer) yayınlanıyor; bu installer indirilip pakete eklenir, ama
  kurulumu (`java -jar <installer> --installServer`) bir kerelik elle
  yapmanız gerekir — `start.sh`/`start.bat` içinde tam komut yazılı.
- Nadir bir durumda (ağ hatası ya da o Minecraft versiyonu için resmi bir
  dosya hiç yayınlanmamışsa) otomatik indirme başarısız olursa export
  BOZULMAZ — pakete `SUNUCU_DOSYASI_INDIRILEMEDI.txt` eklenir ve program
  size bunu hemen bir uyarı penceresiyle bildirir.

### 4.2 Dünya Ekleme Notu
Pack'inize bir dünya yüklediyseniz, sunucu paketi oluştururken program size
**"Bu pack'e yüklenmiş dünya var, sunucu paketine eklemek ister misiniz?"**
diye sorar. Evet derseniz (birden fazla dünya varsa **ana dünyanızı
seçmeniz** istenir) seçilen dünya, sunucuların beklediği şekilde otomatik
olarak **`world`** adıyla pakete eklenir — orijinal dosya adı ne olursa olsun.

### 4.3 SKLauncher ile Çalıştır
Ayarlar'dan SKLauncher'ın (portable exe/AppImage) yolunu bir kez
belirledikten sonra, bu buton pack'inizi bir SKLauncher instance'ı olarak
hazırlar ve SKLauncher'ı açar — **Minecraft'ı doğrudan MC Pack Manager
çalıştırmaz, hazırlığı yapıp işi SKLauncher'a devreder.**

## 5. Ayarlar

Sağ üstteki **⚙ Ayarlar**'dan:
- **CurseForge API Key**: CurseForge aramasının çalışması için gerekir
  (console.curseforge.com üzerinden kendi hesabınızla alınır). Girdikten
  sonra **Bağlantıyı Test Et** ile gerçekten geçerli olup olmadığını
  kontrol edebilirsiniz.
- **Modrinth tercihi**: aynı mod iki kaynakta da varsa hangisinin tercih
  edileceği.
- **SKLauncher yolu**, **export'ta hariç tutulacak klasörler** (logs,
  crash-reports, saves).

## 6. Sık Sorulan Sorular

**"Modu/paketi indirdim ama oyunda görünmüyor?"**
MC Pack Manager dosyayı indirip pack'inize kaydeder; oyunda görünmesi için
pack'i bir formata **dışa aktarıp** o formatı destekleyen bir başlatıcıya
(CurseForge App, Prism Launcher, Modrinth App) **import etmeniz** gerekir.

**"Bu program Minecraft hesabımı mı kullanıyor?"**
Hayır. Program hiçbir Mojang/Microsoft hesap bilgisi istemez ya da saklamaz.

**"CurseForge/Modrinth çöktü, uygulama donmuş gibi görünüyor?"**
Ağ hatalarında artık kısa, anlaşılır bir hata mesajı gösterilir; alttaki
durum çubuğundaki **İptal** butonuyla uzun süren işlemleri durdurabilirsiniz.
