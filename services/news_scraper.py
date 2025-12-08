from newspaper import Article
from models.news_models import NewsModel
from utils.helpers import full_clean_news_pipeline  # 🆕 TEMİZLEME FONKSİYONU
import time
import random
import logging
import threading

logger = logging.getLogger(__name__)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'
]


def scrape_article_content(url: str):
    """
    Haber URL'sinden tam içeriği çeker
    
    Args:
        url: Haber URL'si
    
    Returns:
        tuple: (full_text, scraped_image)
    """
    try:
        user_agent = random.choice(USER_AGENTS)
        
        article = Article(url, language='tr')
        article.config.browser_user_agent = user_agent
        article.config.request_timeout = 15
        
        article.download()
        article.parse()
        
        full_text = article.text.strip()
        
        if len(full_text) < 100:
            logger.warning(f"⚠️ Çok kısa içerik: {len(full_text)} karakter")
            return None, None
        
        scraped_image = article.top_image if article.top_image else None
        
        logger.debug(f"✅ {len(full_text)} karakter çekildi")
        if scraped_image:
            logger.debug(f"🖼️ Görsel bulundu: {scraped_image}")
        
        return full_text, scraped_image
        
    except Exception as e:
        logger.error(f"❌ Scrape hatası: {e}")
        return None, None


def scrape_latest_news(count=15):
    """
    En son scrape edilmemiş haberleri çeker ve veritabanına kaydeder
    
    🆕 YENİ: İçerikleri temizleyerek kaydeder
    
    Args:
        count: Çekilecek haber sayısı
    """
    logger.info(f"🔍 Scrape edilecek haberler aranıyor... (Hedef: {count})")
    
    pending_articles = NewsModel.get_unscraped(limit=count, exclude_blacklist=True)
    
    if not pending_articles:
        logger.info("✅ Scrape edilecek haber yok")
        return
    
    logger.info(f"📰 {len(pending_articles)} haber scrape edilecek...")
    
    success = 0
    failed = 0
    
    for idx, article in enumerate(pending_articles, 1):
        try:
            article_url = article['url']
            article_id = article['id']
            article_title = article.get('title', '')
            article_date = article.get('published')
            
            # Blacklist kontrolü
            if NewsModel.is_blacklisted(article_url, threshold=3):
                logger.debug(f"🚫 [{idx}/{len(pending_articles)}] Blacklist'te, atlanıyor: {article_title[:60]}...")
                failed += 1
                continue
            
            logger.info(f"🔄 [{idx}/{len(pending_articles)}] {article_title[:60]}...")
            
            # API'den gelen görsel
            api_image = article.get('image')
            
            # İçeriği scrape et
            full_content, scraped_image = scrape_article_content(article_url)
            
            if full_content:
                # 🆕 İÇERİĞİ TEMİZLE
                logger.debug("🧹 İçerik temizleniyor...")
                cleaned_data = full_clean_news_pipeline(
                    title=article_title,
                    content=full_content,
                    description=article.get('description'),
                    date=article_date
                )
                
                # Temizlenmiş içerik
                cleaned_content = cleaned_data['content']
                cleaned_title = cleaned_data['title']
                
                # Görsel önceliği: Scraper > API
                final_image = scraped_image if scraped_image else api_image
                
                # Veritabanına kaydet (temizlenmiş içerikle)
                NewsModel.update_full_content(
                    article_id, 
                    cleaned_content,  # 🆕 Temizlenmiş içerik
                    final_image
                )
                
                # İsteğe bağlı: Başlığı da güncelle
                if cleaned_title and cleaned_title != article_title:
                    try:
                        NewsModel.update_title(article_id, cleaned_title)
                        logger.debug(f"📝 Başlık güncellendi")
                    except:
                        pass  # Başlık güncellemesi opsiyonel
                
                success += 1
                
                # İstatistikler
                original_char_count = len(full_content)
                cleaned_char_count = len(cleaned_content) if cleaned_content else 0
                cleaned_word_count = len(cleaned_content.split()) if cleaned_content else 0
                reduction_pct = round((1 - cleaned_char_count / original_char_count) * 100, 1) if original_char_count > 0 else 0
                
                if scraped_image:
                    logger.info(f"   ✅ {cleaned_char_count} karakter (~{cleaned_word_count} kelime) [%{reduction_pct} temizlendi] (Scraper görseli)")
                elif api_image:
                    logger.info(f"   ✅ {cleaned_char_count} karakter (~{cleaned_word_count} kelime) [%{reduction_pct} temizlendi] (API görseli)")
                else:
                    logger.info(f"   ✅ {cleaned_char_count} karakter (~{cleaned_word_count} kelime) [%{reduction_pct} temizlendi] (görsel yok)")
            else:
                failed += 1
                NewsModel.add_to_blacklist(article_url, reason="content_extraction_failed")
                logger.warning(f"   ⚠️ İçerik alınamadı")
            
            # Rate limiting - Son haberde bekleme
            if idx < len(pending_articles):
                wait_time = random.randint(25, 35)
                time.sleep(wait_time)
            
        except Exception as e:
            failed += 1
            NewsModel.add_to_blacklist(article['url'], reason=f"exception: {str(e)[:50]}")
            logger.error(f"   ❌ Hata: {e}")
    
    logger.info(f"🎉 Scraping tamamlandı! Başarılı: {success}, Başarısız: {failed}")


def scrape_all_pending_articles():
    """
    Tüm bekleyen haberleri scrape eder (varsayılan 20 adet)
    """
    scrape_latest_news(count=20)


def scrape_in_background(count=15):
    """
    Scraping işlemini arka planda başlatır
    
    Args:
        count: Scrape edilecek haber sayısı
    """
    thread = threading.Thread(
        target=scrape_latest_news,
        args=(count,),
        daemon=True
    )
    thread.start()
    logger.info(f"🔥 Scraping arka planda başlatıldı ({count} haber)")
