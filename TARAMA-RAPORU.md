# mcpack — Kod Tarama Raporu

**Tarih:** 11 Ekim 2026 · **Sürüm:** 1.1.0 · **Kapsam:** tüm `src/mcpack` + testler

## Özet

Tarama sırasında proje ~7.000 satır Python'du ve 176 test vardı, hepsi geçiyordu. Backend
(modeller, mod kaynakları, export, sunucu çalıştırma) iyi ayrılmıştı. Asıl zayıf noktalar
**arayüz katmanında**, **loglamada** (hiç yoktu) ve birkaç **güvenlik ayrıntısındaydı**.

Rapordan sonra masaüstü arayüzü ve web panelinin ön yüzü sıfırdan yeniden yazıldı, merkezi
bir loglama ve hata ayıklama sistemi eklendi. Aşağıdaki tablolardaki **Durum** sütunu her
maddenin şu anki halini gösterir.

| Durum | Anlamı |
|---|---|
| ✅ | Düzeltildi |
| ⏳ | Açık, henüz yapılmadı |

---

## 🔴 Kritik / Hata

| # | Sorun | Yer | Durum |
|---|---|---|---|
| 1 | **Loglama sistemi yoktu.** Hatalar sadece `traceback.print_exc()` ile terminale basılıyordu; paketlenmiş (konsolsuz) sürümde bu çıktı kayboluyor, çökme sonrası teşhis imkânsızdı. | `gui/widgets.py` | ✅ `logging_setup.py`: dönen log dosyası, bellek tamponu, crash raporu, istisna kancaları |
| 2 | **Thread güvenliği ihlali:** `progress_cb=self.set_progress` arka plan thread'inden doğrudan `QProgressBar`'a dokunuyordu. Bu, daha önce düzeltilen QPixmap çökmesiyle aynı sınıftan, rastgele çökmeye yol açabilecek bir hataydı. | `gui/main_window.py` | ✅ Yeni görev yöneticisi (`gui/tasks.py`): ilerleme sinyalle ve kısıtlanarak GUI thread'ine taşınıyor |
| 3 | **Komut enjeksiyonu:** Web panelinde oyuncu adı URL'den doğrudan konsol komutuna gömülüyordu (`kill {player}`). `%0A` ile ikinci, keyfi bir komut (ör. `op …`) çalıştırılabiliyordu. | `webpanel/app.py` | ✅ Oyuncu adı `^[A-Za-z0-9_]{1,16}$` ile doğrulanıyor (web + masaüstü) |
| 4 | **Port doluysa web paneli sessizce başarısız oluyordu.** Arayüz "başladı" diyordu ama sunucu ayağa kalkmamıştı. | `webpanel/app.py` | ✅ Önce açık hata verecek şekilde, ardından otomatik boş port seçecek şekilde düzeltildi (bkz. "Sonradan bildirilenler") |
| 5 | Kapatırken çalışan sunucular GUI thread'inde sırayla, her biri 15 sn'ye kadar bekletilerek durduruluyordu; bu sırada pencere donuyordu. | `gui/main_window.py` | ✅ Sunucular paralel thread'lerde durduruluyor |

## 🟠 Güvenlik

| Sorun | Durum |
|---|---|
| CurseForge API anahtarı ve web paneli şifresi `settings.json` içinde düz metin olarak duruyor (keyring kullanılabilir). | ✅ İşletim sistemi anahtar zinciri; düz metin değerler otomatik taşınır, dosya 0600 |
| Web paneli girişinde deneme sınırı yoktu, kaba kuvvetle şifre denemeye açıktı. | ✅ IP başına 5 dakikada 8 hatalı deneme, sonra HTTP 429 |
| Wurst/Meteor indirmelerinde hash doğrulaması yok. | ✅ İlk indirmede doğrulama (Wurst: GitHub SHA-256), hash'ler pack'e kaydediliyor |

## 🟡 Sağlamlık / Kod kalitesi

| Sorun | Durum |
|---|---|
| `save_pack` ve `Settings.save` atomik değil: yazma sırasında çökme olursa pack JSON'u bozulabilir. Çözüm: geçici dosyaya yazıp `os.replace` ile değiştirmek. | ✅ `fsutil.atomic_write_text` |
| Sürüm tutarsızdı: `__init__.__version__ = "0.1.0"`, User-Agent'ta `0.1.0`, gerçek sürüm 1.1.0. | ✅ Hepsi `mcpack.__version__` = 1.1.0 |
| `ServerProcess` bir `QObject`; backend Qt'ye bağımlı, web paneli Qt olmadan çalışamıyor. | ✅ Düz Python dinleyicileri; backend PySide6 olmadan import edilebiliyor (testli) |
| Oyuncu listesi her 4 sn'de bir koşulsuz `list` gönderip sunucu konsolunu ve loglarını kirletiyordu. | ✅ Sadece Oyuncular sekmesi açıkken yoklanıyor |
| `i18n.py` docstring'i var olmayan bir `i18n.js` dosyasına atıf yapıyordu. | ✅ |
| `main_window.py` 1.585 satırlık tek bir sınıftı; iş mantığı ile arayüz iç içeydi. | ✅ İş mantığı `gui/controller.py`'de, sayfalar `gui/pages/*` altında |
| Dışa aktarmada overrides klasörü seçilmezse sessizce çalışma dizinine (`Path.cwd()`) düşülüyordu; proje klasörü yanlışlıkla pakete girebiliyordu. | ✅ Artık açıkça soruluyor ("sadece modlar" / "klasör seç") |
| Aynı pack'in birden çok kopyası bellekte tutulabiliyor, arka plan görevi eski kopyayı kaydedip kullanıcının değişikliğini ezebiliyordu. | ✅ Denetleyicide pack başına tek canlı nesne (kimlik haritası) |

## 🟢 Eksik özellikler / Geliştirme önerileri

| Öneri | Durum |
|---|---|
| Mod güncelleme kontrolü | ✅ GUI (Modlar > ↑ Güncellemeleri Kontrol Et) + `mcpack-cli check-updates` |
| Dünya yedekleme | ✅ Sunucu > Yedekler: elle/otomatik, 'Hazırla' öncesi koruyucu yedek, güvenli geri yükleme; web paneli |
| `.mrpack` / CurseForge zip **içe aktarma** (şu an sadece dışa aktarma var) | ✅ Kütüphane > İçe Aktar, sürükle-bırak, `mcpack-cli import` |
| Mod silmede onay ve toplu seçim/silme | ✅ Çoklu seçim, onay, bağımlı modlar için ek uyarı |
| Görev geçmişi (hangi export ne zaman bitti/neden patladı) | ✅ Geliştirici > Görevler |
| Sistem teşhisi (Java, ağ erişimi, CF anahtarı, disk tek ekranda) | ✅ Geliştirici > Sistem > Teşhis |
| GUI testleri | ✅ Kısmen: çeviri anahtarı ve biçimlendirme testleri; widget testleri ⏳ |

---

## Yapılanlar (özet)

### Yeni masaüstü arayüzü (`src/mcpack/gui/`)
- Kenar çubuklu kabuk: Ana Sayfa, Kütüphane, Pack, Ayarlar, Geliştirici. **Ctrl+K** komut paleti, toast bildirimleri, kısayollar (Ctrl+N, Ctrl+F, F12, Ctrl+Shift+D).
- **Pack sayfası:** genel bakış ve bağımlılık sağlığı; çoklu seçimli, filtreli, sağ tık menülü mod tablosu; sayfaya gömülü **Keşfet** (mod/shader/kaynak paketi/datapack/dünya) ve sürüm seçici.
- **Sunucu paneli:** renkli konsol, seviye filtresi, vurgulamalı arama, komut otomatik tamamlama ve geçmişi, hızlı komutlar, toplu satır ekleme; oyuncu yönetimi; ham `server.properties` düzenleyicisi.
- **Ayarlar:** kartlar halinde, kaydedilmemiş değişiklik takibi, CurseForge/Java testleri, önbellek yönetimi, **varsayılanlara sıfırlama**.

### Loglama ve hata ayıklama
- Log dosyası: `~/.config/mcpack/logs/mcpack.log` (2 MB × 5), çökmelerde `logs/crash/crash-*.txt`.
- Yakalanmayan tüm istisnalar (ana thread, thread'ler, asyncio, unraisable), Qt uyarıları ve her HTTP isteği kaydediliyor. İstek başlıkları (CurseForge anahtarı) asla kaydedilmiyor.
- **Geliştirici sayfası (F12):** canlı loglar, görevler, ağ istekleri, istisnalar, sistem teşhisi, destek paketi (zip; gizli bilgiler maskeli), debug modunda Python konsolu.
- Debug modu: `mcpack --debug`, `MCPACK_DEBUG=1` ya da Ctrl+Shift+D.

### Web paneli
Ön yüz yeniden yazıldı ve mobil uyumlu. **Uygulama Logları** ve **Teşhis** sekmeleri eklendi. Seçili pack/sekme URL'de tutuluyor. Arka planda `/api/debug/*` uç noktaları, giriş deneme sınırı ve oyuncu adı doğrulaması eklendi.

---

## Sonradan bildirilenler ve düzeltmeler (aynı gün)

| Bildirim | Neden | Düzeltme |
|---|---|---|
| **Keşfet'te metinler kırpılıyordu** | Sonuç kartları liste genişliğinden geniş çiziliyordu (sağ taraf ve indirme sayısı kesiliyordu) ve sabit yükseklik 3 satırlık açıklamaları alttan kesiyordu. | Kart widget'ları yerine satırları doğrudan çizen bir delegate kullanılıyor: başlık ve iki satırlık açıklama gerçek genişliğe göre "…" ile kısaltılıyor, taşma yok. Kaynak, başlığın önünde renkli nokta olarak gösteriliyor (adı ipucunda). Daha hızlı da: satır başına widget oluşturulmuyor. |
| **Web paneli açılmıyordu** (`8765` ve `8080`: "adres zaten kullanımda") | Hata mcpack'te değil: `8765`'i başka bir projen (`cok-kapsamli-proje` → `python -m sistem servis`), `8080`'i Steam (`steamwebhelper`) kullanıyor. | Panel artık tercih edilen port doluysa sıradaki boş portu (en fazla 20 deneme) otomatik seçiyor ve portu kimin tuttuğunu bildiriyor, ör. *"8765 dolu (kullanan: python -m sistem servis) — panel 8766'da açıldı"*. Teşhis ekranı da portu kontrol ediyor. |
| Terminalde uzun traceback (CurseForge 403) | Geçersiz/iptal edilmiş CurseForge anahtarı bir program hatası değil, beklenen bir kullanıcı durumu. | Bu tür bilinen hatalar artık tek satırlık uyarı olarak loglanıyor. Tam traceback Görevler sekmesinde ve DEBUG logunda duruyor; İstisnalar sayacı sadece gerçek hataları sayıyor. **Not:** anahtarın kendisi hâlâ reddediliyor, console.curseforge.com'dan yeni anahtar gerekiyor. |
| Açılır kutularda ok kare görünüyordu | QSS'teki kenarlık üçgeni hilesi Fusion stilinde çalışmıyor. | SVG ok simgesi kullanılıyor (`assets/chevron-down.svg`). |
| **Ayarları sıfırlama özelliği istendi** | — | Ayarlar > **Varsayılanlara Sıfırla** (komut paletinde de var). İki seçenek: her şeyi sıfırla, ya da CurseForge anahtarı ve web paneli şifresini koruyarak sıfırla. Mevcut `settings.json` önce `settings.backup-<zaman>.json` olarak yedekleniyor; pack'lere dokunulmuyor. |

## Test durumu

189 test geçiyor. Bunlara yeni eklenenler: çeviri anahtarı bütünlüğü, biçimlendirme, ayar sıfırlama/yedekleme ve port tespiti testleri. Arayüz ekransız (offscreen) modda tüm sayfalarda gezilip ekran görüntüleriyle kontrol edildi. Web paneli Chrome'da masaüstü ve mobil genişlikte kontrol edildi.

## Açık kalanlar

Rapordaki önerilen 7 maddenin hepsi tamamlandı. Küçük kalanlar:
- Arayüz (widget) testleri: şimdilik ekransız duman testleri elle çalıştırılıyor; pytest'e taşınabilir.
- `PySide6` hâlâ zorunlu bağımlılık; backend artık Qt'siz çalışabildiği için ileride `pip install mcpack[gui]` gibi isteğe bağlı yapılabilir.

## İlerleme (12 Ekim 2026)

- ✅ 1. Atomik yazım · ✅ 2. Wurst/Meteor doğrulaması · ✅ 3. Anahtar zinciri · ✅ 4. Mod güncelleme kontrolü · ✅ 5. Modpack içe aktarma (gerçek bir paketle test edildi: Fabulously Optimized, 48/48 mod tanındı) · ✅ 6. Dünya yedekleme (gerçek 1.20.1 sunucusunda çalışırken yedek + geri yükleme test edildi)
- ✅ 7. `ServerProcess` Qt'den ayrıldı — önerilen 7 maddenin hepsi tamamlandı.
- Ek bulgu: `prepare_server`, seçili dünya varsa sunucunun mevcut `world/` klasörünü siliyordu — artık önce otomatik yedekleniyor.
- Ek: `mcpack-cli export` komutunun `content_root` eksikliği yüzünden çöktüğü fark edilip düzeltildi.
