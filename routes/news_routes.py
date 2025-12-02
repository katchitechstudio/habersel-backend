from flask import Blueprint, jsonify
from models.news_models import NewsModel
from services.news_service import NewsService
from datetime import datetime
import pytz
from config import Config

news_bp = Blueprint("news", __name__, url_prefix="/api/news")


# ============================================================
# 1) EN SON 100 HABER (APP HOME SCREEN)
# ============================================================
@news_bp.route("/latest", methods=["GET"])
def latest_news():
    try:
        news = NewsModel.get_news(limit=100)

        return jsonify({
            "success": True,
            "count": len(news),
            "news": news
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# 2) SADECE SON GÜNCELLEME ZAMANI
# (App açılışında küçük ve hızlı kontrol için ideal)
# ============================================================
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
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# 3) MANUEL GÜNCELLEME (admin/manual trigger)
# ============================================================
@news_bp.route("/update", methods=["POST", "GET"])
def update_news():
    """
    Cron dışında manuel tetiklemek için.
    'auto' → fallback-chain (gnews → currents → newsapi_ai)
    """
    try:
        stats = NewsService.update_all_categories(api_source="auto")

        return jsonify({
            "success": True,
            "message": "Haberler güncellendi.",
            "stats": stats
        })

    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


# ============================================================
# 4) SİSTEM SAĞLIK ve DURUM ENDPOINT'i
# ============================================================
@news_bp.route("/status", methods=["GET"])
def system_status():
    """
    API kullanım durumları ve DB istatistikleri.
    Monitoring / dashboard için ideal.
    """
    try:
        status = NewsService.get_system_status()

        # datetime objesi varsa isoformat'a çevirelim
        db_last = status["database"].get("latest_update")
        if isinstance(db_last, datetime):
            status["database"]["latest_update"] = db_last.isoformat()

        return jsonify(status)

    except Exception as e:
        return jsonify({
            "status": "error",
            "error": str(e)
        }), 500


# ============================================================
# 5) SAĞLIK KONTROLÜ
# ============================================================
@news_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"success": True, "status": "OK"})

