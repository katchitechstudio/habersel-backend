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
    # HABER AYARLARI
    # =============================
    NEWS_UPDATE_INTERVAL = 30   # dakikada bir güncellenecek
    NEWS_MAX_DAYS = 3           # haberler 3 gün saklanır
