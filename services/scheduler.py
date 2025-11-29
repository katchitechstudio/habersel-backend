from services.news_service import NewsService
from config import Config
from datetime import datetime


def run_update(label: str):
    """
    Zamanlanmış güncelleme görevini çalıştırır.
    """
    print(f"\n⏰ [{label}] Haber güncellemesi başladı — {datetime.utcnow()} UTC")

    # Tüm kategorileri güncelle
    NewsService.update_all_categories()

    print(f"✅ [{label}] Güncelleme tamamlandı — {datetime.utcnow()} UTC\n")


# ---------------------------------------------------
# Cron job fonksiyonları
# ---------------------------------------------------

def morning_job():
    run_update("08:00 Sabah")


def noon_job():
    run_update("12:00 Öğle")


def evening_job():
    run_update("18:00 Akşam")


def night_job():
    run_update("23:00 Gece")


def cleanup_job():
    """
    Eski (3 gün önceki) haberleri siler.
    Render cron tarafından 03:00'te çağrılacak.
    """
    print("\n🧹 [03:00 Temizlik] Eski haberler siliniyor...")
    NewsService.clean_expired_news()
    print("🧽 Temizlik tamamlandı!\n")
