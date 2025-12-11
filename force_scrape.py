from services.news_scraper import scrape_latest_news
from models.news_models import NewsModel
import logging
import time

# Logları görelim
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def force_fill_content():
    """
    Veritabanındaki 'içi boş' ama 'başlığı olan' haberleri bulur,
    kaynak sitelerine gidip metinlerini çeker ve günceller.
    """
    print("\n" + "="*60)
    print("🧹 İÇERİK DOLDURMA OPERASYONU BAŞLIYOR (MANUEL TETİKLEME)")
    print("="*60 + "\n")

    # 1. Durum Tespiti
    try:
        unscraped_count = NewsModel.count_unscraped()
        print(f"🧐 Şu an veritabanında içi boş (işlenmeyi bekleyen) {unscraped_count} haber var.")

        if unscraped_count == 0:
            print("✅ Tüm haberlerin içeriği zaten dolu! İşlem gerekmiyor.")
            return

        # 2. İşlemi Başlat
        # Sayıyı yüksek tutalım ki bekleyen hepsini halletsin (örn: 50)
        target_count = 50 
        if unscraped_count < target_count:
            target_count = unscraped_count

        print(f"🚀 {target_count} haber için kaynak sitelere gidiliyor...")
        
        # Scraper fonksiyonunu çağır
        scrape_latest_news(count=target_count)

        # 3. Sonuç Kontrolü
        remaining = NewsModel.count_unscraped()
        filled = unscraped_count - remaining
        
        print("\n" + "-" * 60)
        print(f"🎉 İŞLEM TAMAMLANDI!")
        print(f"✅ {filled} haberin içeriği başarıyla dolduruldu.")
        
        if remaining > 0:
            print(f"⚠️ {remaining} haber doldurulamadı (Site engeli veya yapı bozukluğu olabilir).")
        else:
            print("✨ Veritabanındaki tüm haberler full içerik oldu!")
            
        print("-" * 60 + "\n")

    except Exception as e:
        print(f"❌ Kritik Hata: {e}")

if __name__ == "__main__":
    force_fill_content()
