import os
from dotenv import load_dotenv

# .env dosyasını yükle (Render veya lokal geliştirme için)
load_dotenv()

class Config:
    # -----------------------
    # Flask Genel Ayarlar
    # -----------------------
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_key_change_in_production")
    
    # -----------------------
    # Güvenlik — Cron Secret
    # -----------------------
    CRON_SECRET = os.getenv("CRON_SECRET", "CHANGE_THIS_SECRET_KEY_IN_PRODUCTION")
    
    # -----------------------
    # Veritabanı Ayarları
    # -----------------------
    DB_URL = os.getenv("DB_URL", "postgresql://username:password@localhost:5432/habersel")
    
    # -----------------------
    # API Key'ler
    # -----------------------
    GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
    CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY", "")
    MEDIASTACK_KEY = os.getenv("MEDIASTACK_KEY", "")
    NEWSDATA_KEY = os.getenv("NEWSDATA_KEY", "")
    
    # -----------------------
    # API Limit Ayarları
    # -----------------------
    API_LIMITS = {
        "gnews": {
            "monthly": 3000,
            "daily": 100,
            "priority": 1
        },
        "currents": {
            "monthly": 600,
            "daily": 20,
            "priority": 2
        },
        "mediastack": {
            "monthly": 100,
            "daily": 3,
            "priority": 3
        },
        "newsdata": {
            "monthly": 100,
            "daily": 3,
            "priority": 4
        }
    }
    
    # -----------------------
    # Haber Sistem Ayarları
    # -----------------------
    NEWS_EXPIRATION_DAYS = int(os.getenv("NEWS_EXPIRATION_DAYS", "3"))
    NEWS_CATEGORIES = ["general", "business", "technology", "world", "sports"]
    NEWS_PER_CATEGORY = {
        "gnews": 5,
        "currents": 5,
        "mediastack": 3,
        "newsdata": 3
    }
    
    # -----------------------
    # GÜNLÜK CRON PLANI (TÜRKİYE SAATLERİ)
    # -----------------------
    CRON_SCHEDULE = {
        "morning": {
            "time": "08:00",  # Türkiye saati
            "hour": 8,        # Türkiye saati (scheduler.py UTC'ye çevirecek)
            "apis": ["gnews", "currents"],
            "total_requests": 30
        },
        "noon": {
            "time": "12:00",  # Türkiye saati
            "hour": 12,       # Türkiye saati
            "apis": ["gnews", "currents"],
            "total_requests": 30
        },
        "evening": {
            "time": "18:00",  # Türkiye saati
            "hour": 18,       # Türkiye saati
            "apis": ["gnews", "currents"],
            "total_requests": 30
        },
        "night": {
            "time": "23:00",  # Türkiye saati
            "hour": 23,       # Türkiye saati
            "apis": ["gnews", "mediastack"],
            "total_requests": 28
        }
    }
    
    # -----------------------
    # Zaman Ayarları
    # -----------------------
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Istanbul")
    CACHE_DURATION = int(os.getenv("CACHE_DURATION", "3600"))
    
    # -----------------------
    # Duplicate Filtreleme
    # -----------------------
    SIMILARITY_THRESHOLD = int(os.getenv("SIMILARITY_THRESHOLD", "85"))
    TIME_DIFF_THRESHOLD = int(os.getenv("TIME_DIFF_THRESHOLD", "900"))
    
    # -----------------------
    # Loglama
    # -----------------------
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # -----------------------
    # Rate Limiting
    # -----------------------
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    MAX_NEWS_PER_PAGE = int(os.getenv("MAX_NEWS_PER_PAGE", "50"))
    
    # -----------------------
    # API Timeout / Retry
    # -----------------------
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", "2"))
