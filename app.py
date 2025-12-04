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
    """Son çalışma zamanlarını yükler"""
    if not os.path.exists(LAST_RUNS_FILE):
        return {}
    try:
        with open(LAST_RUNS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ last_runs.json okunamadı: {e}")
        return {}


def save_last_runs(data):
    """Son çalışma zamanlarını kaydeder"""
    try:
        with open(LAST_RUNS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"❌ last_runs.json yazılamadı: {e}")


def should_run(task_name, hour):
    """
    Bu görevi bu saatte çalıştırmalı mı kontrol eder.
    
    Args:
        task_name: Görev adı (morning, noon, evening, night, cleanup)
        hour: Şu anki saat
    
    Returns:
        bool: Çalıştırılmalı mı?
    """
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)
    today = now.strftime("%Y-%m-%d")
    current_hour_str = f"{today}_{hour:02d}"

    runs = load_last_runs()

    # Bugün bu saatte zaten çalıştı mı?
    if runs.get(task_name) == current_hour_str:
        logger.info(f"⏭️  {task_name} bugün saat {hour:02d}:00'de zaten çalıştı")
        return False

    # Çalıştırılacak, kaydet
    runs[task_name] = current_hour_str
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
        logger.info("✅ Database tabloları hazır")
    except Exception as e:
        logger.error(f"❌ DB tablo hatası: {e}")

    # SystemInfo tablosu oluştur
    try:
        from models.system_models import SystemModel
        SystemModel.init_table()
        logger.info("✅ SystemInfo tablosu hazır")
    except Exception as e:
        logger.error(f"❌ SystemInfo tablo hatası: {e}")

    # ====================================================
    # ENDPOINT'LER
    # ====================================================

    # ---------------------------
    # HEALTH CHECK
    # ---------------------------
    @app.route("/health", methods=["GET", "HEAD"])
    def health():
        return jsonify({
            "status": "ok",
            "service": "habersel-backend",
            "timestamp": datetime.now(
                pytz.timezone(Config.TIMEZONE)
            ).isoformat()
        }), 200

    # ---------------------------
    # CRON (FIXED - SAAT ARALIĞI KONTROLÜ)
    # ---------------------------
    @app.route("/cron", methods=["GET", "HEAD"])
    def cron():
        key = request.args.get("key")
        if key != Config.CRON_SECRET:
            return jsonify({"error": "unauthorized"}), 401

        tz = pytz.timezone(Config.TIMEZONE)
        now = datetime.now(tz)
        hour = now.hour

        logger.info(f"⏰ /cron tetiklendi (TR: {now.strftime('%H:%M')})")

        results = []

        # SABAH 08:00-08:59 ✅ ARALIĞA ÇEVRİLDİ
        if 8 <= hour < 9:
            if should_run("morning", 8):
                try:
                    result = morning_job()
                    if not result or not result.get("skipped"):
                        results.append("morning ✅")
                    else:
                        results.append("morning ⏭️ (atlandı)")
                except Exception as e:
                    logger.exception(f"❌ morning_job hatası")
                    results.append(f"morning ❌ {e}")
            else:
                results.append("morning ⏭️ (zaten çalıştı)")

        # ÖĞLE 12:00-12:59 ✅ ARALIĞA ÇEVRİLDİ
        elif 12 <= hour < 13:
            if should_run("noon", 12):
                try:
                    result = noon_job()
                    if not result or not result.get("skipped"):
                        results.append("noon ✅")
                    else:
                        results.append("noon ⏭️ (atlandı)")
                except Exception as e:
                    logger.exception(f"❌ noon_job hatası")
                    results.append(f"noon ❌ {e}")
            else:
                results.append("noon ⏭️ (zaten çalıştı)")

        # AKŞAM 18:00-18:59 ✅ ARALIĞA ÇEVRİLDİ
        elif 18 <= hour < 19:
            if should_run("evening", 18):
                try:
                    result = evening_job()
                    if not result or not result.get("skipped"):
                        results.append("evening ✅")
                    else:
                        results.append("evening ⏭️ (atlandı)")
                except Exception as e:
                    logger.exception(f"❌ evening_job hatası")
                    results.append(f"evening ❌ {e}")
            else:
                results.append("evening ⏭️ (zaten çalıştı)")

        # GECE 23:00-23:59 ✅ ARALIĞA ÇEVRİLDİ
        elif 23 <= hour < 24:
            if should_run("night", 23):
                try:
                    result = night_job()
                    if not result or not result.get("skipped"):
                        results.append("night ✅")
                    else:
                        results.append("night ⏭️ (atlandı)")
                except Exception as e:
                    logger.exception(f"❌ night_job hatası")
                    results.append(f"night ❌ {e}")
            else:
                results.append("night ⏭️ (zaten çalıştı)")

        # TEMİZLİK 03:00-03:59 ✅ ARALIĞA ÇEVRİLDİ
        elif 3 <= hour < 4:
            if should_run("cleanup", 3):
                try:
                    result = cleanup_job()
                    if not result or not result.get("skipped"):
                        results.append("cleanup ✅")
                    else:
                        results.append("cleanup ⏭️ (atlandı)")
                except Exception as e:
                    logger.exception(f"❌ cleanup_job hatası")
                    results.append(f"cleanup ❌ {e}")
            else:
                results.append("cleanup ⏭️ (zaten çalıştı)")

        # DİĞER SAATLER
        else:
            results.append(f"⏸️  Saat {hour:02d}:xx - Planlanmış görev yok")

        return jsonify({
            "status": "ok",
            "timestamp": now.isoformat(),
            "hour": hour,
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
                "/api/usage",
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
