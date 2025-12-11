from newspaper import Article, Config as NewspaperConfig
from models.news_models import NewsModel
from utils.helpers import full_clean_news_pipeline
import time
import random
import logging
import threading
import ssl
import requests
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

# 🔥 SSL HACK
try:
    _create_unverified_https_context = ssl._create_unverified_context
except AttributeError:
    pass
else:
    ssl._create_default_https_context = _create_unverified_https_context

# 🥸 USER AGENT LİSTESİ
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

def scrape_with_beautifulsoup(url: str) -> tuple:
    """
    BeautifulSoup ile manuel scraping (newspaper başarısız olursa)
    """
    try:
        headers = {
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Accept-Encoding': 'gzip, deflate, br',
            'Connection': 'keep-alive',
        }
        
        response = requests.get(url, headers=headers, timeout=20, verify=False)
        response.raise_for_status()
        response.encoding = 'utf-8'
        
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 🗑️ Gereksiz elementleri sil
        for tag in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 
                        'iframe', 'noscript', 'button', 'form']):
            tag.decompose()
        
        # 📰 İçerik alanını bul (yaygın selector'lar)
        content_selectors = [
            'article',
            'div.article-content',
            'div.post-content',
            'div.entry-content',
            'div.content',
            'div.news-content',
            'div.detail-content',
            'div[itemprop="articleBody"]',
            'div.story-body',
            'div.article-body',
            'main',
        ]
        
        content_element = None
        for selector in content_selectors:
            content_element = soup.select_one(selector)
            if content_element:
                break
        
        # Eğer özel selector bulamazsa tüm <p> tag'lerini topla
        if not content_element:
            content_element = soup
        
        # 📝 Tüm paragrafları topla
        paragraphs = []
        for p in content_element.find_all(['p', 'h2', 'h3', 'blockquote']):
            text = p.get_text(strip=True)
            # En az 30 karakter olan paragrafları al
            if len(text) >= 30:
                paragraphs.append(text)
        
        full_text = '\n\n'.join(paragraphs)
        
        # 🖼️ Resim bul
        image_url = None
        img_selectors = [
            'meta[property="og:image"]',
            'article img',
            'div.article-content img',
            'div.post-content img',
        ]
        
        for selector in img_selectors:
            img_tag = soup.select_one(selector)
            if img_tag:
                image_url = img_tag.get('content') or img_tag.get('src')
                if image_url:
                    break
        
        logger.info(f"✅ BeautifulSoup ile çekildi: {len(full_text)} karakter")
        return full_text, image_url
        
    except Exception as e:
        logger.error(f"❌ BeautifulSoup scrape hatası: {e}")
        return None, None


def scrape_article_content(url: str):
    """
    🎯 ADVANCED SCRAPING: newspaper3k + BeautifulSoup kombinasyonu
    """
    try:
        user_agent = random.choice(USER_AGENTS)
        
        # 1️⃣ Önce newspaper3k dene
        config = NewspaperConfig()
        config.browser_user_agent = user_agent
        config.request_timeout = 20
        config.fetch_images = True
        config.memoize_articles = False
        
        article = Article(url, language='tr', config=config)
        article.download()
        article.parse()
        
        full_text = article.text.strip()
        scraped_image = article.top_image if article.top_image else None
        
        # 2️⃣ İçerik çok kısaysa BeautifulSoup ile tekrar dene
        if len(full_text) < 800:  # 800 karakterden az = EKSİK İÇERİK
            logger.warning(f"⚠️ Newspaper kısa çekti ({len(full_text)} char), BeautifulSoup deneniyor...")
            
            bs_text, bs_image = scrape_with_beautifulsoup(url)
            
            # Hangisi daha uzunsa onu kullan
            if bs_text and len(bs_text) > len(full_text):
                logger.info(f"✅ BeautifulSoup daha iyi sonuç verdi: {len(bs_text)} > {len(full_text)}")
                full_text = bs_text
                if bs_image and not scraped_image:
                    scraped_image = bs_image
        
        # 3️⃣ Hala çok kısaysa başarısız say
        if len(full_text) < 300:
            logger.warning(f"⚠️ İçerik hala çok kısa ({len(full_text)} char), başarısız sayılıyor")
            return None, None
        
        logger.info(f"✅ BAŞARILI SCRAPE: {len(full_text)} karakter çekildi")
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
            
            logger.info(f"🔄 [{idx}/{len(pending_articles)}] Scraping: {article['title'][:60]}...")
            
            # İçeriği scrape et
            full_content, scraped_image = scrape_article_content(article_url)
            
            if full_content:
                # Temizle
                try:
                    cleaned_data = full_clean_news_pipeline(
                        title=article.get('title', ''),
                        content=full_content,
                        description=article.get('description'),
                        date=article.get('published')
                    )
                    final_content = cleaned_data['content']
                    
                    # Temizleme sonrası kontrol
                    if not final_content or len(final_content) < 200:
                        logger.warning(f"⚠️ Temizleme sonrası içerik çok kısa: {article_id}")
                        failed += 1
                        NewsModel.add_to_blacklist(article_url, reason="content_too_short_after_cleaning")
                        continue
                        
                except Exception as clean_err:
                    logger.warning(f"⚠️ Temizleme hatası, ham içerik kullanılıyor: {clean_err}")
                    final_content = full_content

                final_image = scraped_image if scraped_image else article.get('image')
                
                # Kaydet
                NewsModel.update_full_content(article_id, final_content, final_image)
                logger.info(f"   ✅ Kaydedildi: {len(final_content)} karakter")
                success += 1
            else:
                failed += 1
                NewsModel.add_to_blacklist(article_url, reason="empty_content")
                logger.info(f"   ❌ Başarısız: İçerik çekilemedi")
            
            # Rate limiting
            time.sleep(random.uniform(1.5, 3.0))
            
        except Exception as e:
            failed += 1
            logger.error(f"   ❌ Döngü Hatası: {e}")
    
    logger.info(f"🎉 Bitti! ✅ Başarılı: {success}, ❌ Başarısız: {failed}")


def scrape_in_background(count=15):
    """
    Scraping işlemini arka planda başlatır
    """
    thread = threading.Thread(
        target=scrape_latest_news,
        args=(count,),
        daemon=True
    )
    thread.start()
    logger.info(f"🔥 Scraping arka planda başlatıldı ({count} haber)")


# 🆕 MANUEL TEST FONKSİYONU
def test_single_url(url: str):
    """
    Tek bir URL'i test et (debugging için)
    
    Kullanım:
        from services.news_scraper import test_single_url
        test_single_url("https://example.com/haber-linki")
    """
    print(f"\n🔍 Test ediliyor: {url}\n")
    
    content, image = scrape_article_content(url)
    
    if content:
        print(f"✅ BAŞARILI!")
        print(f"📏 Karakter sayısı: {len(content)}")
        print(f"🖼️ Resim: {image}")
        print(f"\n📰 İlk 500 karakter:\n{content[:500]}\n")
        print(f"📰 Son 500 karakter:\n{content[-500:]}\n")
    else:
        print(f"❌ BAŞARISIZ - İçerik çekilemedi")
    
    return content, image
