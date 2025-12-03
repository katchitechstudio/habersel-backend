from services.news_service import NewsService
from models.system_models import SystemModel
from config import Config
from datetime import datetime
import pytz
import logging

logger = logging.getLogger(__name__)

# ======================================================
# CRON ÇALIŞTIRMA MOTORU – FİNAL SÜRÜM (FIXED)
# ======================================================

def should_run_update(slot_name: str) -> bool:
    """
    Şu anki saat, belirtilen slot'un çalışma saati mi kontrol eder.
    
    Args:
        slot_name: Config.CRON_SCHEDULE key'i (morning, noon, evening, night)
    
    Returns:
        bool: Şu an bu slot çalışmalı mı?
    """
    if slot_name not in Config.CRON_SCHEDULE:
        logger.warning(f"⚠️  Bilinmeyen slot: {slot_name}")
        return False
    
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)
    current_hour = now.hour
    
    # Config'den slot'un çalışma saatini al
    slot_hour = Config.CRON_SCHEDULE[slot_name]["hour"]
    
    # Sadece belirlenen saatte çalıştır
    if current_hour == slot_hour:
        logger.info(f"✅ Saat {current_hour:02d}:xx - {slot_name.upper()} slot'u çalışacak")
        return True
    else:
        logger.info(f"⏭️  Saat {current_hour:02d}:xx - {slot_name.upper()} slot'u atlandı (beklenen saat: {slot_hour:02d}:00)")
        return False


def run_update(label: str, slot_name: str = None):
    """
    Zamanlanmış haber güncelleme görevini çalıştırır.
    
    Args:
        label: Log etiketi (örn: SABAH 08:00)
        slot_name: Config.CRON_SCHEDULE key'i (örn: morning)
    """
    # Saat kontrolü - slot_name varsa kontrol et
    if slot_name:
        if not should_run_update(slot_name):
            logger.info(f"⏸️  [{label}] Şu an çalışma zamanı değil, atlanıyor.")
            return {"skipped": True, "reason": "wrong_time"}
    
    tz = pytz.timezone(Config.TIMEZONE)
    start_time = datetime.now(tz)
    
    logger.info("\n" + "=" * 75)
    logger.info(f"⏰ [{label}] HABER GÜNCELLEMESİ BAŞLADI")
    logger.info(f"🕒 {start_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 75)
    
    try:
        # Slot'a göre API zincirli güncelleme
        if slot_name and slot_name in Config.CRON_SCHEDULE:
            stats = NewsService.update_scheduled_slot(slot_name)
        else:
            stats = NewsService.update_all_categories()
        
        end_time = datetime.now(tz)
        duration = (end_time - start_time).total_seconds()
        
        # last_update güncellemesi
        last_update_utc = datetime.utcnow()
        SystemModel.set_last_update(last_update_utc)
        logger.info(f"💾 last_update güncellendi → {last_update_utc.isoformat()} UTC")
        
        logger.info("=" * 75)
        logger.info(f"✅ [{label}] GÜNCELLEME TAMAMLANDI")
        logger.info(f"⏱️  Toplam Süre: {duration:.2f} saniye")
        logger.info("=" * 75 + "\n")
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ [{label}] HATA: {e}")
        raise


# ======================================================
# CRON JOB FONKSİYONLARI (TÜRKİYE SAATLERİNE GÖRE)
# ======================================================

def morning_job():
    """Sabah 08:00 — GNews + Currents + NewsAPI.ai"""
    return run_update("SABAH 08:00", slot_name="morning")


def noon_job():
    """Öğle 12:00 — GNews + Currents"""
    return run_update("ÖĞLE 12:00", slot_name="noon")


def evening_job():
    """Akşam 18:00 — GNews + Currents + NewsAPI.ai"""
    return run_update("AKŞAM 18:00", slot_name="evening")


def night_job():
    """Gece 23:00 — GNews + Mediastack"""
    return run_update("GECE 23:00", slot_name="night")


# ======================================================
# TEMİZLİK GÖREVİ – 03:00
# ======================================================

def cleanup_job():
    """
    Her gece 03:00 → 3 günden eski haberleri siler.
    """
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)
    
    # Sadece 03:00'te çalıştır
    if now.hour != 3:
        logger.info(f"⏭️  TEMİZLİK - Şu an saat {now.hour:02d}:xx, atlanıyor (beklenen: 03:00)")
        return {"skipped": True, "reason": "wrong_time"}
    
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
