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
