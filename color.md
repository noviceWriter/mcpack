**Beyaz tema için canlı, çok renkli bir palet önerisi** (Minecraft mod paketi yöneticisi için).

Ana arka plan beyaz/çok açık gri tutularak modern ve temiz kalır, renkler ise vurgu, durum ve etkileşim için kullanılır. Tüm renkler yüksek kontrastlı ve erişilebilir olacak şekilde seçildi.

### Ana Renkler

| Renk Adı | Hex | RGB | Kullanım Yeri |
|----------|-----|-----|---------------|
| **Primary Blue** | `#2563EB` | 37, 99, 235 | Ana butonlar, aktif sekme, seçili öğe, linkler, “Yükle / Kur” butonu |
| **Accent Green** | `#16A34A` | 22, 163, 74 | Başarılı durumlar, “Kurulu” etiketi, onay butonları, progress bar tamamlandı |
| **Warning Orange** | `#F97316` | 249, 115, 22 | Uyarılar, “Güncelleme var”, bağımlılık uyarıları, orta seviye bildirimler |
| **Error / Danger Red** | `#DC2626` | 220, 38, 38 | Hata mesajları, “Kurulum başarısız”, silme / kaldırma butonları, kritik uyarılar |
| **Purple Accent** | `#7C3AED` | 124, 58, 237 | Premium / özel özellikler, “Öne çıkan modlar”, kategori etiketleri, filtreler |
| **Cyan / Info** | `#0891B2` | 8, 145, 178 | Bilgi mesajları, “Yeni sürüm”, ipuçları, tooltip’ler |
| **Pink / Magenta** | `#DB2777` | 219, 39, 119 | Favori / beğenilen modlar, “Popüler” etiketi, özel vurgular |

### Nötr + Destek Renkleri (Beyaz tema temeli)

| Renk Adı | Hex | Kullanım |
|----------|-----|----------|
| **Background** | `#FFFFFF` | Ana arka plan |
| **Surface / Card** | `#F8FAFC` | Kartlar, sidebar, paneller |
| **Border / Divider** | `#E2E8F0` | Çizgiler, kart kenarları |
| **Text Primary** | `#0F172A` | Ana metin |
| **Text Secondary** | `#64748B` | İkincil metin, açıklamalar |
| **Hover / Subtle** | `#F1F5F9` | Hover arka planı |
| **Disabled** | `#94A3B8` | Devre dışı öğeler |

### Önerilen Kullanım Haritası

- **Üst bar / Header**: Beyaz + Primary Blue logo/ikon + Text Primary
- **Sidebar**: Surface (`#F8FAFC`) + aktif menü Primary Blue arka plan + beyaz yazı
- **Mod kartları**: Beyaz kart + Border, hover’da hafif gölge + Primary Blue kenar
- **Durum etiketleri**:
  - Kurulu → Accent Green
  - Güncelleme var → Warning Orange
  - Hata / Uyumsuz → Error Red
  - Yeni / Öne çıkan → Purple veya Pink
- **Progress bar**: Primary Blue dolgu + hafif yeşil tamamlandığında
- **Butonlar**:
  - Birincil → Primary Blue
  - Başarı → Accent Green
  - Tehlikeli → Error Red
  - İkincil → Border + Text Primary
- **Bildirimler / Toast**: Sol kenarda ilgili renk şeridi (yeşil/turuncu/kırmızı/cyan)
- **Favori yıldızı / beğeni**: Pink / Magenta
- **Arama kutusu focus**: Primary Blue outline

### Notlar (Özellik varsa diye)

- Bu palet **sadece öneridir**. Programında şu anda beyaz tema, durum renkleri, etiketler veya özel vurgu renkleri yoksa bunları eklemen gerekir.
- Eğer zaten bir “tema motoru” veya CSS değişkenleri (CSS custom properties) kullanıyorsan, yukarıdaki renkleri `--color-primary`, `--color-success` vb. olarak tanımlamak en temiz yoldur.
- Koyu tema da planlıyorsan aynı renklerin koyu versiyonlarını ayrıca hazırlaman gerekir (şu an sadece beyaz tema için verildi).
- Minecraft hissiyatı için istersen Primary Blue’yu biraz daha “Minecraft mavisi”ne (`#3B82F6`) veya yeşili vanilla yeşiline yaklaştırabilirsin, ama yukarıdaki set daha modern ve okunaklıdır.

İstersen bu paleti doğrudan CSS değişkenleri olarak da yazabilirim veya belirli ekranlara (mod listesi, detay sayfası, kurulum sihirbazı vb.) göre daha detaylı yerleşim önerebilirim.