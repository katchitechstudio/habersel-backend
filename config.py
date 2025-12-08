import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    DEBUG = os.getenv("DEBUG", "False").lower() == "true"
    SECRET_KEY = os.getenv("SECRET_KEY", "super_secret_key_change_in_production")
    
    CRON_SECRET = os.getenv("CRON_SECRET", "CHANGE_THIS_SECRET_KEY_IN_PRODUCTION")
    
    DB_URL = os.getenv("DB_URL", "postgresql://username:password@localhost:5432/habersel")
    
    GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
    CURRENTS_API_KEY = os.getenv("CURRENTS_API_KEY", "")
    MEDIASTACK_KEY = os.getenv("MEDIASTACK_KEY", "")
    NEWSDATA_KEY = os.getenv("NEWSDATA_KEY", "")
    
    API_LIMITS = {
        "gnews": {
            "monthly": 3000,
            "daily": 100,
            "priority": 1
        },
        "currents": {
            "monthly": 600,
            "daily": 20,
            "priority": 2
        },
        "mediastack": {
            "monthly": 100,
            "daily": 3,
            "priority": 3
        },
        "newsdata": {
            "monthly": 100,
            "daily": 3,
            "priority": 4
        }
    }
    
    NEWS_EXPIRATION_DAYS = int(os.getenv("NEWS_EXPIRATION_DAYS", "3"))
    NEWS_CATEGORIES = ["general", "business", "technology", "world", "sports"]
    NEWS_PER_CATEGORY = {
        "gnews": 5,
        "currents": 5,
        "mediastack": 3,
        "newsdata": 3
    }
    
    CRON_SCHEDULE = {
        "midnight": {
            "time": "00:00",
            "hour": 0,
            "apis": ["gnews"],
            "categories": ["general", "world"],
            "scraping_count": 10
        },
        "late_night": {
            "time": "02:00",
            "hour": 2,
            "apis": ["currents"],
            "categories": ["sports", "general"],
            "scraping_count": 10
        },
        "early_morning": {
            "time": "04:00",
            "hour": 4,
            "apis": ["gnews"],
            "categories": ["general", "business"],
            "scraping_count": 10
        },
        "dawn": {
            "time": "06:00",
            "hour": 6,
            "apis": ["currents"],
            "categories": ["technology", "world"],
            "scraping_count": 10
        },
        "morning": {
            "time": "08:00",
            "hour": 8,
            "apis": ["gnews", "currents"],
            "categories": ["general", "business", "sports"],
            "scraping_count": 15
        },
        "mid_morning": {
            "time": "10:00",
            "hour": 10,
            "apis": ["mediastack"],
            "categories": ["general"],
            "scraping_count": 10
        },
        "noon": {
            "time": "12:00",
            "hour": 12,
            "apis": ["gnews", "mediastack"],
            "categories": ["business", "technology"],
            "scraping_count": 15
        },
        "afternoon": {
            "time": "14:00",
            "hour": 14,
            "apis": ["currents"],
            "categories": ["sports", "general"],
            "scraping_count": 10
        },
        "late_afternoon": {
            "time": "16:00",
            "hour": 16,
            "apis": ["gnews", "currents"],
            "categories": ["world", "technology"],
            "scraping_count": 15
        },
        "early_evening": {
            "time": "18:00",
            "hour": 18,
            "apis": ["mediastack"],
            "categories": ["general"],
            "scraping_count": 10
        },
        "evening": {
            "time": "20:00",
            "hour": 20,
            "apis": ["currents"],
            "categories": ["general", "sports"],
            "scraping_count": 15
        },
        "night": {
            "time": "22:00",
            "hour": 22,
            "apis": ["currents"],
            "categories": ["world", "general"],
            "scraping_count": 10
        }
    }
    
    TIMEZONE = os.getenv("TIMEZONE", "Europe/Istanbul")
    CACHE_DURATION = int(os.getenv("CACHE_DURATION", "3600"))
    
    SIMILARITY_THRESHOLD = int(os.getenv("SIMILARITY_THRESHOLD", "85"))
    TIME_DIFF_THRESHOLD = int(os.getenv("TIME_DIFF_THRESHOLD", "900"))
    
    LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
    LOG_FORMAT = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    RATE_LIMIT_PER_MINUTE = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    MAX_NEWS_PER_PAGE = int(os.getenv("MAX_NEWS_PER_PAGE", "50"))
    
    API_TIMEOUT = int(os.getenv("API_TIMEOUT", "10"))
    MAX_RETRIES = int(os.getenv("MAX_RETRIES", "3"))
    RETRY_DELAY = int(os.getenv("RETRY_DELAY", "2"))
