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

Program solda bir **kenar çubuğu** ile açılır: **Ana Sayfa**, **Kütüphane**,
açık olan pack, **Ayarlar** ve **Geliştirici**. Her yerden **Ctrl+K** ile
komut paletini açıp sayfa, pack ya da eylem arayabilirsiniz.

- **Ana Sayfa**: pack/mod sayıları, çalışan sunucular, son düzenlenen
  pack'ler, sistem sağlığı (Java, CurseForge anahtarı, SKLauncher) ve
  hızlı erişim düğmeleri.
- **Kütüphane**: tüm pack'ler kart ızgarası ya da liste olarak (☰ düğmesi).
  Arama, loader filtresi (Fabric/Forge/…) ve sıralama (son düzenlenen, ad,
  mod sayısı, MC sürümü) var. Karta tıklamak pack'i açar; sağ tık ya da
  **⋯** menüsü: bilgileri düzenle, kopyala, fork, dışa aktar, klasörleri
  aç, sil.
- **⇪ İçe Aktar** (Ctrl+O ya da dosyayı pencereye sürükleyip bırakın):
  Modrinth `.mrpack` veya CurseForge modpack `.zip` dosyasından yeni bir
  pack oluşturur. Modlar Modrinth'te dosya hash'iyle (tek istekte),
  CurseForge'ta proje/dosya kimliğiyle (API anahtarı gerekir) tanınır;
  Modrinth'te bulunmayan dosyalar doğrudan indirme adresiyle (hash
  doğrulamalı) eklenir. Paketin `overrides/` dosyaları (config, kubejs…)
  pack'in kendi klasörüne açılır, içindeki dünyalar Dünyalar bölümüne
  taşınır; dışa aktarırken **İçe aktarılan overrides** seçeneğiyle tekrar
  pakete eklenir.
- **+ Yeni Pack** (Ctrl+N): ad, Minecraft sürümü, loader ve loader sürümü.
  Sürümler resmi listelerden gelir; en yeni ve sağlayıcının **★ önerilen**
  sürümü işaretlenir.

Alt durum çubuğunda o an çalışan görev (ilerleme çubuğu ve **İptal**
düğmesiyle), uyarı/hata sayaçları (⚠/✖, tıklayınca log görüntüleyici
açılır) ve web panelinin durumu görünür. Bildirimler sağ altta kısa süreli
kutucuklar (toast) olarak çıkar; hata bildirimlerindeki **Ayrıntılar**
düğmesi doğrudan ilgili log/istisnayı açar.

## 3. Pack Sayfası

Bir pack'i açtığınızda üstte başlık ve **Dışa Aktar ▾** menüsü, solda
bölümler bulunur:

- **Genel Bakış**: mod/içerik sayıları, sadece-istemci ve sunucu modları,
  indirme boyutu, pack bilgileri ve **bağımlılık sağlığı** (eksik zorunlu
  bağımlılıklar çevrimdışı olarak hemen gösterilir; **Bağımlılıkları Kontrol
  Et** adlarını ağdan çözer).

### 3.1 Modlar
- Tablo: ad, kaynak, ortam (İstemci / Sunucu / İstemci + Sunucu), dosya,
  boyut, bağımlılık. Sütun başlığına tıklayarak sıralanır; metin, kaynak ve
  ortam filtresi vardır (**Eksik bağımlılığı olan** filtresi sorunlu modları
  tek tıkla gösterir).
- **Çoklu seçim** (Ctrl/Shift) ile birden çok modu aynı anda kaldırabilir
  ya da ortamını düzeltebilirsiniz. **Delete** tuşu kaldırır; kaldırılan
  modlara bağımlı başka modlar varsa ayrıca uyarılırsınız.
- Sağ tık: istemci/sunucu düzelt, proje sayfasını aç, proje ID'si / dosya
  adı / indirme URL'si kopyala. Çift tıklama ortam düzenleyicisini açar.
- **↑ Güncellemeleri Kontrol Et**: pack'teki mod ve shader/kaynak paketi/
  datapack'ler için, pack'in Minecraft sürümü ve loader'ıyla uyumlu daha yeni
  sürüm olup olmadığına bakar (Modrinth modları tek istekte sorgulanır).
  Güncellemesi olan modlar tabloda **↑** ile işaretlenir ("Güncellemesi olan"
  filtresiyle listelenebilir); açılan pencereden istediklerinizi seçip
  güncellersiniz. Elle düzelttiğiniz istemci/sunucu ayarları korunur; yeni
  sürüm yeni bir zorunlu bağımlılık getirirse otomatik eklenir.

### 3.2 Keşfet (mod / shader / kaynak paketi / datapack / dünya ekleme)
- Üstteki çiplerle içerik türünü seçin, arayın (boş arama popülerleri
  listeler). Sonuçlar sonsuz kaydırmalıdır.
- Sağ panelde seçili projenin ayrıntısı: **En Yeni Sürümü Ekle**, **Sürüm
  Seç…** (tüm uyumlu sürümler tablo halinde: MC sürümleri, loader, boyut,
  zorunlu bağımlılık sayısı) ve **Tarayıcıda aç**. Çift tıklama hızlı ekler.
- Zorunlu bağımlılıklar otomatik eklenir; uyumlu sürümü olmayan zorunlu
  bağımlılık varsa uyarılırsınız. Opsiyonel bağımlılıklar "Önerilen Modlar"
  penceresinde size sorulur.
- Dünyalar sadece CurseForge'ta bulunur (API anahtarı gerekir).

### 3.3 Shader / Kaynak Paketi / Datapack
Eklenenler kendi bölümlerinde listelenir; çoklu seçimle kaldırılabilir,
**Keşfet'te Ara** ilgili türü doğrudan açar.

> Not: Minecraft datapack'leri sadece bir dünya kaydının içinden çalışır.
> Eklediğiniz bir datapack'in export'ta işe yaraması için pack'inize
> **bir dünya da eklemiş olmanız** gerekir (bkz. 3.4).

### 3.4 Dünyalar
İki yol vardır:
- **+ Klasörden Dünya Ekle**: diskinizdeki hazır bir dünya kaydını (içinde
  `level.dat` olan klasör, genelde `.minecraft/saves/<dünya adı>`) seçip
  pack'e kopyalar. `level.dat` yoksa eklemeden önce uyarılırsınız.
- **CurseForge'ta Ara**: CurseForge'ta hazır bir harita/dünya arayıp indirir.

Birden fazla dünya yükleyebilirsiniz; hangisinin sunucu paketine
ekleneceği export sırasında ayrıca sorulur (bkz. 4.2).

### 3.5 Sunucu
Yerel sunucu yönetimi bu bölümdedir — ayrıntılar için bkz. 4.4.

## 4. Dışa Aktarma

Pack sayfasının sağ üstündeki **Dışa Aktar ▾** menüsünden bir format seçin
(dışa aktarmadan önce eksik zorunlu bağımlılıklar kontrol edilir; ek
config/kubejs dosyaları — overrides — eklemek isteyip istemediğiniz sorulur):

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
   ekranda akar (HATA kırmızı, UYARI turuncu, sohbet mavi, giriş/çıkış
   yeşil). **Seviye filtresi** (tüm satırlar / uyarı+ / sadece hata),
   eşleşmeleri vurgulayan **arama** (▲/▼ ile önceki/sonraki), **Otomatik
   kaydır**, **Satır kaydır**, kopyala / dosyaya kaydet / temizle ve hızlı
   komut düğmeleri (gündüz, hava, save-all, list…) var. Komut kutusu
   vanilla komutlarını otomatik tamamlar. Alttaki kutudan sunucuya komut
   yazıp (ör. `op <isim>`, `say merhaba`) **Gönder**'e basabilir, **↑/↓**
   ile daha önce gönderdiğiniz komutlar arasında (terminal gibi)
   gezinebilirsiniz.
5. **Oyuncular sekmesi**: sekme açıkken çevrimiçi oyuncular ~5 saniyede
   bir otomatik listelenir (ya da **Yenile**'ye basın). OP ver/al, oyun
   modu ve at (kick) kısayolları da vardır.
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

Kenar çubuğundaki **🌐 Web Panelini Aç** (ya da Ayarlar > Web paneli)
düğmesi, 4.4'teki sunucu yönetiminin AYNISINI (hazırla/kur/başlat/durdur/
konsol/oyuncular/ayarlar/server.properties) — artık uygulama logları ve
teşhis sekmeleriyle birlikte — bir
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
- Ayarlardaki port başka bir program tarafından kullanılıyorsa panel
  otomatik olarak sıradaki boş portta açılır ve portu hangi programın
  tuttuğunu bildirir (ör. "8765 dolu — panel 8766'da açıldı").
- Şifreyle giriş yapılınca tarayıcıda bir oturum çerezi tutulur; "Ayarlar
  > Port" ile hangi port kullanılacağını da değiştirebilirsiniz.

## 5. Ayarlar

Kenar çubuğundaki **⚙ Ayarlar** (Ctrl+,) sayfasında ayarlar kartlar
halinde gruplanır; değişiklikler **Kaydet**'e basınca uygulanır (kaydedilmemiş
değişiklik varsa başlıkta gösterilir, pencereyi kapatırken sorulur).
- **Genel**: arayüz dili (yeniden başlatınca etkili olur; web paneli de aynı
  dili kullanır) ve **Debug modu** (bkz. 7).
- **Mod kaynakları**: CurseForge API anahtarı (**Test Et** ile doğrulanır),
  Modrinth tercihi. Anahtar ve web paneli şifresi işletim sisteminin anahtar
  zincirinde saklanır (eski sürümden kalan düz metin anahtar ilk açılışta
  otomatik taşınır); kart bunun nerede saklandığını gösterir.
- **Başlatıcı ve Java**: SKLauncher yolu, Java yolu (**Algıla** sürümü de
  gösterir; boşsa PATH'teki `java`).
- **Web paneli**: port, şifre, başlat/durdur (bkz. 4.5).
- **Dışa aktarma**: logs / crash-reports / saves hariç tutma.
- **Veri ve önbellek**: pack klasörü, önbellek boyutunu ölçme ve temizleme.
- **Varsayılanlara Sıfırla** (sağ üst): tüm ayarları ilk kurulum değerlerine
  döndürür. İsterseniz CurseForge anahtarı ve web paneli şifresi korunur.
  Eski ayar dosyası önce `settings.backup-<zaman>.json` olarak yedeklenir;
  pack'lerinize dokunulmaz.

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

## 7. Loglar ve Hata Ayıklama

Program her şeyi bir log dosyasına yazar:
- Linux: `~/.config/mcpack/logs/mcpack.log` · Windows: `%APPDATA%\mcpack\logs\mcpack.log`
  (2 MB'ta döner, 5 eski dosya saklanır).
- Beklenmeyen bir çökme olursa `logs/crash/` altına sistem bilgisi ve son
  log satırlarını içeren bir **crash raporu** yazılır.

Kenar çubuğundaki **🐞 Geliştirici** (F12) sayfası:
- **Loglar**: canlı log akışı — seviye, kaynak ve metin filtresi, duraklat,
  kopyala, dışa aktar. Bir satıra tıklayınca tam mesaj ve traceback görünür.
- **Görevler**: arka planda çalışan/çalışmış her işlem (indirme, export,
  arama…) — durum, ilerleme, süre, hata ve traceback; buradan iptal
  edilebilir.
- **Ağ**: her HTTP isteği (yöntem, durum, süre, sunucu) ve istatistikler.
  İstek başlıkları — dolayısıyla CurseForge anahtarınız — asla kaydedilmez.
- **İstisnalar**: yakalanan/yakalanmayan tüm hatalar (tekrar sayısıyla) ve
  crash raporları.
- **Sistem**: sürüm/ortam bilgisi, canlı uygulama durumu, tek tıkla
  **teşhis** (klasör izinleri, disk, Java, Modrinth/Mojang/Fabric/Forge
  erişimi, CurseForge anahtarı, web paneli portu, pack dosyaları) ve
  **Destek Paketi Oluştur** — loglar, crash raporları ve gizli bilgileri
  maskelenmiş ayarları tek bir zip'te toplar; hata bildirirken ekleyin.
- **Python** (sadece debug modunda): uygulamanın canlı nesnelerine erişen
  geliştirici konsolu.

**Debug modu**: Ayarlar'dan, Geliştirici > Loglar'daki DEBUG kutusundan,
**Ctrl+Shift+D** ile, `mcpack --debug` ile ya da `MCPACK_DEBUG=1` ortam
değişkeniyle açılır — her ağ isteği ve iç adım ayrıntılı loglanır.

Web panelinde de **Uygulama Logları** ve **Teşhis** sekmeleri vardır
(sistem bilgisi, ağ istekleri, son istisnalar).
