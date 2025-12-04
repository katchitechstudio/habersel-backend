from services.news_service import NewsService
from models.system_models import SystemModel
from config import Config
from datetime import datetime
import pytz
import logging

logger = logging.getLogger(__name__)

# ======================================================
# CRON ÇALIŞTIRMA MOTORU – FİNAL SÜRÜM (UTC FIXED)
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
    
    # ✅ UTC saati al (Render UTC'de çalışıyor)
    now_utc = datetime.now(pytz.UTC)
    current_hour_utc = now_utc.hour
    
    # Config'den TR saatini al, UTC'ye çevir
    slot_hour_tr = Config.CRON_SCHEDULE[slot_name]["hour"]
    slot_hour_utc = (slot_hour_tr - 3) % 24  # TR - 3 = UTC
    
    # Türkiye saati sadece log için
    tz_tr = pytz.timezone(Config.TIMEZONE)
    now_tr = now_utc.astimezone(tz_tr)
    
    # UTC bazlı kontrol
    if current_hour_utc == slot_hour_utc:
        logger.info(
            f"✅ UTC {current_hour_utc:02d}:{now_utc.minute:02d} "
            f"(TR {now_tr.hour:02d}:{now_tr.minute:02d}) - "
            f"{slot_name.upper()} slot'u çalışacak"
        )
        return True
    else:
        logger.info(
            f"⏭️  UTC {current_hour_utc:02d}:{now_utc.minute:02d} "
            f"(TR {now_tr.hour:02d}:{now_tr.minute:02d}) - "
            f"{slot_name.upper()} slot'u atlandı (beklenen UTC: {slot_hour_utc:02d}:00)"
        )
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
    
    # UTC ve TR saati
    now_utc = datetime.now(pytz.UTC)
    tz_tr = pytz.timezone(Config.TIMEZONE)
    now_tr = now_utc.astimezone(tz_tr)
    
    logger.info("\n" + "=" * 75)
    logger.info(f"⏰ [{label}] HABER GÜNCELLEMESİ BAŞLADI")
    logger.info(f"🕒 UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🕒 TR:  {now_tr.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 75)
    
    try:
        # Slot'a göre API zincirli güncelleme
        if slot_name and slot_name in Config.CRON_SCHEDULE:
            stats = NewsService.update_scheduled_slot(slot_name)
        else:
            stats = NewsService.update_all_categories()
        
        end_time_utc = datetime.now(pytz.UTC)
        duration = (end_time_utc - now_utc).total_seconds()
        
        # last_update güncellemesi
        SystemModel.set_last_update(end_time_utc)
        logger.info(f"💾 last_update güncellendi → {end_time_utc.isoformat()} UTC")
        
        logger.info("=" * 75)
        logger.info(f"✅ [{label}] GÜNCELLEME TAMAMLANDI")
        logger.info(f"⏱️  Toplam Süre: {duration:.2f} saniye")
        logger.info("=" * 75 + "\n")
        
        return stats
        
    except Exception as e:
        logger.exception(f"❌ [{label}] HATA: {e}")
        raise


# ======================================================
# CRON JOB FONKSİYONLARI (TÜRKİYE SAATLERİNE GÖRE)
# ======================================================

def morning_job():
    """Sabah 08:00 (TR) = 05:00 (UTC) — GNews + Currents + NewsAPI.ai"""
    return run_update("SABAH 08:00", slot_name="morning")


def noon_job():
    """Öğle 12:00 (TR) = 09:00 (UTC) — GNews + Currents"""
    return run_update("ÖĞLE 12:00", slot_name="noon")


def evening_job():
    """Akşam 18:00 (TR) = 15:00 (UTC) — GNews + Currents + NewsAPI.ai"""
    return run_update("AKŞAM 18:00", slot_name="evening")


def night_job():
    """Gece 23:00 (TR) = 20:00 (UTC) — GNews + Mediastack"""
    return run_update("GECE 23:00", slot_name="night")


# ======================================================
# TEMİZLİK GÖREVİ – 03:00 (TR) = 00:00 (UTC)
# ======================================================

def cleanup_job():
    """
    Her gece 03:00 (TR) = 00:00 (UTC) → 3 günden eski haberleri siler.
    """
    # UTC saati al
    now_utc = datetime.now(pytz.UTC)
    current_hour_utc = now_utc.hour
    
    # Türkiye saati log için
    tz_tr = pytz.timezone(Config.TIMEZONE)
    now_tr = now_utc.astimezone(tz_tr)
    
    # Sadece 00:00 UTC'de çalıştır (TR 03:00)
    if current_hour_utc != 0:
        logger.info(
            f"⏭️  TEMİZLİK - UTC {current_hour_utc:02d}:xx (TR {now_tr.hour:02d}:xx), "
            f"atlanıyor (beklenen UTC: 00:00)"
        )
        return {"skipped": True, "reason": "wrong_time"}
    
    logger.info("\n" + "=" * 75)
    logger.info(f"🧹 [TEMİZLİK 03:00 TR / 00:00 UTC] ESKİ HABERLER SİLİNİYOR")
    logger.info(f"🕒 UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🕒 TR:  {now_tr.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 75)
    
    try:
        result = NewsService.clean_expired_news()
        
        logger.info("=" * 75)
        logger.info(f"✅ TEMİZLİK TAMAMLANDI")
        logger.info(f"🗑️  Silinen haber: {result.get('deleted_count', 0)}")
        logger.info("=" * 75 + "\n")
        
        return result
        
    except Exception as e:
        logger.exception(f"❌ TEMİZLİK HATASI: {e}")
        raise
