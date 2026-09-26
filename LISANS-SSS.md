# Lisans SSS (Sıkça Sorulan Sorular)

> **Bu belge hukuki tavsiye değildir; sadece AGPL-3.0'ı anlamayı
> kolaylaştırmak için yazılmıştır. Ciddi bir hukuki anlaşmazlık durumunda
> gerçek bir avukata danışın.**

Bu belge, mcpack'in neden AGPL-3.0 ile lisanslandığını ve bunun pratikte
ne anlama geldiğini, hukuk diline girmeden, sade bir dille açıklamak için
yazıldı. Tam ve bağlayıcı metin her zaman depodaki `LICENSE` dosyasıdır;
burada bir çelişki olursa `LICENSE` dosyası geçerlidir.

## mcpack nedir, kime ait?

mcpack, Modrinth/CurseForge'tan mod arama, pack oluşturma ve
`.mrpack`/CurseForge/Prism formatlarında export gibi işleri yapan bağımsız
bir Minecraft mod paket yöneticisi aracıdır. **mcpack; Mojang/Microsoft
(Minecraft), CurseForge/Overwolf veya Modrinth ile bağlantılı, onlar
tarafından desteklenen veya onaylanan resmi bir ürün değildir.** Bu araç
sadece onların kamuya açık API'lerini kullanan bağımsız, resmi olmayan bir
istemcidir.

## AGPL-3.0 ne demek, kısaca?

mcpack, **GNU Affero General Public License v3.0 (AGPL-3.0)** ile
lisanslanmıştır. Bu, gerçek, OSI onaylı (Open Source Initiative tarafından
tanınan) bir açık kaynak lisansıdır — uydurma veya "yarı açık kaynak" bir
lisans değildir.

Basitleştirilmiş özet:

- **Kullanabilirsiniz.** mcpack'i indirip istediğiniz gibi kullanabilirsiniz.
- **Değiştirebilirsiniz.** Kodu inceleyip kendi ihtiyacınıza göre
  değiştirebilirsiniz.
- **Satabilirsiniz.** Evet, AGPL ticari kullanımı yasaklamaz. mcpack'i veya
  değiştirilmiş bir sürümünü satabilir, ücretli bir hizmet olarak
  sunabilirsiniz.
- **Ama:** mcpack'in değiştirilmiş bir sürümünü **dağıtırsanız** (ör. bir
  .exe/kurulum paketi olarak insanlara verirseniz) **veya** onu bir **ağ
  servisi olarak** (ör. bir web sitesi/SaaS üzerinden insanların uzaktan
  kullanmasını sağlayarak) çalıştırırsanız, o değiştirilmiş sürümün kaynak
  kodunu da **aynı AGPL-3.0 lisansı altında, kullanıcılara/kullanıcıların
  erişebileceği şekilde** açmanız gerekir.

Bu son madde, AGPL'yi normal GPL'den ayıran şeydir: GPL'de biri kodu alıp
değiştirip bunu kendi sunucusunda çalıştırıp hiç kimseye kaynak kodu
vermeden bir SaaS ürünü haline getirebilir (buna bazen "SaaS açığı" ya da
"ASP açığı" denir). AGPL bu boşluğu kapatır: kod sadece indirilip
kurulduğunda değil, bir ağ üzerinden hizmet olarak sunulduğunda da kaynağın
paylaşılmasını zorunlu kılar.

## "Ticari kullanım serbest ama..." çelişkili değil mi?

Değil — bu AGPL'nin gerçek ve kasıtlı dengesidir, bir eksiklik değildir:

- **Yasak olan şey ticaret değil, kapalı kaynak yeniden dağıtımdır.**
  Biri mcpack'i alıp üzerine özellik ekleyip bunu **ücretli** bir ürün
  olarak satabilir — bu tamamen yasaldır. Ama bunu yaparken, değiştirilmiş
  kaynak kodunu da AGPL-3.0 altında müşterilerine/kullanıcılarına açmak
  **zorundadır**.
- Yani biri mcpack'i alıp, rebrand edip (adını değiştirip), kapalı
  kaynak, "sırrı bizde kalsın" tarzı bir ürün olarak satamaz. Bunu yapmaya
  kalkarsa, lisansı ihlal etmiş olur ve telif hakkı sahibi (proje
  sahibi) bunun düzeltilmesini (ya kaynağı açmasını ya da dağıtımı
  durdurmasını) talep edebilir.
- Kısacası: **"para kazanma" serbest, "kaynağı gizleyerek para kazanma"
  serbest değil.**

## AGPL'nin koruyamadığı şeyler (dürüst sınırlar)

AGPL kodun **kendisini** (yani onun somut, yazılmış ifadesini) korur —
"Minecraft mod paketi yöneticisi yapma **fikrini**" değil. Yani:

- Biri mcpack'in kaynak koduna hiç bakmadan, sıfırdan kendi kodunu yazarak
  benzer bir mod paketi yöneticisi geliştirip bunu kapalı kaynak, ücretli
  bir ürün olarak satabilir. **Bu bir lisans ihlali değildir** — çünkü
  mcpack'in kodunu kullanmamıştır, sadece benzer bir fikri bağımsız olarak
  uygulamıştır.
- AGPL, "bu tür bir yazılım kimse yapamasın" demez; sadece "**bu belirli
  kod tabanını** alıp kapalı kaynak olarak dağıtamazsın/sunamazsın" der.
- Dolayısıyla lisans, rekabeti tamamen engellemez; sadece bu spesifik
  kodun kapalı kaynak bir türevinin dağıtılmasını/sunulmasını engeller.
  Bunun ötesinde iddialarda bulunmak yanıltıcı olur — bu belge de öyle bir
  iddiada bulunmuyor.

## Katkıda bulunursam ne olur?

Projeye pull request gönderirseniz, katkınızın da AGPL-3.0 altında
lisanslanmasını kabul etmiş olursunuz (bkz. `CONTRIBUTING.md`). Bu, ayrı bir
sözleşme (CLA) imzalamanızı gerektirmeyen, çoğu açık kaynak projesinde
kullanılan standart bir varsayımdır.

## Daha fazla bilgi

- Tam, bağlayıcı lisans metni: [`LICENSE`](./LICENSE) dosyası (resmi
  Free Software Foundation AGPL-3.0 metni).
- Resmi AGPL-3.0 SSS'si (İngilizce): https://www.gnu.org/licenses/gpl-faq.html
- Lisansın resmi kaynağı: https://www.gnu.org/licenses/agpl-3.0.html

---

> **Tekrar hatırlatma: Bu belge hukuki tavsiye değildir; sadece AGPL-3.0'ı
> anlamayı kolaylaştırmak için yazılmıştır. Ciddi bir hukuki anlaşmazlık
> durumunda gerçek bir avukata danışın.**
