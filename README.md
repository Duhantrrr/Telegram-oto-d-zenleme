# Telegram Panel (FastAPI)

Web panelinden Telegram hesabınıza girersiniz (kod + varsa iki adımlı şifre).
Hesabınızdan gönderdiğiniz bir mesaj bir kuralla birebir aynıysa (ör. `ads`, `done`)
anında sizin belirlediğiniz metne çevrilir.

## Render'a kurulum (önerilen)
1. Bu klasörü bir GitHub deposuna yükleyin (`.env` dosyasını yüklemeyin).
2. Render → New → Blueprint → depoyu seçin (`render.yaml` otomatik okunur).
3. Ortam değişkenlerini girin:
   - `API_ID`, `API_HASH` → my.telegram.org
   - `PANEL_PASSWORD` → panel şifreniz
   - `PHONE` → `+905315151419` (isteğe bağlı, kutu dolu gelir)
4. Siteyi açın → panel şifresi → numara → **Kod gönder** → Telegram'a gelen kodu girin.
5. Giriş sonrası **Oturum anahtarını göster** → değeri Render'da `SESSION_STRING` olarak kaydedin.
   Kuralları ekledikten sonra **Kuralları kopyala** → `RULES_JSON` olarak kaydedin.
   Böylece sunucu yeniden başlasa da giriş ve kurallar kaybolmaz.

Not: Render Free plan 15 dk ziyaret olmazsa uyur ve o sırada mesajlar düzenlenmez.
Sürekli çalışması için Starter plan kullanın.

## Vercel hakkında
Vercel istek bitince sunucuyu kapatır; Telegram'ı sürekli dinlemek gerektiği için
otomatik düzenleme orada çalışmaz. Bu yüzden Render kullanın.

## Yerelde çalıştırma
```
pip install -r requirements-dev.txt
cp .env.example .env   # değerleri doldurun ve ortamınıza yükleyin
uvicorn app.main:app --port 8000
pytest -q
```
