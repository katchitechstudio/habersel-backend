from services.news_fetcher import (
    fetch_gnews,
    fetch_currents,
    fetch_newsapi_ai,
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
    Haber güncelleme ve yönetim servisi

    İşlevler:
    - API'lerden haber çekme
    - Duplicate filtreleme
    - Kalite kontrolü
    - DB'ye kaydetme
    - Eski haberleri temizleme
    """

    @staticmethod
    def update_category(category: str, api_source: str = "auto") -> dict:
        """
        Belirli bir kategori için haber günceller.

        İş akışı:
        1. API'den haber çek
        2. Duplicate temizle
        3. Kalite kontrolü
        4. DB'ye kaydet

        Args:
            category: Kategori (technology, sports, vb.)
            api_source: Hangi API kullanılacak ("auto" veya "gnews", "currents", vb.)

        Returns:
            dict: İşlem sonucu istatistikleri
        """
        logger.info(f"🔍 [{category}] Kategori güncelleniyor...")

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
            # 1. API'den haber çek
            if api_source == "auto":
                raw_news = get_news_from_best_source(category)
                stats["api_used"] = "fallback_chain"
            else:
                # Belirli bir API kullan
                api_functions = {
                    "gnews": fetch_gnews,
                    "currents": fetch_currents,
                    "newsapi_ai": fetch_newsapi_ai,
                    "mediastack": fetch_mediastack,
                    "newsdata": fetch_newsdata
                }

                fetch_func = api_functions.get(api_source)
                if not fetch_func:
                    logger.error(f"❌ Bilinmeyen API: {api_source}")
                    return stats

                raw_news = fetch_func(category)

            if not raw_news:
                logger.warning(f"⚠️  [{category}] API'den haber alınamadı")
                return stats

            stats["fetched"] = len(raw_news)
            logger.info(f"📥 [{category}] {len(raw_news)} haber çekildi")

            # 2. Duplicate temizle
            clean_news = remove_duplicates(raw_news)
            stats["after_duplicate_filter"] = len(clean_news)
            stats["duplicates"] = stats["fetched"] - stats["after_duplicate_filter"]

            if stats["duplicates"] > 0:
                logger.info(f"🧹 [{category}] {stats['duplicates']} duplicate haber temizlendi")

            # 3. Kalite kontrolü (opsiyonel)
            quality_news = filter_low_quality(clean_news, min_score=60)
            stats["after_quality_filter"] = len(quality_news)

            low_quality_count = stats["after_duplicate_filter"] - stats["after_quality_filter"]
            if low_quality_count > 0:
                logger.info(f"🎯 [{category}] {low_quality_count} düşük kaliteli haber filtrelendi")

            # 4. DB'ye kaydet
            logger.info(f"💾 [{category}] {len(quality_news)} haber DB'ye kaydediliyor...")

            save_stats = NewsModel.save_bulk(
                quality_news,
                category,
                api_source=stats["api_used"]
            )

            stats["saved"] = save_stats["saved"]
            stats["duplicates"] += save_stats["duplicates"]  # DB'deki duplicate'ler
            stats["errors"] = save_stats["errors"]

            # Sonuç logu
            logger.info(
                f"✅ [{category}] Tamamlandı: "
                f"{stats['fetched']} çekildi → "
                f"{stats['saved']} kaydedildi "
                f"({stats['duplicates']} duplicate, {stats['errors']} hata)"
            )

            return stats

        except Exception as e:
            logger.error(f"❌ [{category}] Hata: {e}")
            stats["errors"] += 1
            return stats

    @staticmethod
    def update_all_categories(api_source: str = "auto") -> dict:
        """
        Tüm kategorileri günceller (Cron job için ana fonksiyon)

        Args:
            api_source: Hangi API kullanılacak

        Returns:
            dict: Toplam istatistikler
        """
        tz = pytz.timezone(Config.TIMEZONE)
        start_time = datetime.now(tz)

        logger.info("=" * 60)
        logger.info(f"🚀 TÜM KATEGORİLER GÜNCELLENİYOR")
        logger.info(f"⏰ Başlangıç: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info("=" * 60)

        total_stats = {
            "start_time": start_time.isoformat(),
            "categories": {},
            "totals": {
                "fetched": 0,
                "saved": 0,
                "duplicates": 0,
                "errors": 0
            }
        }

        # Her kategoriyi güncelle
        for category in Config.NEWS_CATEGORIES:
            category_stats = NewsService.update_category(category, api_source)
            total_stats["categories"][category] = category_stats

            # Toplam istatistikleri güncelle
            total_stats["totals"]["fetched"] += category_stats["fetched"]
            total_stats["totals"]["saved"] += category_stats["saved"]
            total_stats["totals"]["duplicates"] += category_stats["duplicates"]
            total_stats["totals"]["errors"] += category_stats["errors"]

        # Bitiş zamanı
        end_time = datetime.now(tz)
        duration = (end_time - start_time).total_seconds()

        total_stats["end_time"] = end_time.isoformat()
        total_stats["duration_seconds"] = duration

        # Sonuç özeti
        logger.info("=" * 60)
        logger.info(f"🎉 GÜNCELLEME TAMAMLANDI!")
        logger.info(
            f"📊 Toplam: {total_stats['totals']['fetched']} çekildi, "
            f"{total_stats['totals']['saved']} kaydedildi"
        )
        logger.info(f"🧹 Duplicate: {total_stats['totals']['duplicates']}")
        logger.info(f"❌ Hata: {total_stats['totals']['errors']}")
        logger.info(f"⏱️  Süre: {duration:.2f} saniye")
        logger.info("=" * 60)

        return total_stats

    @staticmethod
    def update_scheduled_slot(slot_name: str) -> dict:
        """
        Zamanlanmış slot'a göre güncelleme yapar (Config'deki CRON_SCHEDULE'e göre)

        Args:
            slot_name: "morning", "noon", "evening", "night"

        Returns:
            dict: İstatistikler
        """
        slot_config = Config.CRON_SCHEDULE.get(slot_name)

        if not slot_config:
            logger.error(f"❌ Bilinmeyen slot: {slot_name}")
            return {}

        logger.info(f"⏰ {slot_name.upper()} SLOT ({slot_config['time']})")
        logger.info(f"🎯 Kullanılacak API'ler: {slot_config['apis']}")
        logger.info(f"📊 Hedef istek sayısı: {slot_config['total_requests']}")

        # Her kategori için belirtilen API'lerden sırayla dene
        all_stats = []

        for category in Config.NEWS_CATEGORIES:
            for api in slot_config['apis']:
                stats = NewsService.update_category(category, api_source=api)

                if stats['saved'] > 0:
                    all_stats.append(stats)
                    break  # Başarılı olduysa sonraki API'yi deneme

        return {
            "slot": slot_name,
            "categories_updated": len(all_stats),
            "stats": all_stats
        }

    @staticmethod
    def clean_expired_news() -> dict:
        """
        3 günden eski haberleri siler.

        Returns:
            dict: Silinen haber sayısı
        """
        tz = pytz.timezone(Config.TIMEZONE)
        start_time = datetime.now(tz)

        logger.info("=" * 60)
        logger.info(f"🧹 ESKİ HABERLER TEMİZLENİYOR")
        logger.info(f"⏰ {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
        logger.info(f"🗑️  {Config.NEWS_EXPIRATION_DAYS} günden eski haberler silinecek")
        logger.info("=" * 60)

        try:
            deleted_count = NewsModel.delete_expired()

            end_time = datetime.now(tz)
            duration = (end_time - start_time).total_seconds()

            logger.info("=" * 60)
            logger.info(f"✅ TEMİZLİK TAMAMLANDI!")
            logger.info(f"🗑️  {deleted_count} eski haber silindi")
            logger.info(f"⏱️  Süre: {duration:.2f} saniye")
            logger.info("=" * 60)

            return {
                "deleted_count": deleted_count,
                "duration_seconds": duration,
                "timestamp": end_time.isoformat()
            }

        except Exception as e:
            logger.error(f"❌ Temizlik hatası: {e}")
            return {
                "deleted_count": 0,
                "error": str(e)
            }

    @staticmethod
    def get_system_status() -> dict:
        """
        Sistemin genel durumunu döndürür (monitoring için)

        Returns:
            dict: Sistem durumu
        """
        from services.api_manager import get_all_usage, get_daily_summary

        try:
            total_news = NewsModel.get_total_count()
            latest_update = NewsModel.get_latest_update_time()

            category_stats = {}
            for category in Config.NEWS_CATEGORIES:
                category_stats[category] = NewsModel.count_by_category(category)

            return {
                "status": "healthy",
                "timestamp": datetime.now(pytz.timezone(Config.TIMEZONE)).isoformat(),
                "database": {
                    "total_news": total_news,
                    "latest_update": latest_update,  # route tarafında isoformat'a çevirebiliriz
                    "by_category": category_stats
                },
                "api_usage": get_all_usage(),
                "api_summary": get_daily_summary()
            }

        except Exception as e:
            logger.error(f"❌ Sistem durumu alınamadı: {e}")
            return {
                "status": "error",
                "error": str(e)
            }
