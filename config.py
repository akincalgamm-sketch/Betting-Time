"""
Web sürümü yapılandırması. Telegram token'a ihtiyaç yok, sadece API-Sports
anahtarı gerekiyor.
"""
import os
from dotenv import load_dotenv

load_dotenv()

API_SPORTS_KEY = os.getenv("API_SPORTS_KEY", "")
PORT = int(os.getenv("PORT", "8000"))

SPORT_HOSTS = {
    "futbol": "v3.football.api-sports.io",
    "basketbol": "v1.basketball.api-sports.io",
}

SPORT_BASE_URLS = {
    sport: f"https://{host}" for sport, host in SPORT_HOSTS.items()
}

if not API_SPORTS_KEY:
    print("UYARI: API_SPORTS_KEY tanımlı değil. .env dosyasını kontrol et.")
