# Katkıda Bulunma

Bu proje şu an tek bir geliştirici tarafından yürütülüyor. Yine de açık
kaynak olduğu için hata bildirimi, öneri ya da pull request göndermek
isteyen olursa diye kısa bir yol haritası:

## Hata bildirmek / öneri sunmak

En kolay yol: [GitHub Issues](https://github.com/noviceWriter/mcpack/issues)
üzerinden yeni bir issue açmak. Bir hata bildiriyorsanız, ne yaptığınızı,
ne beklediğinizi ve ne olduğunu kısaca yazmanız yeterli.

## Kod göndermek isterseniz

1. Depoyu fork'layın, bir dal (branch) açın.
2. Geliştirme ortamını kurun:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate       # Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```
3. Değişikliğinizi yapın, testleri çalıştırın:
   ```bash
   pytest
   ```
4. Pull request açın, ne değiştirdiğinizi kısaca açıklayın.

Özel bir kod stili zorunluluğu yok — mevcut dosyalardaki üsluba
(Türkçe docstring/yorum, `pathlib.Path`, tip belirteçleri) uymanız yeterli.

## Lisans notu

Gönderdiğiniz katkı, projenin lisansı olan **AGPL-3.0** altında
yayınlanmış sayılır (açık kaynak projelerde standart varsayım — ayrı bir
sözleşme imzalamanız gerekmez).
