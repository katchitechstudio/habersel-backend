import requests
from typing import List, Dict, Optional

from config import Config
from services.api_manager import can_call, register_call


# Uygulamada desteklenen kategoriler (config'ten çekilebilir)
CATEGORIES = Config.NEWS_CATEGORIES


# ------------------------------------------
# Ortak GET fonksiyonu (timeout + hata yakalama)
# ------------------------------------------
def _safe_get(url: str, params: dict) -> Optional[dict]:
    try:
        resp = requests.get(url, params=params, timeout=10)
        if resp.status_code != 200:
            return None
        return resp.json()
    except Exception:
        return None


# ------------------------------------------
# GNEWS
# ------------------------------------------
def fetch_gnews(category: str, limit: int = 5) -> List[Dict]:
    if not can_call("gnews"):
        return []

    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "category": category,
        "lang": "tr",
        "max": limit,
        "apikey": Config.GNEWS_API_KEY,
    }

    data = _safe_get(url, params)
    if not data:
        return []

    register_call("gnews")

    # Standart format: title, description, url, image, source
    return [
        {
            "title": a.get("title"),
            "description": a.get("description"),
            "url": a.get("url"),
            "image": a.get("image"),
            "source": "GNews",
        }
        for a in data.get("articles", [])
    ]


# ------------------------------------------
# Currents API
# ------------------------------------------
def fetch_currents(category: str, limit: int = 5) -> List[Dict]:
    if not can_call("currents"):
        return []

    url = "https://api.currentsapi.services/v1/latest-news"
    params = {
        "category": category,
        "apiKey": Config.CURRENTS_API_KEY,
    }

    data = _safe_get(url, params)
    if not data:
        return []

    register_call("currents")

    return [
        {
            "title": n.get("title"),
            "description": n.get("description"),
            "url": n.get("url"),
            "image": n.get("image"),
            "source": "Currents",
        }
        for n in data.get("news", [])[:limit]
    ]


# ------------------------------------------
# NewsAPI.ai
# ------------------------------------------
def fetch_newsapi_ai(category: str, limit: int = 2) -> List[Dict]:
    if not can_call("newsapi_ai"):
        return []

    url = "https://newsapi.ai/api/v1/article/getArticles"
    params = {
        "apikey": Config.NEWSAPI_AI_KEY,
        "sourceCountries": "tr",
        "categoryUri": category,
    }

    data = _safe_get(url, params)
    if not data:
        return []

    register_call("newsapi_ai")

    articles = data.get("articles", {}).get("results", [])
    return [
        {
            "title": a.get("title"),
            "description": a.get("body"),
            "url": a.get("url"),
            "image": a.get("image"),
            "source": "NewsAPI.ai",
        }
        for a in articles[:limit]
    ]


# ------------------------------------------
# Mediastack
# ------------------------------------------
def fetch_mediastack(category: str, limit: int = 3) -> List[Dict]:
    if not can_call("mediastack"):
        return []

    url = "http://api.mediastack.com/v1/news"
    params = {
        "access_key": Config.MEDIASTACK_KEY,
        "categories": category,
        "languages": "tr",
        "limit": limit,
    }

    data = _safe_get(url, params)
    if not data:
        return []

    register_call("mediastack")

    return [
        {
            "title": d.get("title"),
            "description": d.get("description"),
            "url": d.get("url"),
            "image": d.get("image"),
            "source": "Mediastack",
        }
        for d in data.get("data", [])
    ]


# ------------------------------------------
# NewsData (fallback)
# ------------------------------------------
def fetch_newsdata(category: str, limit: int = 3) -> List[Dict]:
    if not can_call("newsdata"):
        return []

    url = "https://newsdata.io/api/1/news"
    params = {
        "apikey": Config.NEWSDATA_KEY,
        "category": category,
        "language": "tr",
    }

    data = _safe_get(url, params)
    if not data:
        return []

    register_call("newsdata")

    return [
        {
            "title": r.get("title"),
            "description": r.get("description"),
            "url": r.get("link"),
            "image": r.get("image_url"),
            "source": "NewsData",
        }
        for r in data.get("results", [])[:limit]
    ]


# ------------------------------------------
# Fallback zinciri ile haber alma
# ------------------------------------------
def get_news_from_best_source(category: str) -> List[Dict]:
    """
    İlk çalışan API'den haber alır.
    Sıra:
    1) GNews
    2) Currents
    3) NewsAPI.ai
    4) Mediastack
    5) NewsData
    """

    funcs = [
        fetch_gnews,
        fetch_currents,
        fetch_newsapi_ai,
        fetch_mediastack,
        fetch_newsdata,
    ]

    for fn in funcs:
        news = fn(category)
        if news:
            return news

    return []  # tüm API'ler çökerse bile boş döner
