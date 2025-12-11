from services.news_fetcher import (
    fetch_gnews,
    fetch_currents,
    fetch_mediastack,
    fetch_newsdata,
    get_news_from_best_source
)
from services.duplicate_filter import remove_duplicates, filter_low_quality
from models.news_models import NewsModel
from config import Config
import logging
from datetime import datetime
import pytz

logger = logging.getLogger(__name__)


class NewsService:
    """
    Haber güncelleme ve yönetim servisi.
    Görevi: API'lerden ham veriyi alıp veritabanına "işlenecek aday" olarak kaydetmektir.
    """

    @staticmethod
    def update_category(category: str, api_source: str = "auto") -> dict:
        """
        Belirli bir kategori için haber günceller.
        """
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
            # 1) API'den haber çek
            raw_news = []
            
            if api_source == "auto":
                # En iyi kaynaktan çek (Zincirleme)
                raw_news = get_news_from_best_source(category)
                stats["api_used"] = "fallback_chain"
            else:
                # Belirli API'den çek
                api_functions = {
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

            # Eğer hiç haber gelmediyse çık
            if not raw_news:
                logger.warning(f"⚠️  [{category}] API'den haber alınamadı (Liste boş)")
                return stats

            stats["fetched"] = len(raw_news)
            logger.info(f"📥 [{category}] {stats['fetched']} adet ham haber çekildi")

            # 2) Duplicate filtreleme (Basit URL/Başlık kontrolü)
            clean_news = remove_duplicates(raw_news)
            stats["after_duplicate_filter"] = len(clean_news)
            
            # Log detayı
            if len(clean_news) < len(raw_news):
                logger.info(f"   ✂️ {len(raw_news) - len(clean_news)} adet mükerrer (duplicate) elendi.")

            # 3) Kalite filtreleme (DÜZELTİLDİ: Artık daha esnek)
            # Scraper'ın çalışabilmesi için sadece Başlık ve URL olması yeterli.
            # Eskiden description kısa diye atıyordu, şimdi atmıyoruz.
            # Sadece bomboş olanları atıyoruz.
            quality_news = []
            for item in clean_news:
                if item.get('title') and item.get('url'):
                    quality_news.append(item)
            
            stats["after_quality_filter"] = len(quality_news)

            # 4) Veritabanına kaydet
            # Burası çok önemli: Kaydederken 'full_content' henüz yok.
            # Veritabanına girecek, sonra Scraper (Cron) bunları görüp içini dolduracak.
            if quality_news:
                save_stats = NewsModel.save_bulk(
                    quality_news,
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
        """Tüm kategorileri günceller (manuel veya klasik cron)."""

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
        """CRON slotlarına göre güncelleme yapar."""
        slot_config = Config.CRON_SCHEDULE.get(slot_name)

        if not slot_config:
            logger.error(f"❌ Bilinmeyen slot: {slot_name}")
            return {}

        logger.info(f"⏰ CRON TETİKLENDİ: {slot_name.upper()} ({slot_config['time']})")
        
        all_stats = []
        
        # Her kategori için, slotta tanımlı API'leri sırayla dener
        for category in Config.NEWS_CATEGORIES:
            success = False
            for api in slot_config["apis"]:
                logger.info(f"👉 Deneniyor: {api} -> {category}")
                stats = NewsService.update_category(category, api_source=api)
                
                # Eğer en az 1 haber çekildiyse (kaydedilmese bile, API çalıştı demektir)
                if stats["fetched"] > 0:
                    all_stats.append(stats)
                    success = True
                    break # Bu kategori için diğer API'ye geçme, başarılı oldu
            
            if not success:
                logger.warning(f"⚠️ [{category}] Hiçbir API'den veri alınamadı.")

        return {
            "slot": slot_name,
            "categories_updated": len(all_stats),
            "stats": all_stats
        }

    @staticmethod
    def clean_expired_news() -> dict:
        """Eski haberleri temizler."""
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
        """Monitoring için sistem durum bilgisi döndürür."""
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
                    "scraped_count": NewsModel.count_scraped(),     # Dolu haberler
                    "unscraped_count": NewsModel.count_unscraped()  # İşlenmeyi bekleyenler
                },
                "api_usage": get_all_usage(),
                "api_summary": get_daily_summary()
            }

        except Exception as e:
            logger.error(f"❌ Sistem durumu alınamadı: {e}")
            return {"status": "error", "error": str(e)}
