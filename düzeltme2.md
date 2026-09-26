# MC Pack Manager - Arayüz İyileştirme ve Düzeltme Notları

Bu belge, "MC Pack Manager" uygulamasının mevcut kullanıcı arayüzü (UI) ve kullanıcı deneyimi (UX) üzerine yapılan incelemeler sonucunda tespit edilen eksiklikleri ve düzeltilmesi gereken noktaları içermektedir.

---

## 1. Dil Tutarlılığı (Localization)
Arayüzde İngilizce ve Türkçe terimler karışık olarak kullanılmaktadır. Uygulamanın tamamen Türkçe (veya seçili dile göre) tek bir dilde hizmet vermesi sağlanmalıdır.

*   **Mevcut Durum:** Sol üstte "Pack'ler", sağ üstte "Export Et", alt tarafta "Yeni Pack" yazarken; sağ üstteki butonlarda "Server Pack" ve "SKLauncher" gibi İngilizce terimler kalmış.
*   **Öneri:** 
    *   "Export Et" -> **"Dışa Aktar"** olarak değiştirilmeli.
    *   "Server Pack" -> **"Sunucu Paketi"** olarak değiştirilmeli.
    *   "SKLauncher" bir özel isim olduğu için kalabilir ancak yanına Türkçe açıklama eklenebilir.
    *   Tüm buton ve metinler için bir çeviri (i18n) altyapısı kurulmalı.

## 2. Görsel Hiyerarşi ve Renk Kullanımı
*   **Seçili Öğe (Active State) Kontrastı:** Sol taraftaki listede seçili olan "Forge - MC 1.20.1" öğesinin arka planı çok koyu lacivert yapılmış. Bu durum açık tema ile sert bir kontrast oluşturarak göz yormaktadır.
    *   *Öneri:* Seçili öğe için daha yumuşak bir vurgu rengi (örneğin açık mavi bir arka plan veya sol tarafa ince bir renk şeridi) kullanılmalı.
*   **İkon Kullanımı:** Sol taraftaki "V" (Vanilla) ve "F" (Forge) harfleri yerine görsel ikonlar kullanılmalı.
    *   *Öneri:* Vanilla için çimen bloğu, Forge için örs ikonu gibi görsel ikonlar kullanmak listedeki öğelerin daha hızlı ayırt edilmesini sağlar.

## 3. Buton Yerleşimi ve Önceliklendirme
*   **Buton Hiyerarşisi:** Sağ üstteki "Export Et" butonu mavi ve dikkat çekiciyken, "Server Pack" ve "SKLauncher" butonları sönük kalmış. "Yeni Pack" butonu ise sol altta tam genişlikte duruyor.
    *   *Öneri:* Ana eylemler (Yeni Pack, Export Et) için renk paletinde tutarlılık sağlanmalı. İkincil eylemler (Server Pack, SKLauncher) için "outline" (çerçeveli) buton stili kullanılabilir.

## 4. Metin ve Bilgilendirme Alanları
*   **Orta Alan Metni:** Sayfanın ortasında yer alan "Vanilla pack'lerde mod eklenemez..." yazısı çok soluk (gri) ve sayfanın ortasında kaybolmuş durumda.
    *   *Öneri:* Eğer bu bir uyarıysa, bir uyarı ikonu ile birlikte daha görünür bir kutu içine alınmalı. Eğer bir bilgi notuysa, yazı boyutu biraz büyütülmeli ve rengi koyulaştırılmalı.
*   **Sıralama Metni:** "Sıralamak için sütun başlığına tıkla ↓" yazısı da çok soluk.
    *   *Öneri:* Kullanıcıyı yönlendirmek için metin rengi koyulaştırılmalı veya yanına küçük bir bilgi ikonu eklenmeli.

## 5. Boşluk Kullanımı (Whitespace) ve "Call to Action"
*   **Boş Durum (Empty State):** Sağ taraftaki büyük beyaz alan (mod listesinin olduğu yer) şu an tamamen boş. Sayfa yarım kalmış gibi duruyor.
    *   *Öneri:* Eğer seçili pack'te hiç mod yoksa, buraya bir "Henüz mod eklenmemiş" görseli veya "Mod Ekle" butonu gibi bir "Call to Action" (Eylem Çağrısı) eklenmeli.

## 6. Teknik ve Fonksiyonel Detaylar
*   **Versiyon Bilgisi:** "Forge - MC 1.20.1 - 34 mod" yazıyor. Buradaki "34 mod" kısmı küçük bir etiket (badge) haline getirilirse daha okunaklı olur.
*   **Sağ Üst Menü:** Sağ üstteki "Ayarlar" butonu bir dişli ikonu ile desteklenebilir. Ayrıca sağ üstteki pencere kontrol butonları (kapat, küçült) ile "Ayarlar" butonu çok yakın duruyor, araya biraz boşluk konulmalı.

---
**Öncelik Sırası:**
1. Dil birliğinin sağlanması (Localization)
2. Seçili öğe renginin göz yormayacak şekilde yumuşatılması
3. Boş alanlar için "Call to Action" eklenmesi