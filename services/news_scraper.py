from newspaper import Article, Config as NewspaperConfig
from models.news_models import NewsModel
from utils.helpers import full_clean_news_pipeline
import time
import random
import logging
import threading
import ssl # 👈 YENİ: SSL kütüphanesi

logger = logging.getLogger(__name__)

# 🔥 SSL HACK: Sertifika hatalarını görmezden gel (Render için şart)
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# 🥸 KILIK DEĞİŞTİRME LİSTESİ
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def scrape_article_content(url: str):
    """
    Haber URL'sinden tam içeriği çeker (SSL Koruması Kaldırıldı)
    """
    try:
        user_agent = random.choice(USER_AGENTS)
        
        config = NewspaperConfig()
        config.browser_user_agent = user_agent
        config.request_timeout = 20 # Süreyi artırdık
        config.fetch_images = True
        config.memoize_articles = False # Önbellek yapma, taze çek
        
        # Haberi indir
        article = Article(url, language='tr', config=config)
        article.download()
        article.parse()
        
        full_text = article.text.strip()
        
        if len(full_text) < 200:
            logger.warning(f"⚠️ İçerik çok kısa, başarısız: {url}")
            return None, None
        
        scraped_image = article.top_image if article.top_image else None
        
        logger.info(f"✅ ÇEKİLDİ: {len(full_text)} karakter.")
        return full_text, scraped_image
        
    except Exception as e:
        logger.error(f"❌ Scrape hatası ({url}): {e}")
        return None, None

def scrape_latest_news(count=15):
    """
    En son scrape edilmemiş haberleri çeker
    """
    logger.info(f"🔍 Scrape işlemi başlıyor (Hedef: {count})...")
    
    pending_articles = NewsModel.get_unscraped(limit=count, exclude_blacklist=True)
    
    if not pending_articles:
        logger.info("✅ Scrape edilecek haber yok.")
        return
    
    success = 0
    failed = 0
    
    for idx, article in enumerate(pending_articles, 1):
        try:
            article_url = article['url']
            article_id = article['id']
            
            # İçeriği scrape et
            full_content, scraped_image = scrape_article_content(article_url)
            
            if full_content:
                # Temizle (Varsa helper, yoksa düz)
                try:
                    cleaned_data = full_clean_news_pipeline(
                        title=article.get('title', ''),
                        content=full_content,
                        description=article.get('description'),
                        date=article.get('published')
                    )
                    final_content = cleaned_data['content']
                except:
                    final_content = full_content

                final_image = scraped_image if scraped_image else article.get('image')
                
                # Kaydet
                NewsModel.update_full_content(article_id, final_content, final_image)
                success += 1
            else:
                failed += 1
                NewsModel.add_to_blacklist(article_url, reason="empty_content")
            
            time.sleep(1) # Hızlı gitme, banlanma
            
        except Exception as e:
            failed += 1
            logger.error(f"   ❌ Döngü Hatası: {e}")
    
    logger.info(f"🎉 Bitti! Başarılı: {success}, Başarısız: {failed}")
