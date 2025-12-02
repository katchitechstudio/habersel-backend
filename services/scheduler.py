from services.news_service import NewsService
from models.news_models import NewsModel
from config import Config
from datetime import datetime
import pytz
import logging

logger = logging.getLogger(__name__)


# ======================================================
# CRON ÇALIŞTIRMA MOTORU – FİNAL SÜRÜM
# ======================================================

def run_update(label: str, slot_name: str = None):
    """
    Zamanlanmış güncelleme görevini çalıştırır.

    Args:
        label: Log etiketi (örn: SABAH 08:00)
        slot_name: Config.CRON_SCHEDULE key'i (örn: "morning")
    """
    tz = pytz.timezone(Config.TIMEZONE)
    start_time = datetime.now(tz)

    logger.info("\n" + "=" * 75)
    logger.info(f"⏰ [{label}] HABER GÜNCELLEMESİ BAŞLADI")
    logger.info(f"🕒 {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 75)

    try:
        # Slot bazlı güncelleme (önerilen)
        if slot_name and slot_name in Config.CRON_SCHEDULE:
            stats = NewsService.update_scheduled_slot(slot_name)
        else:
            # Klasik tüm kategoriler
            stats = NewsService.update_all_categories()

        # Süreyi hesapla
        end_time = datetime.now(tz)
        duration = (end_time - start_time).total_seconds()

        # Cron sonunda last_update değerini DB'ye yazalım:
        last_update = datetime.utcnow()
        logger.info(f"💾 Last update DB'ye işleniyor → {last_update.isoformat()} UTC")
        _write_last_update(last_update)

        logger.info("=" * 75)
        logger.info(f"✅ [{label}] GÜNCELLEME TAMAMLANDI")
        logger.info(f"⏱️  Toplam Süre: {duration:.2f} saniye")
        logger.info("=" * 75 + "\n")

        return stats

    except Exception as e:
        logger.error(f"❌ [{label}] HATA: {e}")
        raise


# ======================================================
# LAST-UPDATE DB YAZICI
# ======================================================

def _write_last_update(dt: datetime):
    """
    Cron çalıştıktan sonra son güncelleme zamanını
    DB'ye işleyen fonksiyon.
    """
    try:
        # Aynı NewsModel içine eklenebilir ama sade bırakıyoruz.
        conn = NewsModel.get_db() if hasattr(NewsModel, "get_db") else None
        conn = conn or get_db()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO system_info (id, last_update)
            VALUES (1, %s)
            ON CONFLICT (id) DO UPDATE SET last_update = EXCLUDED.last_update;
        """, (dt,))

        conn.commit()
        cur.close()
        conn.close()

    except Exception as e:
        logger.error(f"❌ Last update yazma hatası: {e}")


# ======================================================
# CRON JOB FONKSİYONLARI
# ======================================================

def morning_job():
    """
    Sabah 08:00 (Türkiye) → GNews + Currents + NewsAPI.ai
    """
    return run_update("SABAH 08:00", slot_name="morning")


def noon_job():
    """
    Öğle 12:00 → GNews + Currents
    """
    return run_update("ÖĞLE 12:00", slot_name="noon")


def evening_job():
    """
    Akşam 18:00 → GNews + Currents + NewsAPI.ai
    """
    return run_update("AKŞAM 18:00", slot_name="evening")


def night_job():
    """
    Gece 23:00 → GNews + Mediastack
    """
    return run_update("GECE 23:00", slot_name="night")


# ======================================================
# TEMİZLİK GÖREVİ
# ======================================================

def cleanup_job():
    """
    Her gece 03:00 → 3 günden eski haberleri siler.
    """
    tz = pytz.timezone(Config.TIMEZONE)
    start_time = datetime.now(tz)

    logger.info("\n" + "=" * 75)
    logger.info(f"🧹 [TEMİZLİK 03:00] ESKİ HABERLER SİLİNİYOR")
    logger.info(f"🕒 {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 75)

    try:
        result = NewsService.clean_expired_news()

        logger.info("=" * 75)
        logger.info(f"✅ TEMİZLİK TAMAMLANDI")
        logger.info(f"🗑️  Silinen haber: {result.get('deleted_count', 0)}")
        logger.info("=" * 75 + "\n")

        return result

    except Exception as e:
        logger.error(f"❌ TEMİZLİK HATASI: {e}")
        raise
