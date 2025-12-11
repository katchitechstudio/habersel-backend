from newspaper import Article, Config as NewspaperConfig
from models.news_models import NewsModel
from utils.helpers import full_clean_news_pipeline
import time
import random
import logging
import threading

logger = logging.getLogger(__name__)

# 🥸 KILIK DEĞİŞTİRME LİSTESİ (User-Agents)
# Bu listeyle siteye "Ben Chrome'um", "Ben Firefox'um" diyeceğiz.
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:121.0) Gecko/20100101 Firefox/121.0'
]

def scrape_article_content(url: str):
    """
    Haber URL'sinden tam içeriği çeker (Gelişmiş Ayarlar ile)
    """
    try:
        # Rastgele bir kimlik seç
        user_agent = random.choice(USER_AGENTS)
        
        # Newspaper kütüphanesini kandırmak için ayarlar
        config = NewspaperConfig()
        config.browser_user_agent = user_agent
        config.request_timeout = 15 # 15 saniye bekle
        config.fetch_images = True
        
        article = Article(url, language='tr', config=config)
        article.download()
        article.parse()
        
        full_text = article.text.strip()
        
        # Eğer metin çok kısaysa (mesela 200 karakterden az), muhtemelen hata vermiştir veya sadece özet çekmiştir.
        if len(full_text) < 200:
            logger.warning(f"⚠️ İçerik çok kısa ({len(full_text)} karakter), başarısız sayıldı: {url}")
            return None, None
        
        scraped_image = article.top_image if article.top_image else None
        
        logger.debug(f"✅ Başarılı Scrape: {len(full_text)} karakter çekildi.")
        return full_text, scraped_image
        
    except Exception as e:
        logger.error(f"❌ Scrape hatası ({url}): {e}")
        return None, None


def scrape_latest_news(count=15):
    """
    En son scrape edilmemiş haberleri çeker ve veritabanına kaydeder
    """
    logger.info(f"🔍 Scrape edilecek haberler aranıyor... (Hedef: {count})")
    
    pending_articles = NewsModel.get_unscraped(limit=count, exclude_blacklist=True)
    
    if not pending_articles:
        logger.info("✅ Scrape edilecek haber yok (Hepsi dolu)")
        return
    
    logger.info(f"📰 {len(pending_articles)} haber işleme alındı...")
    
    success = 0
    failed = 0
    
    for idx, article in enumerate(pending_articles, 1):
        try:
            article_url = article['url']
            article_id = article['id']
            article_title = article.get('title', '')
            
            # Blacklist kontrolü
            if NewsModel.is_blacklisted(article_url, threshold=3):
                logger.debug(f"🚫 Blacklist, atlanıyor: {article_title[:30]}...")
                failed += 1
                continue
            
            logger.info(f"🔄 [{idx}/{len(pending_articles)}] İndiriliyor: {article_title[:40]}...")
            
            # İçeriği scrape et
            full_content, scraped_image = scrape_article_content(article_url)
            
            if full_content:
                # İçeriği temizle (Gereksiz boşlukları vs at)
                # Not: helper fonksiyonu yoksa düz metni kullanırız
                try:
                    cleaned_data = full_clean_news_pipeline(
                        title=article_title,
                        content=full_content,
                        description=article.get('description'),
                        date=article.get('published')
                    )
                    final_content = cleaned_data['content']
                except:
                    final_content = full_content

                # Görsel seçimi
                api_image = article.get('image')
                final_image = scraped_image if scraped_image else api_image
                
                # Veritabanına kaydet
                NewsModel.update_full_content(
                    article_id, 
                    final_content, 
                    final_image
                )
                
                success += 1
                logger.info(f"   ✅ KAYDEDİLDİ: {len(final_content)} karakter.")
            else:
                failed += 1
                NewsModel.add_to_blacklist(article_url, reason="content_empty")
                logger.warning(f"   ⚠️ İçerik boş döndü, pas geçildi.")
            
            # ⏳ Site bizi engellemesin diye azıcık bekle (1-3 saniye)
            time.sleep(random.uniform(1.0, 3.0))
            
        except Exception as e:
            failed += 1
            logger.error(f"   ❌ Kritik Hata: {e}")
    
    logger.info(f"🎉 Scraping Turu Bitti! Başarılı: {success}, Başarısız: {failed}")

def scrape_in_background(count=15):
    """Arka planda çalıştır"""
    thread = threading.Thread(target=scrape_latest_news, args=(count,), daemon=True)
    thread.start()
