import os
from dotenv import load_dotenv

# .env dosyasını yükle (Render veya lokal geliştirme için)
load_dotenv()

class Config:
    # -----------------------
    # Flask Genel Ayarlar
    # -----------------------
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_key")

    # -----------------------
       # Güvenlik — Cron Secret
    # -----------------------
    # Cron job isteklerini doğrulamak için gizli anahtar
    CRON_SECRET = os.getenv("CRON_SECRET", "SET_YOUR_CRON_SECRET")

    # -----------------------
    # Veritabanı Ayarları
    # -----------------------
    # Render veya lokal DB connection string
    DB_URL = os.getenv("DB_URL", "postgresql://username:password@localhost:5432/habersel")

    # -----------------------
    # API Key'ler (placeholder)
    # -----------------------
    GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "CHANGE_ME")
    CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY", "CHANGE_ME")
    NEWSAPI_AI_KEY = os.getenv("NEWSAPI_AI_KEY", "CHANGE_ME")
    MEDIASTACK_KEY = os.getenv("MEDIASTACK_KEY", "CHANGE_ME")
    NEWSDATA_KEY = os.getenv("NEWSDATA_KEY", "CHANGE_ME")

    # -----------------------
    # Haber Sistem Ayarları
    # -----------------------
    # Kaç gün geriye dönük haber saklanacak
    NEWS_EXPIRATION_DAYS = int(os.getenv("NEWS_EXPIRATION_DAYS", 3))

    # Kategoriler — Hem backend hem Android için ortak
    NEWS_CATEGORIES = ["general", "business", "technology", "world", "sports"]

    # Günlük görev saatleri (UTC uyumlu)
    CRON_TIMES = {
        "morning": "05:00",    # 08:00 Türkiye
        "noon": "09:00",       # 12:00 Türkiye
        "evening": "15:00",    # 18:00 Türkiye
        "night": "20:00",      # 23:00 Türkiye
    }

    # -----------------------
    # Zaman Dilimi (Render UTC kullanır)
    # -----------------------
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Istanbul")

    # -----------------------
    # Loglama
    # -----------------------
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
