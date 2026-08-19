# Maç Analiz — Web Uygulaması

Telegram'a gerek yok: telefonun tarayıcısından açıp kullanacağın, futbol ve
basketbol için maç öncesi çok faktörlü analiz sunan mobil web uygulaması.

Analiz motoru (form, ev/deplasman, head-to-head, sıralama, gol averajı,
dinlenme günü, sakatlık, bahis oranları) Telegram bot sürümüyle birebir
aynı — sadece arayüz Telegram yerine bir web sitesi.

## 1. Gereksinimler
- Python 3.10+
- Ücretli [api-sports.io](https://api-sports.io) hesabı (sakatlık/oran verisi için)

## 2. Kurulum

```bash
cd mac_analiz_web
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

`.env` dosyasını aç, `API_SPORTS_KEY` değerini kendi anahtarınla değiştir.

## 3. Yerel olarak çalıştırma (bilgisayarda test için)

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

Tarayıcıda `http://localhost:8000` adresine git.

## 4. Telefondan erişebilmek için: buluta deploy et

Telefonun tarayıcısından her yerden erişmek için siteyi Railway'e (ya da
benzeri bir servise) yükle — aynı Telegram bot kurulumunda izlediğin adımlar:

1. Bu klasördeki dosyaları bir GitHub reposuna yükle (`.env` **hariç**)
2. [railway.app](https://railway.app) → GitHub ile giriş yap
3. "New Project" → "Deploy from GitHub repo" → reponu seç
4. "Variables" sekmesine `API_SPORTS_KEY` değişkenini ekle
5. "Settings" → "Start Command" kısmına şunu yaz:
   ```
   uvicorn main:app --host 0.0.0.0 --port $PORT
   ```
6. Deploy tamamlanınca Railway sana bir `https://...up.railway.app` adresi
   verecek — bu adresi telefonunda tarayıcıdan aç.

## 5. Ana ekrana ekleyip uygulama gibi kullanma

Railway adresini telefonda Chrome'da açtıktan sonra:
- Chrome menüsü (⋮) → **"Ana ekrana ekle"**
- Artık telefonunda gerçek bir uygulama gibi ikon olur, tam ekran açılır
  (adres çubuğu görünmez), Telegram'a hiç gerek kalmaz.

iPhone/Safari kullanıyorsan: Paylaş butonu → **"Ana Ekrana Ekle"**.

## 6. Nasıl çalışıyor?

- `main.py`: FastAPI sunucusu. İki uç nokta:
  - `GET /api/fixtures?sport=futbol` — bugünün maçları
  - `GET /api/analyze?sport=futbol&fixture_id=123` — tam analiz (JSON)
- `sports_api.py` / `analysis.py`: Telegram bot sürümüyle birebir aynı analiz
  motoru (7 faktörlü model + piyasa oranı harmanlaması).
- `static/index.html`: Tek sayfalık mobil arayüz — maç listesi ve analiz
  ekranını gösterir, sunucudaki API'leri çağırır.
- `static/manifest.json` + `icon.svg`: "Ana ekrana ekle" ile uygulama gibi
  görünmesini sağlar (PWA).

## 7. Not

- Gerçek bir Android/iOS mağaza uygulaması (APK/IPA) değildir — bu, native
  uygulama derleme araçları (Android Studio, Xcode, imzalama sertifikaları)
  gerektirir ve bu ortamda üretilemez. Web uygulaması pratikte aynı deneyimi
  verir (ikon, tam ekran, hızlı erişim) ama mağazadan indirilmez.
- Aynı analiz motoru olduğu için Telegram bot ile web uygulamasını **aynı
  anda** da çalıştırabilirsin — istersen ikisini de aynı Railway hesabında
  iki ayrı proje olarak barındırabilirsin.
