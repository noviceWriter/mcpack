# Katkıda Bulunma Rehberi

mcpack'e katkı göstermek istediğiniz için teşekkürler! Bu belge, projeye
katkı sağlarken izlenecek pratik adımları ve beklentileri özetler.

## 1. Geliştirme Ortamını Kurma

Proje Python 3.11+ ve PySide6 üzerine kurulu. `README.md`'deki kurulum
adımlarıyla aynı:

```bash
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

Bu komut `pytest`, `pytest-asyncio` ve `respx` gibi geliştirme
bağımlılıklarını da kurar (bkz. `pyproject.toml` içindeki `[project.optional-dependencies].dev`).

Uygulamayı çalıştırmak için:

```bash
mcpack            # GUI
mcpack-cli --help # CLI
```

## 2. Testleri Çalıştırma

Değişiklik göndermeden önce test paketinin tamamının geçtiğinden emin olun:

```bash
pytest
```

Testler `tests/` klasöründe, gerçek ağ isteği atmadan `respx` ile
Modrinth/CurseForge API'lerini mock'layarak çalışır (bkz. `tests/test_modrinth.py`,
`tests/test_curseforge.py`). Yeni bir özellik veya bug fix eklerken:

- Davranışı değiştiren her PR için en az bir test ekleyin veya güncelleyin.
- Dış API'lere gerçek istek atan test yazmayın — mevcut testlerdeki `respx`
  mock kalıplarını örnek alın.
- Async kod için `pytest-asyncio` zaten `asyncio_mode = "auto"` ile
  yapılandırılmış (`pyproject.toml`); `async def test_...` fonksiyonları
  ekstra dekoratör gerektirmez.

## 3. Kod Kuralları

Kod tabanını incelerken göze çarpan yerleşik kurallar:

- **Türkçe docstring ve yorumlar.** Modül/sınıf/fonksiyon docstring'leri ve
  kod içi yorumlar Türkçe yazılıyor; kullanıcıya dönük arayüz metinleri de
  Türkçe (bkz. `proje-amacı.md` §6: "Türkçe arayüz tercih edilir").
- **Tip belirteçleri (type hints) zorunlu gibi düşünün.** Modeller
  `pydantic.BaseModel`, enum'lar `StrEnum` üzerinden tanımlanıyor
  (`src/mcpack/models.py`). Fonksiyon imzalarında parametre/dönüş tipleri
  belirtiliyor, `from __future__ import annotations` üstte kullanılıyor.
- **`pathlib.Path` tercih edilir**, ham string yol birleştirme yerine.
- **Modüler yapı korunur:** `sources/` (Modrinth/CurseForge client'ları),
  `packs/` (pack yaşam döngüsü), `export/` (format bazlı export motorları),
  `gui/` (PySide6 arayüzü) birbirinden ayrı sorumluluklara sahip; yeni kod
  bu ayrımı bozmadan ilgili modüle eklenmeli.
- Repoda henüz otomatik bir linter/formatter (ruff, black vb.)
  yapılandırılmamış; mevcut dosyalardaki stile (girinti, import sıralaması,
  satır uzunluğu) sadık kalmak yeterli. Katkınızda bir linter/formatter
  önerisi varsa, ayrı bir PR'da tartışmaya açabilirsiniz.

## 4. Commit ve PR Süreci

- Commit mesajlarını kısa, açıklayıcı ve Türkçe yazın (`git log` geçmişindeki
  stile bakabilirsiniz — ör. "Dünya araması sonuçları hiç göstermiyordu; boş
  durumda CF arama butonu ekle").
- Bir PR'ı mümkün olduğunca tek bir konuya odaklayın; ilgisiz değişiklikleri
  ayrı PR'lara bölün.
- PR açıklamasında neyi, neden değiştirdiğinizi kısaca yazın; davranış
  değişikliği varsa nasıl test ettiğinizi belirtin.
- CI/otomatik kontrol yoksa bile PR'ı göndermeden önce yerelde `pytest`
  çalıştırdığınızdan emin olun.
- Büyük bir özellik eklemeden önce (özellikle yeni bir export formatı, yeni
  bir mod kaynağı vb.) bir Issue açıp yaklaşımınızı tartışmanız, boşa emek
  harcamanızı önler.

## 5. Lisans ve Katkılarınız Üzerindeki Haklar

mcpack, **GNU Affero General Public License v3.0 (AGPL-3.0)** ile
lisanslanmıştır (bkz. `LICENSE`). Bu projeye bir pull request, patch veya
başka bir katkı gönderdiğinizde:

- Katkınızın projenin geri kalanıyla aynı şekilde **AGPL-3.0 altında
  lisanslanmasını kabul etmiş** olursunuz.
- Bu, çoğu açık kaynak projesinde kullanılan standart ve yaygın "inbound =
  outbound" varsayımıdır: projeye giren katkı (inbound), projeden çıkan
  lisansla (outbound) aynı koşullarda kabul edilir. Bu, ayrı bir Katkıda
  Bulunan Lisans Sözleşmesi (CLA) imzalamanızı **gerektirmez** — sadece
  katkınızı bu projenin lisansı altında sunduğunuzu ifade eder.
- Katkının size ait olduğundan veya gönderme hakkınız olduğundan emin olun
  (örn. başka bir projeden lisansı uyumsuz kod kopyalamayın).

Sorularınız için bir Issue açabilir veya proje sahibiyle GitHub üzerinden
iletişime geçebilirsiniz. İyi kodlamalar!
