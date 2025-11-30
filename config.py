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
    # Cron job isteklerini doğrulamak için gizli anahtar
    # Üretim ortamında mutlaka değiştir!
    CRON_SECRET = os.getenv("CRON_SECRET", "CHANGE_THIS_SECRET_KEY_IN_PRODUCTION")
    
    # -----------------------
    # Veritabanı Ayarları
    # -----------------------
    # Render'dan alacağın PostgreSQL URL'i buraya gelecek
    DB_URL = os.getenv("DB_URL", "postgresql://username:password@localhost:5432/habersel")
    
    # -----------------------
    # API Key'ler (En son dolduracağız)
    # -----------------------
    GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
    CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY", "")
    NEWSAPI_AI_KEY = os.getenv("NEWSAPI_AI_KEY", "")
    MEDIASTACK_KEY = os.getenv("MEDIASTACK_KEY", "")
    NEWSDATA_KEY = os.getenv("NEWSDATA_KEY", "")
    
    # -----------------------
    # API Limit Ayarları (Aylık)
    # -----------------------
    API_LIMITS = {
        "gnews": {
            "monthly": 3000,
            "daily": 100,
            "priority": 1  # En yüksek öncelik
        },
        "currents": {
            "monthly": 600,
            "daily": 20,
            "priority": 2
        },
        "newsapi_ai": {
            "monthly": 200,
            "daily": 7,  # ~6.6 → 7'ye yuvarladım
            "priority": 3
        },
        "mediastack": {
            "monthly": 100,
            "daily": 3,
            "priority": 4
        },
        "newsdata": {
            "monthly": 100,
            "daily": 3,
            "priority": 5  # Yedek API
        }
    }
    
    # -----------------------
    # Haber Sistem Ayarları
    # -----------------------
    # Kaç gün geriye dönük haber saklanacak
    NEWS_EXPIRATION_DAYS = int(os.getenv("NEWS_EXPIRATION_DAYS", "3"))
    
    # Kategoriler — Android app ile senkronize
    NEWS_CATEGORIES = ["general", "business", "technology", "world", "sports"]
    
    # Her kategori için kaç haber çekilecek (API'ye göre değişir)
    NEWS_PER_CATEGORY = {
        "gnews": 5,
        "currents": 5,
        "newsapi_ai": 2,
        "mediastack": 3,
        "newsdata": 3
    }
    
    # -----------------------
    # Günlük Güncelleme Planı
    # -----------------------
    # Hangi saatte hangi API'ler kullanılacak
    CRON_SCHEDULE = {
        "morning": {  # 08:00 (Türkiye) = 05:00 (UTC)
            "time": "05:00",
            "apis": ["gnews", "currents", "newsapi_ai"],
            "total_requests": 32  # 25 + 5 + 2
        },
        "noon": {  # 12:00 (Türkiye) = 09:00 (UTC)
            "time": "09:00",
            "apis": ["gnews", "currents"],
            "total_requests": 30  # 25 + 5
        },
        "evening": {  # 18:00 (Türkiye) = 15:00 (UTC)
            "time": "15:00",
            "apis": ["gnews", "currents", "newsapi_ai"],
            "total_requests": 32  # 25 + 5 + 2
        },
        "night": {  # 23:00 (Türkiye) = 20:00 (UTC)
            "time": "20:00",
            "apis": ["gnews", "mediastack"],
            "total_requests": 28  # 25 + 3
        }
    }
    
    # -----------------------
    # Zaman Dilimi
    # -----------------------
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Istanbul")
    
    # -----------------------
    # Cache Ayarları
    # -----------------------
    # Her güncelleme sonrası cache süresi (saniye)
    CACHE_DURATION = int(os.getenv("CACHE_DURATION", "3600"))  # 1 saat
    
    # -----------------------
    # Duplicate Filter Ayarları
    # -----------------------
    # Başlık benzerlik oranı (%)
    SIMILARITY_THRESHOLD = int(os.getenv("SIMILARITY_THRESHOLD", "85"))
    
    # Aynı haber için zaman farkı toleransı (saniye)
    TIME_DIFF_THRESHOLD = int(os.getenv("TIME_DIFF_THRESHOLD", "900"))  # 15 dakika
    
    # -----------------------
    # Loglama
    # -----------------------
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    
    # Log formatı
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    # -----------------------
    # API Endpoint Ayarları
    # -----------------------
    # Rate limiting (kullanıcı başına)
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    
    # Maksimum sayfa başına haber sayısı
    MAX_NEWS_PER_PAGE = int(os.getenv("MAX_NEWS_PER_PAGE", "50"))
    
    # -----------------------
    # Hata Yönetimi
    # -----------------------
    # API timeout süresi (saniye)
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))
    
    # Başarısız isteklerde retry sayısı
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    
    # Retry aralığı (saniye)
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", "2"))
