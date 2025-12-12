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
    cleanup_job
)
from config import Config
from services.init_db import init_database, verify_tables
import os
import time
import logging
from datetime import datetime
import pytz

logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT
)
logger = logging.getLogger(__name__)


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
        minute_utc = now_utc.minute
        
        tz_tr = pytz.timezone(Config.TIMEZONE)
        now_tr = now_utc.astimezone(tz_tr)
        
        logger.info(f"⏰ /cron tetiklendi (UTC: {hour_utc:02d}:{minute_utc:02d}, TR: {now_tr.strftime('%H:%M')})")
        
        results = []
        
        if minute_utc > 15:
            logger.info("⏸️  Dakika > 15, sadece saat başlarında çalışır")
            return jsonify({
                "status": "skipped",
                "reason": "not_on_hour",
                "next_run": f"{hour_utc+1:02d}:00 UTC"
            }), 200
        
        job_schedule = {
            21: ("midnight", midnight_job, "00:00 TR"),
            23: ("late_night", late_night_job, "02:00 TR"),
            1: ("early_morning", early_morning_job, "04:00 TR"),
            3: ("dawn", dawn_job, "06:00 TR"),
            5: ("morning", morning_job, "08:00 TR"),
            7: ("mid_morning", mid_morning_job, "10:00 TR"),
            9: ("noon", noon_job, "12:00 TR"),
            11: ("afternoon", afternoon_job, "14:00 TR"),
            13: ("late_afternoon", late_afternoon_job, "16:00 TR"),
            15: ("early_evening", early_evening_job, "18:00 TR"),
            17: ("evening", evening_job, "20:00 TR"),
            19: ("night", night_job, "22:00 TR"),
            0: ("cleanup", cleanup_job, "03:00 TR"),
        }
        
        if hour_utc in job_schedule:
            job_name, job_func, job_time = job_schedule[hour_utc]
            
            logger.info(f"▶️  {job_name} ({job_time}) çalıştırılıyor...")
            
            try:
                result = job_func()
                
                if result and result.get("skipped"):
                    logger.info(f"⏭️  {job_name} atlandı")
                    results.append(f"{job_name} ⏭️")
                else:
                    logger.info(f"✅ {job_name} başarılı")
                    results.append(f"{job_name} ✅")
                    
            except Exception as e:
                logger.exception(f"❌ {job_name} hatası: {e}")
                results.append(f"{job_name} ❌")
                
                try:
                    logger.info(f"🔄 {job_name} retry deneniyor (5 saniye sonra)...")
                    time.sleep(5)
                    result = job_func()
                    logger.info(f"✅ {job_name} retry başarılı!")
                    results.append(f"{job_name} ✅ (retry)")
                except Exception as e2:
                    logger.exception(f"❌ {job_name} retry de başarısız: {e2}")
                    results.append(f"{job_name} ❌ (retry failed)")
        else:
            results.append(f"⏸️  UTC {hour_utc:02d}:xx - Planlanmış görev yok")
        
        return jsonify({
            "status": "ok",
            "timestamp": now_utc.isoformat(),
            "hour_utc": hour_utc,
            "minute_utc": minute_utc,
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
