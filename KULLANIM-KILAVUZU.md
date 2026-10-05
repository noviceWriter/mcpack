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

### 4.4 Sunucu Yönetimi (yerel sunucu başlat/durdur)

4.1'deki "Sunucu Paketi" bir zip ÜRETİR (başka yere taşıyıp elle
çalıştırırsınız) — instance sayfasındaki sol rafta **"🖥 Sunucu"**
bölümü ise sunucuyu doğrudan MC Pack Manager İÇİNDEN, ayrı bir terminale
hiç gitmeden çalıştırır:

1. **Hazırla / Güncelle**: pack'inizdeki sunucuya uygun modları + gerçek
   sunucu dosyasını (bkz. 4.1) indirip pack'in kendi kalıcı sunucu
   klasörüne kurar/günceller.
2. **Forge/NeoForge'ta ek bir adım**: resmi olarak sadece bir *kurulum
   programı* var — "Hazırla"dan sonra bir **"Kur"** butonu belirir, ona
   basmanız gerekir (bir kerelik).
3. **Başlat**: ilk seferinde Minecraft EULA'sını (gerçek metne link
   verilir) kabul etmeniz istenir — kabul etmeden sunucu başlamaz, bu
   SİZİN kararınızdır. Java sisteminizde yoksa ya da PATH'te
   bulunamıyorsa Ayarlar'dan **Java Yolu**'nu elle belirtebilirsiniz.
4. **Canlı + renkli konsol**: sunucunun gerçek log çıktısı anlık olarak
   ekranda akar (HATA satırları kırmızı, UYARI satırları turuncu);
   **Konsolu Temizle**, konsolda **Ara**, ve **Otomatik Kaydır**
   (kapatırsanız yeni satırlar gelince sayfa aşağı zıplamaz, eski loga
   rahat bakabilirsiniz) araçları var. Alttaki kutudan sunucuya komut
   yazıp (ör. `op <isim>`, `say merhaba`) **Gönder**'e basabilir, **↑/↓**
   ile daha önce gönderdiğiniz komutlar arasında (terminal gibi)
   gezinebilirsiniz.
5. **Oyuncular paneli**: sunucu çalışırken çevrimiçi oyuncular ~4
   saniyede bir otomatik listelenir (ya da **Listeyi Yenile**'ye basın).
   Bir oyuncu seçince, komut yazmadan: **İyileştir**, **Öldür**, **Hasar
   Ver** (miktar girilebilir — MC 1.19.4+'ta tam isabetli, öncesinde
   yaklaşık), **Doyur**, **Açlığı Azalt** (bu SADECE süre boyunca daha
   hızlı acıktırır, vanilla'da "anında belirli bir seviyeye ayarlama"
   diye bir şey yok — buton bunu açıkça belirtir), **Envanteri
   Görüntüle** (zırh + eldeki/ikinci eldeki eşya dahil) ve **Ender
   Sandığını Görüntüle** — hepsi SALT OKUNUR, tamamen vanilla
   komutlarla (RCON/eklenti gerekmez). Envanter DÜZENLEME yoktur —
   Minecraft bunu oyuncu hesapları için zaten engeller (hile önleme).
6. **Durdur**: sunucuya GERÇEK Minecraft `stop` komutunu gönderir (dünya
   düzgünce kaydedilir) — asla zorla kapatmaz.
7. **Ayarlar**:
   - **Bellek (RAM)**: GB cinsinden bir açılır listeden seçin, ya da
     "Özel (MB)" ile tam MB girin. **Listede, bilgisayarınızın gerçek
     RAM'inden FAZLA bir seçenek hiç gösterilmez** — sisteminiz
     donmasın diye her zaman en az 2 GB size bırakılır (ör. 16 GB
     RAM'iniz varsa sunucuya en fazla 14 GB ayrılabilir; bu sınır
     otomatik hesaplanır, elle bir şey yapmanız gerekmez).
   - **Performans bayraklarını kullan (Aikar's flags)**: işaretlerseniz
     Minecraft sunucu topluluğunda yıllardır bilinen, GC
     duraklamalarını azaltan standart bir JVM bayrak seti eklenir —
     mcpack'e özgü değil, sadece doğru bayrakları sizin için üretiyoruz.
   - Hangi yüklü dünyanın kullanılacağı, ve en sık değiştirilen
     `server.properties` alanları (MOTD, zorluk, oyun modu, port, PVP,
     beyaz liste, görüş mesafesi...) buradan düzenlenip kaydedilebilir —
     kaydetmek sunucunun kendi ürettiği diğer tüm ayarları SİLMEZ,
     sadece bu alanları günceller.

mcpack kapatılırken hâlâ çalışan bir sunucu varsa, önce düzgünce
durdurulsun mu diye sorulur (sessizce öksüz bırakmaz).

### 4.5 Web Paneli (tarayıcıdan sunucu yönetimi)

Araç çubuğundaki **"🌐 Web Paneli"** butonu, 4.4'teki sunucu yönetiminin
AYNISINI (hazırla/kur/başlat/durdur/konsol/oyuncular/ayarlar) bir
tarayıcı sekmesinde, daha modern bir arayüzle sunar — Qt'nin yerini almaz,
sadece ek bir önyüzdür. Tekrar tıklayınca kapanır (**kullanıcı isterse
tamamen kapatabilir** — açık bir ağ portu istemiyorsanız hiç başlatmayın).

**Güvenlik — mutlaka okuyun:**
- Ayarlar'da **Web Paneli Şifresi** BOŞSA panel SADECE bu bilgisayardan
  açılabilir (`127.0.0.1`) — ağa hiç çıkmaz.
- Bir şifre girerseniz panel **aynı ağdaki diğer cihazlardan da**
  (telefonunuz, aynı WiFi'daki başka bir bilgisayar) erişilebilir hale
  gelir — buton bu durumda size gerçek yerel ağ adresinizi gösterir.
  Şifre girmeden ağa açık bir panel ASLA yayınlanmaz — aksi halde aynı
  ağdaki herkes (misafir WiFi'ı, güvenilmeyen biri) hiçbir onay sormadan
  sunucunuzu durdurabilir ya da oyuncu öldürebilirdi.
- Şifreyle giriş yapılınca tarayıcıda bir oturum çerezi tutulur; "Ayarlar
  > Port" ile hangi port kullanılacağını da değiştirebilirsiniz.

## 5. Ayarlar

Sağ üstteki **⚙ Ayarlar**'dan:
- **CurseForge API Key**: CurseForge aramasının çalışması için gerekir
  (console.curseforge.com üzerinden kendi hesabınızla alınır). Girdikten
  sonra **Bağlantıyı Test Et** ile gerçekten geçerli olup olmadığını
  kontrol edebilirsiniz.
- **Modrinth tercihi**: aynı mod iki kaynakta da varsa hangisinin tercih
  edileceği.
- **SKLauncher yolu**, **Java yolu** (bkz. 4.4 — boşsa PATH'teki `java`
  kullanılır), **Web Paneli Şifresi/Port** (bkz. 4.5), **export'ta hariç
  tutulacak klasörler** (logs, crash-reports, saves).

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
