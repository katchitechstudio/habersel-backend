from flask import Blueprint, jsonify, request
from models.news_models import NewsModel
from services.news_service import NewsService
from datetime import datetime
import pytz
from config import Config
import logging

logger = logging.getLogger(__name__)

news_bp = Blueprint("news", __name__, url_prefix="/api/news")


@news_bp.route("/scraped", methods=["GET"])
def get_scraped_news():
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        category = request.args.get('category', None, type=str)
        
        if limit > 200:
            limit = 200
        
        news = NewsModel.get_scraped_only(
            category=category,
            limit=limit,
            offset=offset
        )
        
        total_scraped = NewsModel.count_scraped()
        
        logger.info(f"📱 Android request: {len(news)} scrape edilmiş haber döndürüldü")
        
        return jsonify({
            "success": True,
            "count": len(news),
            "total_scraped": total_scraped,
            "has_more": (offset + len(news)) < total_scraped,
            "news": news
        })
        
    except Exception as e:
        logger.exception("❌ /scraped endpoint hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@news_bp.route("/scraped/after", methods=["GET"])
def get_scraped_after():
    try:
        after = request.args.get('after', type=str)
        limit = request.args.get('limit', 50, type=int)
        category = request.args.get('category', None, type=str)
        
        if not after:
            return jsonify({
                "success": False,
                "error": "Missing required parameter: 'after' (ISO date)"
            }), 400
        
        if limit > 200:
            limit = 200
        
        news = NewsModel.get_scraped_after(
            after_date=after,
            category=category,
            limit=limit
        )
        
        logger.info(f"📱 Worker request: {after} sonrası {len(news)} yeni haber")
        
        return jsonify({
            "success": True,
            "count": len(news),
            "after": after,
            "news": news
        })
        
    except ValueError as e:
        return jsonify({
            "success": False,
            "error": f"Invalid date format: {str(e)}"
        }), 400
    except Exception as e:
        logger.exception("❌ /scraped/after endpoint hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@news_bp.route("/scraped/stats", methods=["GET"])
def scraped_stats():
    try:
        scraped = NewsModel.count_scraped()
        unscraped = NewsModel.count_unscraped()
        blacklisted = NewsModel.get_blacklist_count()
        total = NewsModel.get_total_count()
        
        return jsonify({
            "success": True,
            "scraped": scraped,
            "unscraped": unscraped,
            "blacklisted": blacklisted,
            "total": total,
            "scraping_rate": round((scraped / total * 100) if total > 0 else 0, 1)
        })
        
    except Exception as e:
        logger.exception("❌ /scraped/stats hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@news_bp.route("/latest", methods=["GET"])
def latest_news():
    try:
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)
        
        news = NewsModel.get_news(limit=limit, offset=offset)
        
        return jsonify({
            "success": True,
            "count": len(news),
            "news": news
        })
    except Exception as e:
        logger.exception("❌ /latest endpoint hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@news_bp.route("/last-update", methods=["GET"])
def last_update():
    try:
        dt = NewsModel.get_latest_update_time()
        
        if not dt:
            return jsonify({
                "success": True,
                "last_update": None,
                "has_data": False
            })
        
        tz = pytz.timezone(Config.TIMEZONE)
        dt_local = dt.astimezone(tz)
        
        return jsonify({
            "success": True,
            "last_update": dt_local.isoformat(),
            "timestamp_unix": int(dt_local.timestamp()),
            "has_data": True
        })
        
    except Exception as e:
        logger.exception("❌ /last-update hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@news_bp.route("/update", methods=["POST", "GET"])
def update_news():
    try:
        stats = NewsService.update_all_categories(api_source="auto")
        
        return jsonify({
            "success": True,
            "message": "Haberler güncellendi.",
            "stats": stats
        })
        
    except Exception as e:
        logger.exception("❌ /update hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@news_bp.route("/status", methods=["GET"])
def system_status():
    try:
        status = NewsService.get_system_status()
        
        db_last = status["database"].get("latest_update")
        if isinstance(db_last, datetime):
            status["database"]["latest_update"] = db_last.isoformat()
        
        status["scraping"] = {
            "scraped": NewsModel.count_scraped(),
            "unscraped": NewsModel.count_unscraped(),
            "blacklisted": NewsModel.get_blacklist_count()
        }
        
        return jsonify(status)
        
    except Exception as e:
        logger.exception("❌ /status hatası")
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


@news_bp.route("/health", methods=["GET"])
def health():
    return jsonify({
        "success": True,
        "status": "OK"
    })


@news_bp.route("/blacklist", methods=["GET"])
def get_blacklist():
    try:
        count = NewsModel.get_blacklist_count()
        
        return jsonify({
            "success": True,
            "blacklisted_urls": count,
            "message": f"{count} URL blacklist'te"
        })
        
    except Exception as e:
        logger.exception("❌ /blacklist hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@news_bp.route("/unscraped", methods=["GET"])
def get_unscraped():
    try:
        limit = request.args.get('limit', 20, type=int)
        
        articles = NewsModel.get_unscraped(limit=limit)
        
        return jsonify({
            "success": True,
            "count": len(articles),
            "total_unscraped": NewsModel.count_unscraped(),
            "articles": articles
        })
        
    except Exception as e:
        logger.exception("❌ /unscraped hatası")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
