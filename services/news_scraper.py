import requests
from bs4 import BeautifulSoup
from newspaper import Article
from models.news_models import NewsModel
from utils.helpers import full_clean_news_pipeline, clean_news_title, clean_news_content
from config import Config
import logging
import time
import re

logger = logging.getLogger(__name__)


class NewsScraper:
    
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.timeout = Config.API_TIMEOUT
        self.max_retries = 3
    
    def scrape_article(self, url: str, title: str = None) -> dict:
        if NewsModel.is_blacklisted(url):
            logger.debug(f"⏭️  Blacklist'te: {url[:60]}...")
            return {'success': False, 'error': 'blacklisted'}
        
        try:
            result = self._scrape_with_newspaper(url)
            
            if result['success']:
                cleaned = full_clean_news_pipeline(
                    title=result.get('title', title or ''),
                    content=result.get('content'),
                    description=None,
                    date=None
                )
                
                return {
                    'success': True,
                    'title': cleaned['title'],
                    'content': cleaned['content'],
                    'image': result.get('image'),
                    'error': None
                }
            
            logger.debug(f"📰 newspaper başarısız, BeautifulSoup deneniyor: {url[:60]}...")
            result = self._scrape_with_beautifulsoup(url)
            
            if result['success']:
                cleaned = full_clean_news_pipeline(
                    title=result.get('title', title or ''),
                    content=result.get('content'),
                    description=None,
                    date=None
                )
                
                return {
                    'success': True,
                    'title': cleaned['title'],
                    'content': cleaned['content'],
                    'image': result.get('image'),
                    'error': None
                }
            
            error_msg = result.get('error', 'unknown_error')
            NewsModel.add_to_blacklist(url, reason=error_msg)
            
            return {
                'success': False,
                'error': error_msg
            }
        
        except Exception as e:
            logger.error(f"❌ Scraping hatası ({url[:50]}): {e}")
            NewsModel.add_to_blacklist(url, reason=str(e))
            return {'success': False, 'error': str(e)}
    
    def _scrape_with_newspaper(self, url: str) -> dict:
        try:
            article = Article(url, language='tr')
            article.download()
            article.parse()
            
            content = article.text.strip()
            
            if not content or len(content) < 200:
                return {'success': False, 'error': 'content_too_short'}
            
            return {
                'success': True,
                'title': article.title or '',
                'content': content,
                'image': article.top_image or None
            }
        
        except Exception as e:
            logger.debug(f"⚠️  newspaper3k hatası: {e}")
            return {'success': False, 'error': f'newspaper_error: {e}'}
    
    def _scrape_with_beautifulsoup(self, url: str) -> dict:
        try:
            response = self.session.get(url, timeout=self.timeout)
            
            if response.status_code != 200:
                return {'success': False, 'error': f'http_{response.status_code}'}
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            title = None
            for selector in ['h1', 'title', '.article-title', '.post-title']:
                title_tag = soup.select_one(selector)
                if title_tag:
                    title = title_tag.get_text(strip=True)
                    break
            
            content = self._extract_content_beautifulsoup(soup)
            
            image = None
            img_tag = soup.select_one('meta[property="og:image"]')
            if img_tag:
                image = img_tag.get('content')
            
            if not content or len(content) < 200:
                return {'success': False, 'error': 'content_too_short'}
            
            return {
                'success': True,
                'title': title or '',
                'content': content,
                'image': image
            }
        
        except Exception as e:
            logger.debug(f"⚠️  BeautifulSoup hatası: {e}")
            return {'success': False, 'error': f'beautifulsoup_error: {e}'}
    
    def _extract_content_beautifulsoup(self, soup: BeautifulSoup) -> str:
        for element in soup(['script', 'style', 'nav', 'header', 'footer', 'aside', 'iframe']):
            element.decompose()
        
        content_selectors = [
            'article',
            '.article-content',
            '.post-content',
            '.entry-content',
            '.content',
            'main',
            '[itemprop="articleBody"]'
        ]
        
        for selector in content_selectors:
            content_div = soup.select_one(selector)
            if content_div:
                paragraphs = content_div.find_all('p')
                if paragraphs:
                    text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
                    if len(text) > 200:
                        return text
        
        paragraphs = soup.find_all('p')
        text = '\n\n'.join([p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True)])
        
        return text
    
    def scrape_batch(self, limit: int = 10) -> dict:
        stats = {
            'total_attempted': 0,
            'successful': 0,
            'failed': 0,
            'blacklisted': 0
        }
        
        unscraped = NewsModel.get_unscraped(limit=limit, exclude_blacklist=True)
        
        if not unscraped:
            logger.info("✨ Scrape edilecek haber kalmadı!")
            return stats
        
        stats['total_attempted'] = len(unscraped)
        logger.info(f"🚀 {len(unscraped)} haber scraping başlatılıyor...")
        
        for article in unscraped:
            article_id = article['id']
            url = article['url']
            title = article['title']
            
            logger.info(f"📄 Scraping: {title[:50]}...")
            
            result = self.scrape_article(url, title)
            
            if result['success']:
                cleaned_content = result['content']
                cleaned_title = result['title'] or title
                image = result.get('image') or article.get('image')
                
                NewsModel.update_full_content(article_id, cleaned_content, image)
                NewsModel.update_title(article_id, cleaned_title)
                
                stats['successful'] += 1
                logger.info(f"   ✅ Başarılı: {len(cleaned_content)} karakter (temizlendi)")
            
            else:
                stats['failed'] += 1
                error = result.get('error', 'unknown')
                
                if error == 'blacklisted':
                    stats['blacklisted'] += 1
                
                logger.warning(f"   ❌ Başarısız: {error}")
            
            time.sleep(1)
        
        logger.info("=" * 60)
        logger.info(f"🎉 SCRAPING BİTTİ")
        logger.info(f"✅ Başarılı: {stats['successful']}")
        logger.info(f"❌ Başarısız: {stats['failed']}")
        logger.info(f"🚫 Blacklist: {stats['blacklisted']}")
        logger.info("=" * 60)
        
        return stats


def test_scraper():
    scraper = NewsScraper()
    
    test_urls = [
        "https://www.bbc.com/turkce",
        "https://www.ntv.com.tr",
    ]
    
    for url in test_urls:
        print(f"\n{'='*60}")
        print(f"Testing: {url}")
        print('='*60)
        
        result = scraper.scrape_article(url)
        
        if result['success']:
            print(f"✅ Başarılı!")
            print(f"📝 Başlık: {result['title'][:80]}...")
            print(f"📄 İçerik: {len(result['content'])} karakter")
            print(f"🖼️  Resim: {result.get('image', 'Yok')}")
            print(f"\n📰 İlk 300 karakter:")
            print(result['content'][:300])
        else:
            print(f"❌ Başarısız: {result.get('error')}")


def scrape_latest_news(count: int = 10):
    """
    Manuel içerik doldurma için kullanılır.
    /force-fill endpoint'inden çağrılır.
    """
    scraper = NewsScraper()
    return scraper.scrape_batch(limit=count)


def scrape_in_background(count: int = 10):
    """
    Arka planda scraping yapar.
    Scheduler tarafından otomatik çağrılır.
    """
    scraper = NewsScraper()
    stats = scraper.scrape_batch(limit=count)
    logger.info(f"🤖 Background scraping tamamlandı: {stats}")
    return stats


if __name__ == "__main__":
    test_scraper()
