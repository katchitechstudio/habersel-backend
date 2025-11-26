import os

class Config:
    # =============================
    # GENEL AYARLAR
    # =============================
    DEBUG = False

    # =============================
    # VERİTABANI AYARI
    # =============================
    DB_URL = os.environ.get(
        "DATABASE_URL",
        "postgresql://postgres:password@localhost:5432/habersel"
    )

    # =============================
    # CACHE / RSS AYARLARI
    # =============================
    CACHE_DURATION_MINUTES = 10      # 10 dakika cache
    MAX_NEWS_DAYS = 3                # Haberleri 3 gün saklama

    # =============================
    # SCHEDULER AYARLARI
    # =============================
    RSS_UPDATE_INTERVAL = 10         # 10 dakikada bir RSS çek
    JITTER_MAX_SECONDS = 15          # Bot görünmemesi için gecikme
