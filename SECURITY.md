# Güvenlik Politikası

## Kapsam

Bu politika yalnızca **mcpack (MC Pack Manager)** uygulamasının kendi kodunu
kapsar (bu depodaki `src/mcpack` altındaki uygulama, CLI ve GUI).

mcpack; Mojang/Microsoft (Minecraft), CurseForge/Overwolf veya Modrinth ile
bağlantılı, onlar tarafından desteklenen veya onaylanan resmi bir araç
**değildir**. Bu bağımsız, resmi olmayan bir üçüncü taraf istemci
uygulamasıdır ve yalnızca bu API'leri kamuya açık şekilde tükettiği için bu
servislerle etkileşime girer. Modrinth API'si, CurseForge API'si, Minecraft
istemcisi/sunucusu veya SKLauncher gibi harici sistemlerdeki güvenlik açıkları
bu politikanın kapsamı dışındadır; bu tür sorunlar ilgili projelere/şirkete
bildirilmelidir.

## Bir Güvenlik Açığı Bildirme

mcpack'te bir güvenlik açığı bulduğunuzu düşünüyorsanız, lütfen **önce genel
bir GitHub Issue açarak açığı herkese açık şekilde paylaşmayın.** Bunun
yerine, mümkünse aşağıdaki yollardan birini tercih edin:

1. **Tercih edilen yöntem:** Depoda GitHub Security Advisories özelliği
   etkinse, "Security" sekmesinden özel bir güvenlik danışma bildirimi
   (private security advisory) açarak raporlayın. Bu, detayların düzeltme
   yayınlanana kadar sizinle proje sahibi arasında kalmasını sağlar.
2. **Alternatif:** GitHub Security Advisories bu depoda henüz
   yapılandırılmamışsa veya erişemiyorsanız, bir GitHub Issue açabilirsiniz —
   ancak bu durumda açığın istismar edilmesini kolaylaştıracak ayrıntıları
   (ör. hazır saldırı kodu) paylaşmaktan kaçının; genel bir açıklama ve proje
   sahibiyle özel olarak iletişime geçme talebi yeterlidir.

Lütfen raporunuza mümkün olduğunca şunları ekleyin:

- Açığın kısa bir açıklaması ve potansiyel etkisi
- Yeniden üretme adımları (mümkünse minimal bir örnekle)
- Etkilenen sürüm/commit ve ortam bilgisi (işletim sistemi, Python sürümü vb.)

## Ne Beklenmeli

Bu proje bir hobi projesi olarak tek bir geliştirici tarafından
sürdürülmektedir; profesyonel bir SLA (hizmet seviyesi taahhüdü)
verilmemektedir. Buna rağmen, bildirilen güvenlik sorunlarına makul bir
sürede geri dönüş yapılmaya çalışılacaktır.

## Sorumlu Açıklama (Responsible Disclosure)

Bir düzeltme yayınlanana veya proje sahibiyle karşılıklı olarak makul bir
süre üzerinde anlaşılana kadar açığı kamuya açık şekilde ifşa etmemenizi
rica ediyoruz. Bu süre boyunca sorunu kötüye kullanmamanızı ve yalnızca
sorunu doğrulamak için gerekli olan minimum işlemi yapmanızı bekliyoruz.
Düzeltme yayınlandıktan sonra, isterseniz bulduğunuz açığı (ve varsa
adınızı) kamuya açıklayabilirsiniz — bunu yaparken proje sahibiyle önceden
koordinasyon kurmanız rica olunur.

## Kapsam Dışı Örnekler

Aşağıdakiler genellikle bu proje için güvenlik açığı olarak
değerlendirilmez, ancak yine de bir Issue üzerinden bildirebilirsiniz:

- Kullanıcının kendi `settings.json` dosyasına kaydettiği CurseForge API
  anahtarının, kullanıcının kendi dosya sistemi izinlerini yanlış
  yapılandırmasından kaynaklanan ifşası
- Modrinth/CurseForge tarafında sağlanan içeriğin (mod dosyaları vb.)
  kötü amaçlı olması — mcpack indirdiği dosyaların hash doğrulamasını yapar,
  ancak dosya içeriğinin güvenliğini garanti edemez
