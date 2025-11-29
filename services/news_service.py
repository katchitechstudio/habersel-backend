from services.news_fetcher import get_news_from_best_source
from services.duplicate_filter import remove_duplicates
from models.news_models import NewsModel
from config import Config


class NewsService:

    @staticmethod
    def update_category(category: str):
        """
        Seçili kategori için:
        1) API'lerden haber çek
        2) Duplicate haberleri temizle
        3) DB'ye kaydet
        """
        print(f"🔍 Kategori güncelleniyor: {category}")

        # 1. API'lerden haber çek
        raw_news = get_news_from_best_source(category)

        if not raw_news:
            print(f"❌ '{category}' kategorisi için haber alınamadı.")
            return

        # 2. Duplicate temizle
        clean_news = remove_duplicates(raw_news)

        print(f"📌 {category}: {len(raw_news)} haber bulundu → {len(clean_news)} temiz haber kaydedilecek")

        # 3. DB'ye kaydet
        for article in clean_news:
            NewsModel.save_article(article, category)

        print(f"✅ '{category}' kategorisi başarıyla güncellendi.\n")

    @staticmethod
    def update_all_categories():
        """
        Tüm kategorileri günceller.
        Cron job'lar genelde bunu çağırır.
        """
        print("🚀 Tüm kategoriler güncelleniyor...")
        for category in Config.NEWS_CATEGORIES:
            NewsService.update_category(category)
        print("🎉 Tüm kategoriler başarıyla güncellendi!")

    @staticmethod
    def clean_expired_news():
        """
        3 günden eski haberleri siler.
        """
        print("🧹 Eski haberler temizleniyor...")
        NewsModel.delete_expired()
        print("🧽 Temizlik tamamlandı!")
