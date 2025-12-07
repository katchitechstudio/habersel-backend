from newspaper import Article
from models.news_models import NewsModel
import time
import logging

logger = logging.getLogger(__name__)


def scrape_article_content(url: str) -> str:
    try:
        article = Article(url, language='tr')
        article.download()
        article.parse()
        
        full_text = article.text
        
        if len(full_text) < 200:
            return None
        
        return full_text
        
    except Exception as e:
        logger.error(f"❌ Scrape hatası ({url}): {e}")
        return None


def scrape_all_pending_articles():
    logger.info("🔍 Scrape edilecek haberler aranıyor...")
    
    pending_articles = NewsModel.get_articles_without_content(limit=20)
    
    if not pending_articles:
        logger.info("✅ Scrape edilecek haber yok")
        return
    
    logger.info(f"📰 {len(pending_articles)} haber scrape edilecek...")
    
    success = 0
    failed = 0
    
    for article in pending_articles:
        try:
            logger.info(f"🔄 Scraping: {article['title'][:50]}...")
            
            full_content = scrape_article_content(article['url'])
            
            if full_content:
                NewsModel.update_full_content(article['id'], full_content)
                success += 1
                logger.info(f"   ✅ Başarılı! ({len(full_content)} karakter)")
            else:
                failed += 1
                logger.warning(f"   ⚠️ İçerik çok kısa veya scrape edilemedi")
            
            time.sleep(5)
            
        except Exception as e:
            failed += 1
            logger.error(f"   ❌ Hata: {e}")
    
    logger.info(f"🎉 Scraping tamamlandı! Başarılı: {success}, Başarısız: {failed}")
