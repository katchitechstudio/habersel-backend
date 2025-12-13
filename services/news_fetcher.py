import requests
from typing import List, Dict, Optional
import logging

from config import Config
from services.api_manager import can_call, register_call, get_next_available_api

logger = logging.getLogger(__name__)

CATEGORIES = Config.NEWS_CATEGORIES


def _safe_get(url: str, params: dict, api_name: str = "unknown") -> Optional[dict]:
    try:
        logger.debug(f"🌐 {api_name} → {url}")

        resp = requests.get(
            url,
            params=params,
            timeout=Config.API_TIMEOUT,
            headers={"User-Agent": "Habersel/1.0 (News Aggregator)"}
        )

        if resp.status_code == 429:
            logger.warning(f"⚠️  {api_name} rate limit!")
            return None

        if resp.status_code == 401:
            logger.error(f"❌ {api_name} auth hatası (API KEY yanlış)")
            return None

        if resp.status_code != 200:
            logger.warning(f"⚠️  {api_name} HTTP {resp.status_code} hatası")
            return None

        return resp.json()

    except requests.exceptions.Timeout:
        logger.error(f"❌ {api_name} timeout ({Config.API_TIMEOUT}s)")
        return None
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ {api_name} bağlantı hatası")
        return None
    except Exception as e:
        logger.error(f"❌ {api_name} bilinmeyen hata: {e}")
        return None


def fetch_newsapi(category: str, limit: int = 5) -> List[Dict]:
    api_name = "newsapi"

    if not can_call(api_name, limit):
        logger.warning(f"⚠️ limit dolu → {api_name}")
        return []

    category_map = {
        "general": "general",
        "business": "business",
        "technology": "technology",
        "world": "general",
        "sports": "sports"
    }

    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "country": "tr",
        "category": category_map.get(category, "general"),
        "pageSize": limit,
        "apiKey": Config.NEWSAPI_KEY,
    }

    data = _safe_get(url, params, api_name)
    if not data:
        register_call(api_name, limit, False)
        return []

    articles = data.get("articles", [])
    if not articles:
        register_call(api_name, limit, False)
        return []

    register_call(api_name, min(limit, len(articles)), True)

    return [
        {
            "title": (x.get("title") or "").strip(),
            "description": (x.get("description") or "").strip(),
            "url": (x.get("url") or "").strip(),
            "image": x.get("urlToImage"),
            "source": (x.get("source", {}) or {}).get("name", "NewsAPI"),
            "publishedAt": x.get("publishedAt"),
        }
        for x in articles
        if x.get("title") and x.get("url")
    ]


def fetch_gnews(category: str, limit: int = 5) -> List[Dict]:
    api_name = "gnews"

    if not can_call(api_name, limit):
        logger.warning(f"⚠️ limit dolu → {api_name}")
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
        register_call(api_name, limit, False)
        return []

    articles = data.get("articles", [])
    if not articles:
        register_call(api_name, limit, False)
        return []

    register_call(api_name, min(limit, len(articles)), True)

    return [
        {
            "title": (x.get("title") or "").strip(),
            "description": (x.get("description") or "").strip(),
            "url": (x.get("url") or "").strip(),
            "image": x.get("image"),
            "source": (x.get("source", {}) or {}).get("name", "GNews"),
            "publishedAt": x.get("publishedAt"),
        }
        for x in articles
        if x.get("title") and x.get("url")
    ]


def fetch_currents(category: str, limit: int = 5) -> List[Dict]:
    api_name = "currents"

    if not can_call(api_name, limit):
        return []

    url = "https://api.currentsapi.services/v1/latest-news"
    params = {
        "category": category,
        "language": "tr",
        "apiKey": Config.CURRENTS_API_KEY,
    }

    data = _safe_get(url, params, api_name)
    if not data:
        register_call(api_name, limit, False)
        return []

    news = data.get("news", [])[:limit]
    if not news:
        register_call(api_name, limit, False)
        return []

    register_call(api_name, len(news), True)

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


def fetch_mediastack(category: str, limit: int = 3) -> List[Dict]:
    api_name = "mediastack"

    if not can_call(api_name, limit):
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
        register_call(api_name, limit, False)
        return []

    news = data.get("data", [])
    if not news:
        register_call(api_name, limit, False)
        return []

    register_call(api_name, min(limit, len(news)), True)

    return [
        {
            "title": (x.get("title") or "").strip(),
            "description": (x.get("description") or "").strip(),
            "url": (x.get("url") or "").strip(),
            "image": x.get("image"),
            "source": "Mediastack",
            "publishedAt": x.get("published_at"),
        }
        for x in news
        if x.get("title") and x.get("url")
    ]


def fetch_newsdata(category: str, limit: int = 3) -> List[Dict]:
    api_name = "newsdata"

    if not can_call(api_name, limit):
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
        register_call(api_name, limit, False)
        return []

    results = data.get("results", [])[:limit]
    if not results:
        register_call(api_name, limit, False)
        return []

    register_call(api_name, len(results), True)

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


def get_news_from_best_source(category: str, exclude_apis: list = None) -> List[Dict]:
    if exclude_apis is None:
        exclude_apis = []

    api_funcs = {
        "newsapi": fetch_newsapi,
        "gnews": fetch_gnews,
        "currents": fetch_currents,
        "mediastack": fetch_mediastack,
        "newsdata": fetch_newsdata,
    }

    next_api = get_next_available_api(exclude=exclude_apis)
    if not next_api:
        logger.error(f"❌ {category} için kullanılabilir API KALMADI!")
        return []

    fetch_func = api_funcs.get(next_api)
    if not fetch_func:
        return []

    logger.info(f"🎯 {category}: {next_api} kullanılıyor...")

    news = fetch_func(category)
    if not news:
        exclude_apis.append(next_api)
        return get_news_from_best_source(category, exclude_apis)

    return news


def fetch_all_categories(api_name: str) -> Dict[str, List[Dict]]:
    api_funcs = {
        "newsapi": fetch_newsapi,
        "gnews": fetch_gnews,
        "currents": fetch_currents,
        "mediastack": fetch_mediastack,
        "newsdata": fetch_newsdata,
    }

    func = api_funcs.get(api_name)
    if not func:
        logger.error(f"❌ Bilinmeyen API: {api_name}")
        return {}

    results = {}
    for category in CATEGORIES:
        logger.info(f"📰 {api_name} → {category}")
        results[category] = func(category)

    return results
