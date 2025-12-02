import requests
from typing import List, Dict, Optional
import logging

from config import Config
from services.api_manager import can_call, register_call, get_next_available_api

logger = logging.getLogger(__name__)

# Desteklenen kategoriler
CATEGORIES = Config.NEWS_CATEGORIES


# ------------------------------------------
# Ortak GET fonksiyonu (Geliştirilmiş)
# ------------------------------------------
def _safe_get(url: str, params: dict, api_name: str = "unknown") -> Optional[dict]:
    """
    Güvenli HTTP GET isteği
    """
    try:
        logger.debug(f"🌐 {api_name} → {url}")

        resp = requests.get(
            url,
            params=params,
            timeout=Config.API_TIMEOUT,
            headers={
                "User-Agent": "Habersel/1.0 (News Aggregator)"
            }
        )

        if resp.status_code == 429:
            logger.warning(f"⚠️  {api_name} rate limit hatası!")
            return None

        if resp.status_code == 401:
            logger.error(f"❌ {api_name} authentication hatası! API key kontrol et.")
            return None

        if resp.status_code != 200:
            logger.warning(f"⚠️  {api_name} HTTP {resp.status_code} hatası")
            return None

        data = resp.json()
        logger.debug(f"✅ {api_name} başarılı")
        return data

    except requests.exceptions.Timeout:
        logger.error(f"❌ {api_name} timeout ({Config.API_TIMEOUT}s)")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ {api_name} bağlantı hatası")
        return None
    except Exception as e:
        logger.error(f"❌ {api_name} beklenmeyen hata: {e}")
        return None


# ------------------------------------------
# GNEWS (En öncelikli API)
# ------------------------------------------
def fetch_gnews(category: str, limit: int = 5) -> List[Dict]:
    """
    GNews API'den haber çeker
    """
    api_name = "gnews"

    if not can_call(api_name, count=limit):
        logger.warning(f"⚠️  {api_name} limiti doldu, atlanıyor")
        return []

    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "category": category,
        "lang": "tr",
        "max": limit,
        "apikey": Config.GNEWS_API_KEY,
    }

    data = _safe_get(url, params, api_name)

    if not data:
        register_call(api_name, count=limit, success=False)
        return []

    articles = data.get("articles", [])

    if not articles:
        logger.warning(f"⚠️  {api_name} boş sonuç döndü")
        register_call(api_name, count=limit, success=False)
        return []

    register_call(api_name, count=min(limit, len(articles)), success=True)
    logger.info(f"✅ {api_name} → {len(articles)} haber çekildi ({category})")

    return [
        {
            "title": (a.get("title") or "").strip(),
            "description": (a.get("description") or "").strip(),
            "url": (a.get("url") or "").strip(),
            "image": a.get("image"),
            "source": (a.get("source", {}) or {}).get("name", "GNews"),
            "publishedAt": a.get("publishedAt"),
        }
        for a in articles
        if a.get("title") and a.get("url")
    ]


# ------------------------------------------
# Currents API
# ------------------------------------------
def fetch_currents(category: str, limit: int = 5) -> List[Dict]:
    """Currents API'den haber çeker"""
    api_name = "currents"

    if not can_call(api_name, count=limit):
        logger.warning(f"⚠️  {api_name} limiti doldu, atlanıyor")
        return []

    url = "https://api.currentsapi.services/v1/latest-news"
    params = {
        "category": category,
        "language": "tr",
        "apiKey": Config.CURRENTS_API_KEY,
    }

    data = _safe_get(url, params, api_name)

    if not data:
        register_call(api_name, count=limit, success=False)
        return []

    news = data.get("news", [])[:limit]

    if not news:
        logger.warning(f"⚠️  {api_name} boş sonuç döndü")
        register_call(api_name, count=limit, success=False)
        return []

    register_call(api_name, count=len(news), success=True)
    logger.info(f"✅ {api_name} → {len(news)} haber çekildi ({category})")

    return [
        {
            "title": (n.get("title") or "").strip(),
            "description": (n.get("description") or "").strip(),
            "url": (n.get("url") or "").strip(),
            "image": n.get("image"),
            "source": "Currents",
            "publishedAt": n.get("published"),
        }
        for n in news
        if n.get("title") and n.get("url")
    ]


# ------------------------------------------
# Mediastack
# ------------------------------------------
def fetch_mediastack(category: str, limit: int = 3) -> List[Dict]:
    """Mediastack API'den haber çeker"""
    api_name = "mediastack"

    if not can_call(api_name, count=limit):
        logger.warning(f"⚠️  {api_name} limiti doldu, atlanıyor")
        return []

    url = "http://api.mediastack.com/v1/news"
    params = {
        "access_key": Config.MEDIASTACK_KEY,
        "categories": category,
        "languages": "tr",
        "limit": limit,
        "sort": "published_desc",
    }

    data = _safe_get(url, params, api_name)

    if not data:
        register_call(api_name, count=limit, success=False)
        return []

    news_data = data.get("data", [])

    if not news_data:
        logger.warning(f"⚠️  {api_name} boş sonuç döndü")
        register_call(api_name, count=limit, success=False)
        return []

    register_call(api_name, count=min(limit, len(news_data)), success=True)
    logger.info(f"✅ {api_name} → {len(news_data)} haber çekildi ({category})")

    return [
        {
            "title": (d.get("title") or "").strip(),
            "description": (d.get("description") or "").strip(),
            "url": (d.get("url") or "").strip(),
            "image": d.get("image"),
            "source": "Mediastack",
            "publishedAt": d.get("published_at"),
        }
        for d in news_data
        if d.get("title") and d.get("url")
    ]


# ------------------------------------------
# NewsData (Yedek / Fallback)
# ------------------------------------------
def fetch_newsdata(category: str, limit: int = 3) -> List[Dict]:
    """NewsData API'den haber çeker (yedek olarak kullanılır)"""
    api_name = "newsdata"

    if not can_call(api_name, count=limit):
        logger.warning(f"⚠️  {api_name} limiti doldu, atlanıyor")
        return []

    url = "https://newsdata.io/api/1/news"
    params = {
        "apikey": Config.NEWSDATA_KEY,
        "category": category,
        "language": "tr",
        "size": limit,
    }

    data = _safe_get(url, params, api_name)

    if not data:
        register_call(api_name, count=limit, success=False)
        return []

    results = data.get("results", [])[:limit]

    if not results:
        logger.warning(f"⚠️  {api_name} boş sonuç döndü")
        register_call(api_name, count=limit, success=False)
        return []

    register_call(api_name, count=len(results), success=True)
    logger.info(f"✅ {api_name} → {len(results)} haber çekildi ({category})")

    return [
        {
            "title": (r.get("title") or "").strip(),
            "description": (r.get("description") or "").strip(),
            "url": (r.get("link") or "").strip(),
            "image": r.get("image_url"),
            "source": "NewsData",
            "publishedAt": r.get("pubDate"),
        }
        for r in results
        if r.get("title") and r.get("link")
    ]


# ------------------------------------------
# Akıllı Haber Çekme (Fallback Zinciri)
# ------------------------------------------
def get_news_from_best_source(category: str, exclude_apis: list = None) -> List[Dict]:
    """
    Öncelik sırasına göre ilk çalışan API'den haber alır.
    """
    if exclude_apis is None:
        exclude_apis = []

    api_functions = {
        "gnews": fetch_gnews,
        "currents": fetch_currents,
        "mediastack": fetch_mediastack,
        "newsdata": fetch_newsdata,
    }

    next_api = get_next_available_api(exclude=exclude_apis)

    if not next_api:
        logger.error(f"❌ {category} için hiçbir API kullanılamıyor!")
        return []

    fetch_func = api_functions.get(next_api)
    if not fetch_func:
        logger.error(f"❌ {next_api} için fonksiyon bulunamadı!")
        return []

    logger.info(f"🎯 {category} için {next_api} kullanılıyor...")

    news = fetch_func(category)

    if not news:
        logger.warning(f"⚠️  {next_api} başarısız, fallback deneniyor...")
        exclude_apis.append(next_api)
        return get_news_from_best_source(category, exclude_apis)

    return news


# ------------------------------------------
# Toplu Haber Çekme (Tüm kategoriler için)
# ------------------------------------------
def fetch_all_categories(api_name: str) -> Dict[str, List[Dict]]:
    """
    Belirli bir API'den tüm kategorilerdeki haberleri çeker
    """
    api_functions = {
        "gnews": fetch_gnews,
        "currents": fetch_currents,
        "mediastack": fetch_mediastack,
        "newsdata": fetch_newsdata,
    }

    fetch_func = api_functions.get(api_name)

    if not fetch_func:
        logger.error(f"❌ Bilinmeyen API: {api_name}")
        return {}

    results = {}

    for category in CATEGORIES:
        logger.info(f"📰 {api_name} → {category} çekiliyor...")
        news = fetch_func(category)
        results[category] = news

    return results
