from services.news_fetcher import (
    fetch_newsapi,
    fetch_gnews,
    fetch_currents,
    fetch_mediastack,
    fetch_newsdata,
    get_news_from_best_source
)
from services.duplicate_filter import remove_duplicates, filter_low_quality
from models.news_models import NewsModel
from utils.helpers import clean_news_title, clean_news_content, enhanced_clean_pipeline
from config import Config
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


class NewsService:

    @staticmethod
    def update_category(category: str, api_source: str = "auto") -> dict:
        logger.info(f"🔍 [{category}] Kategori taranıyor...")

        stats = {
            "category": category,
            "fetched": 0,
            "after_duplicate_filter": 0,
            "after_quality_filter": 0,
            "saved": 0,
            "duplicates": 0,
            "errors": 0,
            "api_used": api_source
        }

        try:
            raw_news = []
            
            if api_source == "auto":
                raw_news = get_news_from_best_source(category)
                stats["api_used"] = "fallback_chain"
            else:
                api_functions = {
                    "newsapi": fetch_newsapi,
                    "gnews": fetch_gnews,
                    "currents": fetch_currents,
                    "mediastack": fetch_mediastack,
                    "newsdata": fetch_newsdata,
                }

                fetch_func = api_functions.get(api_source)
                if not fetch_func:
                    logger.error(f"❌ Bilinmeyen API: {api_source}")
                    return stats

                raw_news = fetch_func(category)

            if not raw_news:
                logger.warning(f"⚠️  [{category}] API'den haber alınamadı (Liste boş)")
                return stats

            stats["fetched"] = len(raw_news)
            logger.info(f"📥 [{category}] {stats['fetched']} adet ham haber çekildi")

            clean_news = remove_duplicates(raw_news)
            stats["after_duplicate_filter"] = len(clean_news)
            
            if len(clean_news) < len(raw_news):
                logger.info(f"   ✂️ {len(raw_news) - len(clean_news)} adet mükerrer (duplicate) elendi.")

            quality_news = []
            for item in clean_news:
                if item.get('title') and item.get('url'):
                    quality_news.append(item)
            
            stats["after_quality_filter"] = len(quality_news)

            if quality_news:
                cleaned_news = []
                for item in quality_news:
                    cleaned_item = item.copy()
                    
                    if cleaned_item.get('title'):
                        original_title = cleaned_item['title']
                        cleaned_title = clean_news_title(original_title)
                        
                        if cleaned_title and len(cleaned_title) >= 10:
                            cleaned_item['title'] = cleaned_title
                            if cleaned_title != original_title:
                                logger.debug(f"   🧹 Başlık temizlendi: {original_title[:40]}... → {cleaned_title[:40]}...")
                    
                    if cleaned_item.get('description'):
                        original_desc = cleaned_item['description']
                        cleaned_desc = clean_news_content(original_desc)
                        
                        if cleaned_desc and len(cleaned_desc) >= 30:
                            cleaned_item['description'] = cleaned_desc
                            if cleaned_desc != original_desc:
                                logger.debug(f"   🧹 Açıklama temizlendi")
                    
                    cleaned_news.append(cleaned_item)
                
                logger.info(f"   🧹 {len(cleaned_news)} haber temizlendi, kaydediliyor...")
                
                save_stats = NewsModel.save_bulk(
                    cleaned_news,
                    category,
                    api_source=stats["api_used"]
                )

                stats["saved"] = save_stats["saved"]
                stats["duplicates"] += save_stats["duplicates"]
                stats["errors"] = save_stats["errors"]
            else:
                logger.warning(f"⚠️ [{category}] Kaydedilecek geçerli haber kalmadı.")

            logger.info(
                f"✅ [{category}] Rapor: "
                f"Çekilen: {stats['fetched']} -> "
                f"Kaydedilen: {stats['saved']} "
                f"(Veritabanında zaten olan: {stats['duplicates']})"
            )

            return stats

        except Exception as e:
            logger.exception(f"❌ [{category}] Kritik Hata")
            stats["errors"] += 1
            return stats

    @staticmethod
    def update_all_categories(api_source: str = "auto") -> dict:
        tz = pytz.timezone(Config.TIMEZONE)
        start_time = datetime.now(tz)

        logger.info("=" * 60)
        logger.info(f"🚀 TOPLU GÜNCELLEME BAŞLIYOR (Kaynak: {api_source})")
        logger.info(f"⏰ Zaman: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        total_stats = {
            "start_time": start_time.isoformat(),
            "categories": {},
            "totals": {"fetched": 0, "saved": 0, "duplicates": 0, "errors": 0}
        }

        for category in Config.NEWS_CATEGORIES:
            category_stats = NewsService.update_category(category, api_source)
            total_stats["categories"][category] = category_stats

            total_stats["totals"]["fetched"] += category_stats["fetched"]
            total_stats["totals"]["saved"] += category_stats["saved"]
            total_stats["totals"]["duplicates"] += category_stats["duplicates"]
            total_stats["totals"]["errors"] += category_stats["errors"]

        end_time = datetime.now(tz)
        duration = (end_time - start_time).total_seconds()

        total_stats["end_time"] = end_time.isoformat()
        total_stats["duration_seconds"] = duration

        logger.info("=" * 60)
        logger.info("🎉 GÜNCELLEME BİTTİ")
        logger.info(f"📊 Toplam Çekilen: {total_stats['totals']['fetched']}")
        logger.info(f"💾 Yeni Kaydedilen: {total_stats['totals']['saved']}")
        logger.info(f"♻️  Zaten Var Olan: {total_stats['totals']['duplicates']}")
        logger.info(f"⏱️  Süre: {duration:.2f} saniye")
        logger.info("=" * 60)

        return total_stats

    @staticmethod
    def update_scheduled_slot(slot_name: str) -> dict:
        slot_config = Config.CRON_SCHEDULE.get(slot_name)

        if not slot_config:
            logger.error(f"❌ Bilinmeyen slot: {slot_name}")
            return {}

        logger.info(f"⏰ CRON TETİKLENDİ: {slot_name.upper()} ({slot_config['time']})")
        
        all_stats = []
        
        for category in Config.NEWS_CATEGORIES:
            success = False
            for api in slot_config["apis"]:
                logger.info(f"👉 Deneniyor: {api} -> {category}")
                stats = NewsService.update_category(category, api_source=api)
                
                if stats["fetched"] > 0:
                    all_stats.append(stats)
                    success = True
                    break
            
            if not success:
                logger.warning(f"⚠️ [{category}] Hiçbir API'den veri alınamadı.")

        return {
            "slot": slot_name,
            "categories_updated": len(all_stats),
            "stats": all_stats
        }

    @staticmethod
    def clean_expired_news() -> dict:
        tz = pytz.timezone(Config.TIMEZONE)
        start = datetime.now(tz)

        logger.info("🧹 Eski haber temizliği başlatılıyor...")

        try:
            deleted = NewsModel.delete_expired()
            duration = (datetime.now(tz) - start).total_seconds()

            if deleted > 0:
                logger.info(f"🗑️  {deleted} adet süresi dolmuş haber silindi.")
            else:
                logger.info("✨ Silinecek eski haber yok.")
                
            return {"deleted_count": deleted, "duration_seconds": duration}

        except Exception as e:
            logger.error(f"❌ Temizlik hatası: {e}")
            return {"deleted_count": 0, "error": str(e)}

    @staticmethod
    def get_system_status() -> dict:
        from services.api_manager import get_all_usage, get_daily_summary

        try:
            total_news = NewsModel.get_total_count()
            latest_update = NewsModel.get_latest_update_time()

            by_category = {
                c: NewsModel.count_by_category(c)
                for c in Config.NEWS_CATEGORIES
            }

            return {
                "status": "healthy",
                "timestamp": datetime.now(pytz.timezone(Config.TIMEZONE)).isoformat(),
                "database": {
                    "total_news": total_news,
                    "latest_update": latest_update,
                    "by_category": by_category,
                    "scraped_count": NewsModel.count_scraped(),
                    "unscraped_count": NewsModel.count_unscraped()
                },
                "api_usage": get_all_usage(),
                "api_summary": get_daily_summary()
            }

        except Exception as e:
            logger.error(f"❌ Sistem durumu alınamadı: {e}")
            return {"status": "error", "error": str(e)}
