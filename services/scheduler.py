from services.news_service import NewsService
from config import Config
from datetime import datetime
import pytz
import logging

logger = logging.getLogger(__name__)


def run_update(label: str, slot_name: str = None):
    """
    Zamanlanmış güncelleme görevini çalıştırır.
    
    Args:
        label: Görev adı (loglama için)
        slot_name: Config'deki CRON_SCHEDULE slot adı (opsiyonel)
    """
    tz = pytz.timezone(Config.TIMEZONE)
    start_time = datetime.now(tz)
    
    logger.info("\n" + "=" * 70)
    logger.info(f"⏰ [{label}] HABER GÜNCELLEMESİ BAŞLADI")
    logger.info(f"🕒 {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 70)
    
    try:
        # Slot bazlı güncelleme (önerilen)
        if slot_name and slot_name in Config.CRON_SCHEDULE:
            stats = NewsService.update_scheduled_slot(slot_name)
        else:
            # Klasik tüm kategoriler
            stats = NewsService.update_all_categories()
        
        end_time = datetime.now(tz)
        duration = (end_time - start_time).total_seconds()
        
        logger.info("=" * 70)
        logger.info(f"✅ [{label}] GÜNCELLEME TAMAMLANDI")
        logger.info(f"⏱️  Toplam Süre: {duration:.2f} saniye")
        logger.info("=" * 70 + "\n")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ [{label}] HATA: {e}")
        raise


# ---------------------------------------------------
# Cron Job Fonksiyonları (Zamanlanmış Görevler)
# ---------------------------------------------------

def morning_job():
    """
    Sabah 08:00 (Türkiye) / 05:00 (UTC)
    API'ler: GNews, Currents, NewsAPI.ai
    Toplam: ~32 istek
    """
    return run_update("SABAH 08:00", slot_name="morning")


def noon_job():
    """
    Öğle 12:00 (Türkiye) / 09:00 (UTC)
    API'ler: GNews, Currents
    Toplam: ~30 istek
    """
    return run_update("ÖĞLE 12:00", slot_name="noon")


def evening_job():
    """
    Akşam 18:00 (Türkiye) / 15:00 (UTC)
    API'ler: GNews, Currents, NewsAPI.ai
    Toplam: ~32 istek
    """
    return run_update("AKŞAM 18:00", slot_name="evening")


def night_job():
    """
    Gece 23:00 (Türkiye) / 20:00 (UTC)
    API'ler: GNews, Mediastack
    Toplam: ~28 istek
    """
    return run_update("GECE 23:00", slot_name="night")


def cleanup_job():
    """
    Gece 03:00 (Türkiye) / 00:00 (UTC)
    Eski haberleri temizler (3 gün+)
    """
    tz = pytz.timezone(Config.TIMEZONE)
    start_time = datetime.now(tz)
    
    logger.info("\n" + "=" * 70)
    logger.info(f"🧹 [TEMİZLİK 03:00] ESKİ HABERLER SİLİNİYOR")
    logger.info(f"🕒 {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 70)
    
    try:
        result = NewsService.clean_expired_news()
        
        logger.info("=" * 70)
        logger.info(f"✅ TEMİZLİK TAMAMLANDI")
        logger.info(f"🗑️  {result.get('deleted_count', 0)} haber silindi")
        logger.info("=" * 70 + "\n")
        
        return result
        
    except Exception as e:
        logger.error(f"❌ TEMİZLİK HATASI: {e}")
        raise
