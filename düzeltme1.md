# MC Pack Manager - Renk Paleti ve Tasarım Sistemi Önerisi

Mevcut arayüzdeki en büyük sorun, sert kontrastlar (koyu lacivert seçim) ve soluk metinlerdir. Bu belge, uygulamayı daha modern, profesyonel ve göz yormayan bir hale getirecek renk paletini içerir.

---

## 1. Temel Renk Paleti (Modern & Yumuşak Tema)

Uygulamanın genel havasını belirleyen ana renklerdir. "Material Design 3" veya "Tailwind CSS" standartlarına yakındır.

| Kullanım Amacı | Renk Adı | Hex Kodu | Görsel Açıklama |
| :--- | :--- | :--- | :--- |
| **Ana Arka Plan (Body)** | Açık Gri/Beyaz | `#F8F9FA` | Sayfanın tamamen beyaz olması gözü yorar. Çok hafif gri bir ton derinlik katar. |
| **Kart/Panel Arka Planı** | Saf Beyaz | `#FFFFFF` | Liste öğeleri ve paneller için kullanılır. |
| **Ana Vurgu Rengi (Primary)** | Canlı Mavi | `#3B82F6` | "Yeni Pack" ve "Export Et" gibi ana butonlar için. (Mevcut maviye göre daha canlı ve modern). |
| **Ana Metin Rengi** | Koyu Antrasit | `#1F2937` | Saf siyah (`#000000`) yerine kullanılmalı. Daha yumuşak bir okuma sağlar. |
| **İkincil Metin (Soluk)** | Orta Gri | `#6B7280` | "34 mod", "MC 1.20.1" gibi detay metinleri için. (Mevcut gri çok soluk, bu daha okunaklı). |
| **Kenarlık (Border)** | Açık Gri | `#E5E7EB` | Panelleri ve butonları ayırmak için ince çizgiler. |

---

## 2. Sol Menü (Liste) İyileştirmesi

Mevcut durumda seçili öğe (Forge) koyu lacivert (`#1E3A8A` civarı) ve üzerindeki yazı beyaz. Bu çok sert bir kontrast.

**Önerilen Yeni Stil:**
*   **Normal Öğe Arka Planı:** `#FFFFFF` (Beyaz)
*   **Normal Öğe Metni:** `#1F2937` (Koyu Antrasit)
*   **Seçili Öğe Arka Planı (Active):** `#EFF6FF` (Çok açık, yumuşak mavi)
*   **Seçili Öğe Metni:** `#1D4ED8` (Koyu Mavi - okunaklı)
*   **Seçili Öğe Sol Şerit (Indicator):** Öğenin sol kenarına 4px kalınlığında `#3B82F6` (Canlı Mavi) bir şerit çekilmeli. Bu, listede nerede olduğunuzu gösterir ve lacivert bloğa gerek kalmaz.
*   **Hover (Üzerine Gelme) Rengi:** `#F3F4F6` (Çok açık gri)

*Görsel Mantık:* Kullanıcı listede gezerken gözü yormaz, seçili olduğunu sol taraftaki mavi şeritten ve hafif mavi arka plandan anlar.

---

## 3. Buton Renkleri

Butonların öncelik sırasına göre renkleri netleştirilmeli.

*   **Birincil Buton (Örn: "Yeni Pack", "Export Et"):**
    *   Arka Plan: `#3B82F6` (Canlı Mavi)
    *   Metin: `#FFFFFF` (Beyaz)
    *   Hover (Üzerine Gelince): `#2563EB` (Biraz daha koyu mavi)
*   **İkincil Buton (Örn: "Server Pack", "SKLauncher"):**
    *   Arka Plan: `#FFFFFF` (Beyaz)
    *   Kenarlık: `#D1D5DB` (Gri)
    *   Metin: `#374151` (Koyu Gri)
    *   Hover: Arka plan `#F9FAFB` olur, kenarlık `#9CA3AF` olur.
*   **Tehlike/İptal Butonu (Örn: "İptal"):**
    *   Metin: `#EF4444` (Kırmızı)
    *   Arka Plan: Şeffaf

---

## 4. Metin ve Bilgilendirme Alanları (UX Düzeltmesi)

Sayfanın ortasındaki soluk yazılar için renk önerisi:

*   **Uyarı Metni ("Vanilla pack'lerde mod eklenemez..."):**
    *   Şu anki hali: Soluk gri, kaybolmuş.
    *   *Öneri:* Arka planı `#FEF3C7` (Açık Sarı), metin rengi `#92400E` (Koyu Kahverengi/Turuncu) olan bir kutu içine alınmalı. Bu bir "bilgi" kutusudur, dikkat çekmelidir.
*   **Sıralama Metni ("Sıralamak için sütun başlığına tıkla"):**
    *   *Öneri:* Metin rengi `#6B7280` (Orta Gri) yapılmalı, böylece beyaz arka planda daha okunaklı olur.

---

## 5. Özet Karşılaştırma (Eski vs Yeni)

| Alan | Eski Renk (Sorunlu) | Yeni Renk (Önerilen) |
| :--- | :--- | :--- |
| **Seçili Liste Öğesi** | Koyu Lacivert (#1E3A8A) | Açık Mavi Arka Plan (#EFF6FF) + Sol Mavi Şerit |
| **Ana Buton** | Standart Mavi | Canlı Mavi (#3B82F6) |
| **İkincil Metin** | Çok Soluk Gri | Orta Gri (#6B7280) |
| **Sayfa Arka Planı** | Saf Beyaz | Açık Gri (#F8F9FA) |
| **Uyarı Metni** | Soluk Gri | Sarı Kutu + Koyu Turuncu Metin |

Bu renk paleti uygulandığında arayüz hem daha modern görünecek hem de kullanıcının gözünü yormayacaktır.