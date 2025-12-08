from newspaper import Article
from models.news_models import NewsModel
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
            
            if NewsModel.is_blacklisted(article_url, threshold=3):
                logger.debug(f"🚫 [{idx}/{len(pending_articles)}] Blacklist'te, atlanıyor: {article['title'][:60]}...")
                failed += 1
                continue
            
            logger.info(f"🔄 [{idx}/{len(pending_articles)}] {article['title'][:60]}...")
            
            api_image = article.get('image')
            full_content, scraped_image = scrape_article_content(article_url)
            
            if full_content:
                final_image = scraped_image if scraped_image else api_image
                
                NewsModel.update_full_content(
                    article_id, 
                    full_content, 
                    final_image
                )
                success += 1
                
                char_count = len(full_content)
                word_count = len(full_content.split())
                
                if scraped_image:
                    logger.info(f"   ✅ {char_count} karakter, ~{word_count} kelime (Scraper görseli)")
                elif api_image:
                    logger.info(f"   ✅ {char_count} karakter, ~{word_count} kelime (API görseli)")
                else:
                    logger.info(f"   ✅ {char_count} karakter, ~{word_count} kelime (görsel yok)")
            else:
                failed += 1
                NewsModel.add_to_blacklist(article_url, reason="content_extraction_failed")
                logger.warning(f"   ⚠️ İçerik alınamadı")
            
            if idx < len(pending_articles):
                wait_time = random.randint(25, 35)
                time.sleep(wait_time)
            
        except Exception as e:
            failed += 1
            NewsModel.add_to_blacklist(article['url'], reason=f"exception: {str(e)[:50]}")
            logger.error(f"   ❌ Hata: {e}")
    
    logger.info(f"🎉 Scraping tamamlandı! Başarılı: {success}, Başarısız: {failed}")


def scrape_all_pending_articles():
    scrape_latest_news(count=20)


def scrape_in_background(count=15):
    thread = threading.Thread(
        target=scrape_latest_news,
        args=(count,),
        daemon=True
    )
    thread.start()
    logger.info(f"🔥 Scraping arka planda başlatıldı ({count} haber)")
