from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models.news_models import NewsModel
from services.scheduler import (
    morning_job,
    noon_job,
    evening_job,
    night_job,
    cleanup_job
)
from config import Config
import os
import json
import logging
from datetime import datetime
import pytz

# ====================================================
# LOGGING
# ====================================================
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# ====================================================
# LAST-RUNS DOSYASI (CRON TEKRARINI ENGELLEME)
# ====================================================
LAST_RUNS_FILE = "last_runs.json"


def load_last_runs():
    if not os.path.exists(LAST_RUNS_FILE):
        return {}
    try:
        with open(LAST_RUNS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ last_runs.json okunamadı: {e}")
        return {}


def save_last_runs(data):
    try:
        with open(LAST_RUNS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"❌ last_runs.json yazılamadı: {e}")


def should_run(task_name):
    """
    Bugün bu cron görevi çalıştı mı?
    Çalışmadıysa çalıştırır ve işaretler.
    """
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")

    runs = load_last_runs()

    if runs.get(task_name) == today:
        logger.info(f"⏭️  {task_name} bugün zaten çalıştı")
        return False

    runs[task_name] = today
    save_last_runs(runs)

    logger.info(f"▶️ {task_name} çalıştırılıyor...")
    return True


# ====================================================
# UYGULAMA OLUŞTURMA
# ====================================================
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # CORS
    CORS(app, resources={r"/*": {"origins": "*"}})

    # Rate Limiter
    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{Config.RATE_LIMIT_PER_MINUTE} per minute"],
        app=app
    )

    # ====================================================
    # DATABASE TABLE
    # ====================================================
    try:
        NewsModel.create_table()
    except Exception as e:
        logger.error(f"❌ DB tablo hatası: {e}")

    # ====================================================
    # ENDPOINT'LER
    # ====================================================

    # ---------------------------
    # HEALTH CHECK
    # ---------------------------
    @app.route("/health", methods=["GET"])
    def health():
        return jsonify({
            "status": "ok",
            "service": "habersel-backend",
            "timestamp": datetime.now(
                pytz.timezone(Config.TIMEZONE)
            ).isoformat()
        }), 200

    # ---------------------------
    # CRON
    # ---------------------------
    @app.route("/cron", methods=["GET"])
    def cron():
        key = request.args.get("key")
        if key != Config.CRON_SECRET:
            return jsonify({"error": "unauthorized"}), 401

        tz = pytz.timezone(Config.TIMEZONE)
        now = datetime.now(tz)
        hour = now.hour

        logger.info(f"⏰ /cron tetiklendi (TR: {now.strftime('%H:%M')})")

        results = []

        # 08:00
        if hour == 8 and should_run("morning"):
            try:
                morning_job()
                results.append("morning ✔️")
            except Exception as e:
                results.append(f"morning ❌ {e}")

        # 12:00
        elif hour == 12 and should_run("noon"):
            try:
                noon_job()
                results.append("noon ✔️")
            except Exception as e:
                results.append(f"noon ❌ {e}")

        # 18:00
        elif hour == 18 and should_run("evening"):
            try:
                evening_job()
                results.append("evening ✔️")
            except Exception as e:
                results.append(f"evening ❌ {e}")

        # 23:00
        elif hour == 23 and should_run("night"):
            try:
                night_job()
                results.append("night ✔️")
            except Exception as e:
                results.append(f"night ❌ {e}")

        # 03:00 temizlik
        elif hour == 3 and should_run("cleanup"):
            try:
                cleanup_job()
                results.append("cleanup ✔️")
            except Exception as e:
                results.append(f"cleanup ❌ {e}")

        else:
            results.append(f"{hour}:00 → görev yok")

        return jsonify({
            "status": "ok",
            "timestamp": now.isoformat(),
            "results": results
        }), 200

    # ---------------------------
    # HABER GETİRME
    # ---------------------------
    @app.route("/news", methods=["GET"])
    @limiter.limit("60 per minute")
    def get_news():
        try:
            category = request.args.get("category")
            limit = min(int(request.args.get("limit", 50)), Config.MAX_NEWS_PER_PAGE)
            offset = int(request.args.get("offset", 0))

            data = NewsModel.get_news(category, limit, offset)

            return jsonify({
                "success": True,
                "count": len(data),
                "news": data
            })

        except Exception as e:
            logger.exception("❌ /news hatası")
            return jsonify({"success": False, "error": str(e)}), 500

    # ---------------------------
    # SON GÜNCELLEME
    # ---------------------------
    @app.route("/news/last-update", methods=["GET"])
    def last_update():
        try:
            ts = NewsModel.get_latest_update_time()
            return jsonify({
                "success": True,
                "last_update": ts.isoformat() if ts else None,
                "timestamp": datetime.now(
                    pytz.timezone(Config.TIMEZONE)
                ).isoformat()
            })
        except Exception as e:
            logger.exception("❌ /news/last-update")
            return jsonify({"success": False, "error": str(e)}), 500

    # ---------------------------
    # KATEGORİ İSTATİSTİK
    # ---------------------------
    @app.route("/news/stats", methods=["GET"])
    def stats():
        try:
            out = {cat: NewsModel.count_by_category(cat) for cat in Config.NEWS_CATEGORIES}
            return jsonify({"success": True, "stats": out, "total": sum(out.values())})
        except Exception as e:
            logger.exception("❌ /news/stats")
            return jsonify({"success": False, "error": str(e)}), 500

    # ---------------------------
    # API Kullanım
    # ---------------------------
    @app.route("/api/usage", methods=["GET"])
    def api_usage():
        try:
            from services.api_manager import get_all_usage, get_daily_summary
            return jsonify({
                "success": True,
                "timestamp": datetime.now(pytz.timezone(Config.TIMEZONE)).isoformat(),
                "apis": get_all_usage(),
                "summary": get_daily_summary()
            })
        except Exception as e:
            logger.exception("❌ /api/usage")
            return jsonify({"success": False, "error": str(e)}), 500

    # ---------------------------
    # 404
    # ---------------------------
    @app.errorhandler(404)
    def error_404(e):
        return jsonify({
            "error": "not_found",
            "endpoints": [
                "/health",
                "/news",
                "/news/stats",
                "/news/last-update",
                "/cron?key=SECRET"
            ]
        }), 404

    # ---------------------------
    # 500
    # ---------------------------
    @app.errorhandler(500)
    def error_500(e):
        return jsonify({
            "error": "server_error",
            "message": str(e)
        }), 500

    return app


# ====================================================
# GUNICORN ENTRY POINT
# ====================================================
app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    logger.info("🚀 Habersel backend başlıyor...")
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
