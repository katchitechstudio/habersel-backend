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
    # Veritabanı Ayarları
    # -----------------------
    # Render'dan alacağın gerçek DB_URL'i buraya yazacaksın
    DB_URL = os.getenv("DB_URL", "postgresql://username:password@localhost:5432/habersel")

    # -----------------------
    # API Key'ler (Placeholder)
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

    # Kaç kategori var (Android app ile uyumlu olmalı)
    NEWS_CATEGORIES = ["general", "business", "technology", "world", "sports"]

    # -----------------------
    # Cron Zaman Dilimi
    # Render UTC kullanır!
    # -----------------------
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Istanbul")

    # -----------------------
    # Loglama Ayarları
    # -----------------------
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
