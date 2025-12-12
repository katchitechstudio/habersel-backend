from services.news_service import NewsService
from services.news_scraper import scrape_in_background, scrape_latest_news
from models.system_models import SystemModel
from models.news_models import NewsModel
from config import Config
from datetime import datetime
import pytz
import logging

logger = logging.getLogger(__name__)


def should_run_update(slot_name: str) -> bool:
    if slot_name not in Config.CRON_SCHEDULE:
        logger.warning(f"⚠️  Bilinmeyen slot: {slot_name}")
        return False
    
    now_utc = datetime.now(pytz.UTC)
    current_hour_utc = now_utc.hour
    
    slot_hour_tr = Config.CRON_SCHEDULE[slot_name]["hour"]
    slot_hour_utc = (slot_hour_tr - 3) % 24
    
    tz_tr = pytz.timezone(Config.TIMEZONE)
    now_tr = now_utc.astimezone(tz_tr)
    
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
    if slot_name:
        if not should_run_update(slot_name):
            logger.info(f"⏸️  [{label}] Şu an çalışma zamanı değil, atlanıyor.")
            return {"skipped": True, "reason": "wrong_time"}
    
    now_utc = datetime.now(pytz.UTC)
    tz_tr = pytz.timezone(Config.TIMEZONE)
    now_tr = now_utc.astimezone(tz_tr)
    
    logger.info("\n" + "=" * 75)
    logger.info(f"⏰ [{label}] HABER GÜNCELLEMESİ BAŞLADI")
    logger.info(f"🕒 UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🕒 TR:  {now_tr.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 75)
    
    try:
        if slot_name and slot_name in Config.CRON_SCHEDULE:
            slot_config = Config.CRON_SCHEDULE[slot_name]
            scraping_count = slot_config.get("scraping_count", 15)
            stats = NewsService.update_scheduled_slot(slot_name)
        else:
            scraping_count = 20
            stats = NewsService.update_all_categories()
        
        total_saved = sum(v.get('saved', 0) for v in stats.values() if isinstance(v, dict))
        
        if total_saved == 0:
            logger.warning(f"⚠️  API'lerden yeni haber gelmedi!")
        else:
            logger.info(f"✅ {total_saved} yeni haber API'lerden eklendi")
        
        unscraped_count = NewsModel.count_unscraped()
        
        if unscraped_count > 0:
            logger.info(f"📊 Scrape bekleyen haber: {unscraped_count}")
            logger.info(f"🔥 Scraping arka planda başlatılıyor ({scraping_count} haber)...")
            scrape_in_background(count=scraping_count)
        else:
            logger.info("✅ Tüm haberlerin içeriği zaten dolu")
            
            total_news = NewsModel.get_total_count()
            if total_news < 10:
                logger.warning("⚠️  Database'de çok az haber var (<10), zorla güncelleme yapılıyor...")
                stats = NewsService.update_all_categories()
                logger.info("✅ Zorla güncelleme tamamlandı")
        
        end_time_utc = datetime.now(pytz.UTC)
        duration = (end_time_utc - now_utc).total_seconds()
        
        SystemModel.set_last_update(end_time_utc)
        
        logger.info("=" * 75)
        logger.info(f"✅ [{label}] GÜNCELLEME TAMAMLANDI")
        logger.info(f"⏱️  Toplam Süre: {duration:.2f} saniye")
        logger.info(f"📊 Yeni haber: {total_saved}, Scrape bekleyen: {unscraped_count}")
        logger.info("=" * 75 + "\n")
        
        return stats
        
    except Exception as e:
        logger.exception(f"❌ [{label}] HATA: {e}")
        
        try:
            unscraped_count = NewsModel.count_unscraped()
            if unscraped_count > 0:
                logger.info(f"🔄 Hata olmasına rağmen scraping deneniyor...")
                scrape_in_background(count=10)
                logger.info("✅ Scraping başlatıldı")
        except Exception as e2:
            logger.exception(f"❌ Scraping de başarısız: {e2}")
        
        raise


def scraping_only_job(label: str = "SCRAPING", count: int = 20):
    now_utc = datetime.now(pytz.UTC)
    tz_tr = pytz.timezone(Config.TIMEZONE)
    now_tr = now_utc.astimezone(tz_tr)
    
    logger.info("\n" + "=" * 75)
    logger.info(f"🔍 [{label}] İÇERİK SCRAPING İŞLEMİ")
    logger.info(f"🕒 UTC: {now_utc.strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"🕒 TR:  {now_tr.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info("=" * 75)
    
    try:
        unscraped_count = NewsModel.count_unscraped()
        
        if unscraped_count == 0:
            logger.info("✅ Scrape edilecek haber yok, işlem atlandı")
            logger.info("=" * 75 + "\n")
            return {"skipped": True, "reason": "no_unscraped"}
        
        logger.info(f"📊 Scrape bekleyen haber: {unscraped_count}")
        logger.info(f"🎯 Hedef: {count} haber scrape edilecek")
        
        scrape_latest_news(count=count)
        
        remaining = NewsModel.count_unscraped()
        filled = unscraped_count - remaining
        if filled < 0:
            filled = 0
        
        end_time_utc = datetime.now(pytz.UTC)
        duration = (end_time_utc - now_utc).total_seconds()
        
        logger.info("=" * 75)
        logger.info(f"✅ [{label}] SCRAPING TAMAMLANDI")
        logger.info(f"📈 Dolduruldu: {filled} haber")
        logger.info(f"📊 Kalan boş: {remaining} haber")
        logger.info(f"⏱️  Süre: {duration:.2f} saniye")
        logger.info("=" * 75 + "\n")
        
        return {
            "success": True,
            "filled": filled,
            "remaining": remaining,
            "duration": duration
        }
        
    except Exception as e:
        logger.exception(f"❌ [{label}] SCRAPING HATASI: {e}")
        return {
            "success": False,
            "error": str(e)
        }


def midnight_job():
    return run_update("GECE 00:00", slot_name="midnight")


def late_night_job():
    return run_update("GECE 02:00", slot_name="late_night")


def early_morning_job():
    return run_update("SABAH ERKENİ 04:00", slot_name="early_morning")


def dawn_job():
    return run_update("ŞAFAK 06:00", slot_name="dawn")


def morning_job():
    return run_update("SABAH 08:00", slot_name="morning")


def mid_morning_job():
    return run_update("KUŞLUK 10:00", slot_name="mid_morning")


def noon_job():
    return run_update("ÖĞLE 12:00", slot_name="noon")


def afternoon_job():
    return run_update("İKİNDİ 14:00", slot_name="afternoon")


def late_afternoon_job():
    return run_update("İKİNDİ SONU 16:00", slot_name="late_afternoon")


def early_evening_job():
    return run_update("AKŞAM BAŞI 18:00", slot_name="early_evening")


def evening_job():
    return run_update("AKŞAM 20:00", slot_name="evening")


def night_job():
    return run_update("GECE 22:00", slot_name="night")


def morning_scraping_job():
    return scraping_only_job(label="SABAH SCRAPING", count=30)


def afternoon_scraping_job():
    return scraping_only_job(label="ÖĞLEDEN SONRA SCRAPING", count=20)


def evening_scraping_job():
    return scraping_only_job(label="AKŞAM SCRAPING", count=15)


def cleanup_job():
    now_utc = datetime.now(pytz.UTC)
    current_hour_utc = now_utc.hour
    
    tz_tr = pytz.timezone(Config.TIMEZONE)
    now_tr = now_utc.astimezone(tz_tr)
    
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
