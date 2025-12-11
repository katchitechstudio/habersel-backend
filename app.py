from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models.news_models import NewsModel
from routes.news_routes import news_bp
from services.scheduler import (
    midnight_job,
    late_night_job,
    early_morning_job,
    dawn_job,
    morning_job,
    mid_morning_job,
    noon_job,
    afternoon_job,
    late_afternoon_job,
    early_evening_job,
    evening_job,
    night_job,
    cleanup_job,
    # 🆕 SCRAPING-ONLY JOB'LARI
    morning_scraping_job,
    afternoon_scraping_job,
    evening_scraping_job
)
from config import Config
from services.init_db import init_database, verify_tables
import os
import json
import logging
from datetime import datetime
import pytz

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

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


def should_run(task_name, hour_utc):
    now_utc = datetime.now(pytz.UTC)
    today = now_utc.strftime("%Y-%m-%d")
    current_hour_str = f"{today}_{hour_utc:02d}"

    runs = load_last_runs()

    if runs.get(task_name) == current_hour_str:
        logger.info(f"⏭️  {task_name} bugün UTC {hour_utc:02d}:00'de zaten çalıştı")
        return False

    runs[task_name] = current_hour_str
    save_last_runs(runs)

    logger.info(f"▶️ {task_name} çalıştırılıyor...")
    return True


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/*": {"origins": "*"}})

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{Config.RATE_LIMIT_PER_MINUTE} per minute"],
        app=app
    )

    try:
        init_database()
        verify_tables()
        logger.info("✅ Veritabanı başlatma tamamlandı")
    except Exception as e:
        logger.error(f"❌ init_database hatası: {e}")

    try:
        NewsModel.create_table()
        logger.info("✅ NewsModel tabloları hazır")
    except Exception as e:
        logger.error(f"❌ NewsModel tablo hatası: {e}")

    try:
        from models.system_models import SystemModel
        SystemModel.init_table()
        logger.info("✅ SystemInfo tablosu hazır")
    except Exception as e:
        logger.error(f"❌ SystemInfo tablo hatası: {e}")

    app.register_blueprint(news_bp)

    @app.route("/health", methods=["GET", "HEAD"])
    def health():
        return jsonify({
            "status": "ok",
            "service": "habersel-backend",
            "timestamp": datetime.now(pytz.UTC).isoformat()
        }), 200

    @app.route("/cron", methods=["GET", "HEAD"])
    def cron():
        key = request.args.get("key")
        if key != Config.CRON_SECRET:
            return jsonify({"error": "unauthorized"}), 401
        
        now_utc = datetime.now(pytz.UTC)
        hour_utc = now_utc.hour
        
        tz_tr = pytz.timezone(Config.TIMEZONE)
        now_tr = now_utc.astimezone(tz_tr)
        
        logger.info(f"⏰ /cron tetiklendi (UTC: {hour_utc:02d}:{now_utc.minute:02d}, TR: {now_tr.strftime('%H:%M')})")
        
        results = []
        
        # ============================================
        # HABER TOPLAMA JOB'LARI (Günde 12 kez)
        # ============================================
        
        if 21 <= hour_utc < 22:  # 00:00 TR
            if should_run("midnight", 21):
                try:
                    result = midnight_job()
                    if not result or not result.get("skipped"):
                        results.append("midnight ✅")
                    else:
                        results.append("midnight ⏭️")
                except Exception as e:
                    logger.exception(f"❌ midnight_job hatası: {e}")
                    results.append("midnight ❌")
            else:
                results.append("midnight ⏭️")
        
        elif 23 <= hour_utc < 24:  # 02:00 TR
            if should_run("late_night", 23):
                try:
                    result = late_night_job()
                    if not result or not result.get("skipped"):
                        results.append("late_night ✅")
                    else:
                        results.append("late_night ⏭️")
                except Exception as e:
                    logger.exception(f"❌ late_night_job hatası: {e}")
                    results.append("late_night ❌")
            else:
                results.append("late_night ⏭️")
        
        elif 1 <= hour_utc < 2:  # 04:00 TR
            if should_run("early_morning", 1):
                try:
                    result = early_morning_job()
                    if not result or not result.get("skipped"):
                        results.append("early_morning ✅")
                    else:
                        results.append("early_morning ⏭️")
                except Exception as e:
                    logger.exception(f"❌ early_morning_job hatası: {e}")
                    results.append("early_morning ❌")
            else:
                results.append("early_morning ⏭️")
        
        elif 3 <= hour_utc < 4:  # 06:00 TR
            if should_run("dawn", 3):
                try:
                    result = dawn_job()
                    if not result or not result.get("skipped"):
                        results.append("dawn ✅")
                    else:
                        results.append("dawn ⏭️")
                except Exception as e:
                    logger.exception(f"❌ dawn_job hatası: {e}")
                    results.append("dawn ❌")
            else:
                results.append("dawn ⏭️")
        
        elif 5 <= hour_utc < 6:  # 08:00 TR
            if should_run("morning", 5):
                try:
                    result = morning_job()
                    if not result or not result.get("skipped"):
                        results.append("morning ✅")
                    else:
                        results.append("morning ⏭️")
                except Exception as e:
                    logger.exception(f"❌ morning_job hatası: {e}")
                    results.append("morning ❌")
            else:
                results.append("morning ⏭️")
        
        # 🆕 SABAH SCRAPING (09:00 TR / 06:00 UTC)
        elif 6 <= hour_utc < 7:
            if should_run("morning_scraping", 6):
                try:
                    result = morning_scraping_job()
                    if not result or not result.get("skipped"):
                        results.append("morning_scraping ✅")
                    else:
                        results.append("morning_scraping ⏭️")
                except Exception as e:
                    logger.exception(f"❌ morning_scraping_job hatası: {e}")
                    results.append("morning_scraping ❌")
            else:
                results.append("morning_scraping ⏭️")
        
        elif 7 <= hour_utc < 8:  # 10:00 TR
            if should_run("mid_morning", 7):
                try:
                    result = mid_morning_job()
                    if not result or not result.get("skipped"):
                        results.append("mid_morning ✅")
                    else:
                        results.append("mid_morning ⏭️")
                except Exception as e:
                    logger.exception(f"❌ mid_morning_job hatası: {e}")
                    results.append("mid_morning ❌")
            else:
                results.append("mid_morning ⏭️")
        
        elif 9 <= hour_utc < 10:  # 12:00 TR
            if should_run("noon", 9):
                try:
                    result = noon_job()
                    if not result or not result.get("skipped"):
                        results.append("noon ✅")
                    else:
                        results.append("noon ⏭️")
                except Exception as e:
                    logger.exception(f"❌ noon_job hatası: {e}")
                    results.append("noon ❌")
            else:
                results.append("noon ⏭️")
        
        elif 11 <= hour_utc < 12:  # 14:00 TR
            if should_run("afternoon", 11):
                try:
                    result = afternoon_job()
                    if not result or not result.get("skipped"):
                        results.append("afternoon ✅")
                    else:
                        results.append("afternoon ⏭️")
                except Exception as e:
                    logger.exception(f"❌ afternoon_job hatası: {e}")
                    results.append("afternoon ❌")
            else:
                results.append("afternoon ⏭️")
        
        # 🆕 ÖĞLEDEN SONRA SCRAPING (15:00 TR / 12:00 UTC)
        elif 12 <= hour_utc < 13:
            if should_run("afternoon_scraping", 12):
                try:
                    result = afternoon_scraping_job()
                    if not result or not result.get("skipped"):
                        results.append("afternoon_scraping ✅")
                    else:
                        results.append("afternoon_scraping ⏭️")
                except Exception as e:
                    logger.exception(f"❌ afternoon_scraping_job hatası: {e}")
                    results.append("afternoon_scraping ❌")
            else:
                results.append("afternoon_scraping ⏭️")
        
        elif 13 <= hour_utc < 14:  # 16:00 TR
            if should_run("late_afternoon", 13):
                try:
                    result = late_afternoon_job()
                    if not result or not result.get("skipped"):
                        results.append("late_afternoon ✅")
                    else:
                        results.append("late_afternoon ⏭️")
                except Exception as e:
                    logger.exception(f"❌ late_afternoon_job hatası: {e}")
                    results.append("late_afternoon ❌")
            else:
                results.append("late_afternoon ⏭️")
        
        elif 15 <= hour_utc < 16:  # 18:00 TR
            if should_run("early_evening", 15):
                try:
                    result = early_evening_job()
                    if not result or not result.get("skipped"):
                        results.append("early_evening ✅")
                    else:
                        results.append("early_evening ⏭️")
                except Exception as e:
                    logger.exception(f"❌ early_evening_job hatası: {e}")
                    results.append("early_evening ❌")
            else:
                results.append("early_evening ⏭️")
        
        elif 17 <= hour_utc < 18:  # 20:00 TR
            if should_run("evening", 17):
                try:
                    result = evening_job()
                    if not result or not result.get("skipped"):
                        results.append("evening ✅")
                    else:
                        results.append("evening ⏭️")
                except Exception as e:
                    logger.exception(f"❌ evening_job hatası: {e}")
                    results.append("evening ❌")
            else:
                results.append("evening ⏭️")
        
        # 🆕 AKŞAM SCRAPING (21:00 TR / 18:00 UTC)
        elif 18 <= hour_utc < 19:
            if should_run("evening_scraping", 18):
                try:
                    result = evening_scraping_job()
                    if not result or not result.get("skipped"):
                        results.append("evening_scraping ✅")
                    else:
                        results.append("evening_scraping ⏭️")
                except Exception as e:
                    logger.exception(f"❌ evening_scraping_job hatası: {e}")
                    results.append("evening_scraping ❌")
            else:
                results.append("evening_scraping ⏭️")
        
        elif 19 <= hour_utc < 20:  # 22:00 TR
            if should_run("night", 19):
                try:
                    result = night_job()
                    if not result or not result.get("skipped"):
                        results.append("night ✅")
                    else:
                        results.append("night ⏭️")
                except Exception as e:
                    logger.exception(f"❌ night_job hatası: {e}")
                    results.append("night ❌")
            else:
                results.append("night ⏭️")
        
        # ============================================
        # TEMİZLİK JOB'U (03:00 TR / 00:00 UTC)
        # ============================================
        
        elif hour_utc == 0:
            if should_run("cleanup", 0):
                try:
                    result = cleanup_job()
                    if not result or not result.get("skipped"):
                        results.append("cleanup ✅")
                    else:
                        results.append("cleanup ⏭️")
                except Exception as e:
                    logger.exception(f"❌ cleanup_job hatası: {e}")
                    results.append("cleanup ❌")
            else:
                results.append("cleanup ⏭️")
        
        else:
            results.append(f"⏸️  UTC {hour_utc:02d}:xx - Planlanmış görev yok")
        
        return jsonify({
            "status": "ok",
            "timestamp": now_utc.isoformat(),
            "hour_utc": hour_utc,
            "hour_tr": now_tr.hour,
            "results": results
        }), 200

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

    @app.route("/news/last-update", methods=["GET"])
    def last_update():
        try:
            ts = NewsModel.get_latest_update_time()
            return jsonify({
                "success": True,
                "last_update": ts.isoformat() if ts else None,
                "timestamp": datetime.now(pytz.UTC).isoformat()
            })
        except Exception as e:
            logger.exception("❌ /news/last-update")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/news/stats", methods=["GET"])
    def stats():
        try:
            out = {cat: NewsModel.count_by_category(cat) for cat in Config.NEWS_CATEGORIES}
            return jsonify({"success": True, "stats": out, "total": sum(out.values())})
        except Exception as e:
            logger.exception("❌ /news/stats")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.route("/api/usage", methods=["GET"])
    def api_usage():
        try:
            from services.api_manager import get_all_usage, get_daily_summary
            return jsonify({
                "success": True,
                "timestamp": datetime.now(pytz.UTC).isoformat(),
                "apis": get_all_usage(),
                "summary": get_daily_summary()
            })
        except Exception as e:
            logger.exception("❌ /api/usage")
            return jsonify({"success": False, "error": str(e)}), 500

    @app.errorhandler(404)
    def error_404(e):
        return jsonify({
            "error": "not_found",
            "endpoints": [
                "/health",
                "/news",
                "/news/stats",
                "/news/last-update",
                "/api/news/scraped",
                "/api/news/scraped/after",
                "/api/news/scraped/stats",
                "/api/news/force-fill",
                "/api/usage",
                "/cron?key=SECRET"
            ]
        }), 404

    @app.errorhandler(500)
    def error_500(e):
        return jsonify({
            "error": "server_error",
            "message": str(e)
        }), 500

    return app


app = create_app()

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    logger.info("🚀 Habersel backend başlıyor...")
    app.run(host="0.0.0.0", port=port, debug=Config.DEBUG)
