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

# -----------------------
# Loglama Ayarları
# -----------------------
logging.basicConfig(
    level=getattr(logging, Config.LOG_LEVEL),
    format=Config.LOG_FORMAT
)
logger = logging.getLogger(__name__)

# -----------------------
# Son Çalışma Zamanı Takibi
# -----------------------
LAST_RUNS_FILE = "last_runs.json"

def load_last_runs():
    """Son çalışma zamanlarını yükle"""
    if not os.path.exists(LAST_RUNS_FILE):
        return {}
    try:
        with open(LAST_RUNS_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"❌ last_runs.json okunamadı: {e}")
        return {}

def save_last_runs(data):
    """Son çalışma zamanlarını kaydet"""
    try:
        with open(LAST_RUNS_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        logger.error(f"❌ last_runs.json yazılamadı: {e}")

def should_run(task_name):
    """
    Bugün bu görev çalıştı mı kontrol et
    Returns: True = çalıştırılabilir, False = bugün zaten çalıştı
    """
    # Türkiye saatini al
    tz = pytz.timezone(Config.TIMEZONE)
    now = datetime.now(tz)
    today_str = now.strftime("%Y-%m-%d")
    
    last_runs = load_last_runs()
    
    if last_runs.get(task_name) == today_str:
        logger.info(f"⏭️  {task_name} bugün zaten çalıştı, atlanıyor...")
        return False
    
    # Bugün ilk kez çalışıyor
    last_runs[task_name] = today_str
    save_last_runs(last_runs)
    logger.info(f"✅ {task_name} çalıştırılıyor...")
    return True

# -----------------------
# Flask App Oluşturma
# -----------------------
def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # CORS aktif et (Android app için gerekli)
    CORS(app, resources={
        r"/*": {
            "origins": "*",  # Production'da sadece kendi domain'ine izin ver
            "methods": ["GET", "POST"],
            "allow_headers": ["Content-Type"]
        }
    })
    
    # Rate Limiting (Spam koruması)
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=[f"{Config.RATE_LIMIT_PER_MINUTE} per minute"]
    )
    
    # -----------------------
    # Veritabanı Başlatma
    # -----------------------
    try:
        NewsModel.create_table()
        logger.info("✅ Veritabanı tablosu hazır")
    except Exception as e:
        logger.error(f"❌ Veritabanı hatası: {e}")
    
    # ================================================
    # ROUTES (Endpoint'ler)
    # ================================================
    
    # -----------------------
    # Health Check (UptimeRobot için)
    # -----------------------
    @app.route("/health", methods=["GET"])
    def health():
        """Backend sağlık kontrolü"""
        return jsonify({
            "status": "ok",
            "timestamp": datetime.now(pytz.timezone(Config.TIMEZONE)).isoformat(),
            "service": "habersel-backend"
        }), 200
    
    # -----------------------
    # CRON Endpoint (Otomatik Görevler)
    # -----------------------
    @app.route("/cron", methods=["GET"])
    def cron_runner():
        """
        UptimeRobot veya Render Cron bu endpoint'i tetikler
        Güvenlik: CRON_SECRET ile korunur
        """
        # Güvenlik kontrolü
        key = request.args.get("key")
        if key != Config.CRON_SECRET:
            logger.warning(f"⚠️  Yetkisiz cron denemesi: {request.remote_addr}")
            return jsonify({"error": "unauthorized"}), 401
        
        # Türkiye saatini al
        tz = pytz.timezone(Config.TIMEZONE)
        now = datetime.now(tz)
        hour = now.hour
        
        logger.info(f"⏰ /cron tetiklendi → Türkiye Saati: {now.strftime('%H:%M')}")
        
        results = []
        
        # Sabah 08:00
        if hour == 8 and should_run("morning"):
            try:
                morning_job()
                results.append("morning_job ✅")
            except Exception as e:
                logger.error(f"❌ morning_job hatası: {e}")
                results.append(f"morning_job ❌: {str(e)}")
        
        # Öğle 12:00
        elif hour == 12 and should_run("noon"):
            try:
                noon_job()
                results.append("noon_job ✅")
            except Exception as e:
                logger.error(f"❌ noon_job hatası: {e}")
                results.append(f"noon_job ❌: {str(e)}")
        
        # Akşam 18:00
        elif hour == 18 and should_run("evening"):
            try:
                evening_job()
                results.append("evening_job ✅")
            except Exception as e:
                logger.error(f"❌ evening_job hatası: {e}")
                results.append(f"evening_job ❌: {str(e)}")
        
        # Gece 23:00
        elif hour == 23 and should_run("night"):
            try:
                night_job()
                results.append("night_job ✅")
            except Exception as e:
                logger.error(f"❌ night_job hatası: {e}")
                results.append(f"night_job ❌: {str(e)}")
        
        # Temizlik 03:00 (Gece yarısı)
        elif hour == 3 and should_run("cleanup"):
            try:
                cleanup_job()
                results.append("cleanup_job ✅")
            except Exception as e:
                logger.error(f"❌ cleanup_job hatası: {e}")
                results.append(f"cleanup_job ❌: {str(e)}")
        
        else:
            results.append(f"Saat {hour}:00 için planlanmış görev yok veya bugün zaten çalıştı")
        
        return jsonify({
            "status": "ok",
            "timestamp": now.isoformat(),
            "results": results
        }), 200
    
    # -----------------------
    # Haber Listeleme (Android App için)
    # -----------------------
    @app.route("/news", methods=["GET"])
    @limiter.limit("60 per minute")  # Rate limiting
    def get_news():
        """
        Haberleri kategoriye göre getir
        Query params:
        - category: Kategori (opsiyonel)
        - limit: Kaç haber (default: 50)
        - offset: Sayfa (default: 0)
        """
        try:
            category = request.args.get("category")
            limit = min(int(request.args.get("limit", 50)), Config.MAX_NEWS_PER_PAGE)
            offset = int(request.args.get("offset", 0))
            
            news_list = NewsModel.get_news(
                category=category,
                limit=limit,
                offset=offset
            )
            
            return jsonify({
                "success": True,
                "count": len(news_list),
                "news": news_list
            }), 200
            
        except Exception as e:
            logger.error(f"❌ /news hatası: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # -----------------------
    # Kategorilere Göre Haber Sayıları
    # -----------------------
    @app.route("/news/stats", methods=["GET"])
    def get_stats():
        """Her kategoride kaç haber var?"""
        try:
            stats = {}
            for category in Config.NEWS_CATEGORIES:
                count = NewsModel.count_by_category(category)
                stats[category] = count
            
            return jsonify({
                "success": True,
                "stats": stats,
                "total": sum(stats.values())
            }), 200
            
        except Exception as e:
            logger.error(f"❌ /news/stats hatası: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # -----------------------
    # 🆕 API Kullanım İstatistikleri (YENİ!)
    # -----------------------
    @app.route("/api/usage", methods=["GET"])
    def api_usage_stats():
        """
        API limitlerinin kullanım durumunu gösterir
        
        Response:
        {
            "apis": {
                "gnews": {"limit": 100, "used": 45, "remaining": 55, ...},
                "currents": {...}
            },
            "summary": {
                "total_requests_made": 78,
                "total_daily_limit": 133,
                ...
            }
        }
        """
        try:
            from services.api_manager import get_all_usage, get_daily_summary
            
            return jsonify({
                "success": True,
                "timestamp": datetime.now(pytz.timezone(Config.TIMEZONE)).isoformat(),
                "apis": get_all_usage(),
                "summary": get_daily_summary()
            }), 200
            
        except Exception as e:
            logger.error(f"❌ /api/usage hatası: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # -----------------------
    # Manuel Görev Tetikleme (Sadece Development)
    # -----------------------
    @app.route("/trigger/<task_name>", methods=["POST"])
    def trigger_task(task_name):
        """
        Manuel görev tetikleme (sadece development için)
        Production'da bu endpoint'i kapat!
        """
        if not Config.DEBUG:
            return jsonify({"error": "Not allowed in production"}), 403
        
        # Güvenlik kontrolü
        key = request.args.get("key")
        if key != Config.CRON_SECRET:
            return jsonify({"error": "unauthorized"}), 401
        
        try:
            if task_name == "morning":
                morning_job()
            elif task_name == "noon":
                noon_job()
            elif task_name == "evening":
                evening_job()
            elif task_name == "night":
                night_job()
            elif task_name == "cleanup":
                cleanup_job()
            else:
                return jsonify({"error": "Invalid task name"}), 400
            
            return jsonify({
                "success": True,
                "message": f"{task_name}_job tamamlandı"
            }), 200
            
        except Exception as e:
            logger.error(f"❌ Manual trigger hatası: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    
    # -----------------------
    # 404 Hatası
    # -----------------------
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({
            "error": "Endpoint bulunamadı",
            "available_endpoints": [
                "/health",
                "/cron?key=YOUR_SECRET",
                "/news",
                "/news?category=technology",
                "/news/stats",
                "/api/usage"  # 🆕 YENİ!
            ]
        }), 404
    
    # -----------------------
    # 500 Hatası
    # -----------------------
    @app.errorhandler(500)
    def internal_error(e):
        logger.error(f"❌ Internal server error: {e}")
        return jsonify({
            "error": "Sunucu hatası",
            "message": str(e)
        }), 500
    
    return app

# ================================================
# UYGULAMA BAŞLATMA
# ================================================
if __name__ == "__main__":
    app = create_app()
    
    # Port (Render otomatik 10000 atar)
    port = int(os.getenv("PORT", 10000))
    
    logger.info(f"🚀 Habersel Backend başlatılıyor...")
    logger.info(f"🌍 Port: {port}")
    logger.info(f"🕒 Timezone: {Config.TIMEZONE}")
    logger.info(f"📊 Debug Mode: {Config.DEBUG}")
    
    app.run(
        host="0.0.0.0",
        port=port,
        debug=Config.DEBUG
    )
