from newspaper import Article
from models.news_models import NewsModel
import time
import random
import logging

logger = logging.getLogger(__name__)

USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'
]


def scrape_article_content(url: str):
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


def scrape_all_pending_articles():
    logger.info("🔍 Scrape edilecek haberler aranıyor...")
    
    pending_articles = NewsModel.get_articles_without_content(limit=20)
    
    if not pending_articles:
        logger.info("✅ Scrape edilecek haber yok")
        return
    
    logger.info(f"📰 {len(pending_articles)} haber scrape edilecek...")
    
    success = 0
    failed = 0
    
    for idx, article in enumerate(pending_articles, 1):
        try:
            logger.info(f"🔄 [{idx}/{len(pending_articles)}] {article['title'][:60]}...")
            
            api_image = article.get('image')
            full_content, scraped_image = scrape_article_content(article['url'])
            
            if full_content:
                final_image = scraped_image if scraped_image else api_image
                
                NewsModel.update_full_content(
                    article['id'], 
                    full_content, 
                    final_image
                )
                success += 1
                
                char_count = len(full_content)
                word_count = len(full_content.split())
                
                if scraped_image:
                    logger.info(f"   ✅ {char_count} karakter, ~{word_count} kelime (Scraper görseli)")
                elif api_image:
                    logger.info(f"   ✅ {char_count} karakter, ~{word_count} kelime (API görseli yedek)")
                else:
                    logger.info(f"   ✅ {char_count} karakter, ~{word_count} kelime (görsel yok)")
            else:
                failed += 1
                logger.warning(f"   ⚠️ İçerik alınamadı")
            
            if idx < len(pending_articles):
                wait_time = random.randint(20, 35)
                logger.debug(f"   ⏰ {wait_time} saniye bekleniyor...")
                time.sleep(wait_time)
            
        except Exception as e:
            failed += 1
            logger.error(f"   ❌ Hata: {e}")
    
    logger.info(f"🎉 Scraping tamamlandı! Başarılı: {success}, Başarısız: {failed}")
