from flask import Blueprint, jsonify, request
from models.news_models import NewsModel
from services.news_service import NewsService
from datetime import datetime
import pytz
from config import Config
import logging

logger = logging.getLogger(__name__)

news_bp = Blueprint("news", __name__, url_prefix="/api/news")


# ============================================================
# 🎯 YENİ: SADECE SCRAPE EDİLMİŞ HABERLER (ANDROID İÇİN)
# ============================================================

@news_bp.route("/scraped", methods=["GET"])
def get_scraped_news():
    """
    ✅ SADECE scrape edilmiş (tam metin) haberleri döndür
    Android uygulaması için ASIL endpoint
    
    Query Parameters:
        - limit: Kaç haber (varsayılan 50, max 200)
        - offset: Pagination (varsayılan 0)
        - category: Kategori filtresi (opsiyonel)
    
    Response:
        {
            "success": true,
            "count": 45,
            "total_scraped": 120,
            "news": [...]
        }
    """
    try:
        limit = request.args.get('limit', 50, type=int)
        offset = request.args.get('offset', 0, type=int)
        category = request.args.get('category', None, type=str)
        
        # Limit kontrolü (max 200)
        if limit > 200:
            limit = 200
        
        # SADECE scrape edilmiş haberleri getir
        news = NewsModel.get_scraped_only(
            category=category,
            limit=limit,
            offset=offset
        )
        
        # Toplam scrape edilmiş haber sayısı
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
    """
    ✅ Belirli tarihten sonra scrape edilmiş haberleri döndür
    Android Worker için - sadece yeni tam metin haberler
    
    Query Parameters:
        - after: ISO format tarih (zorunlu) - örn: 2025-12-08T15:00:00Z
        - limit: Kaç haber (varsayılan 50, max 200)
        - category: Kategori filtresi (opsiyonel)
    
    Response:
        {
            "success": true,
            "count": 15,
            "news": [...]
        }
    """
    try:
        after = request.args.get('after', type=str)
        limit = request.args.get('limit', 50, type=int)
        category = request.args.get('category', None, type=str)
        
        # 'after' parametresi zorunlu
        if not after:
            return jsonify({
                "success": False,
                "error": "Missing required parameter: 'after' (ISO date)"
            }), 400
        
        # Limit kontrolü
        if limit > 200:
            limit = 200
        
        # Tarihten sonraki scrape edilmiş haberleri getir
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
    """
    ✅ Scraping istatistikleri
    
    Response:
        {
            "success": true,
            "scraped": 95,
            "unscraped": 25,
            "blacklisted": 3,
            "total": 120
        }
    """
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


# ============================================================
# 📱 ESKİ ENDPOINT'LER (Geriye Dönük Uyumluluk)
# ============================================================

@news_bp.route("/latest", methods=["GET"])
def latest_news():
    """
    ⚠️ ESKİ ENDPOINT - TÜM haberleri döndürür (boş içerikli dahil)
    Geriye dönük uyumluluk için korundu
    
    ✅ YENİ: Android için /scraped endpoint'ini kullan
    """
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
    """
    ✅ Sadece son güncelleme zamanını döndür
    Android Worker için hafif kontrol
    """
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
    """
    🔧 Manuel haber güncelleme tetikleyici
    Cron dışında test/debug için kullan
    """
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
    """
    📊 Sistem durumu ve istatistikler
    Monitoring/dashboard için
    """
    try:
        status = NewsService.get_system_status()
        
        # datetime objesi varsa isoformat'a çevir
        db_last = status["database"].get("latest_update")
        if isinstance(db_last, datetime):
            status["database"]["latest_update"] = db_last.isoformat()
        
        # Scraping istatistiklerini ekle
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
    """
    💚 Basit health check
    Load balancer/monitoring için
    """
    return jsonify({
        "success": True,
        "status": "OK"
    })


# ============================================================
# 🔧 YÖNETİCİ ENDPOINT'LERİ (Opsiyonel)
# ============================================================

@news_bp.route("/blacklist", methods=["GET"])
def get_blacklist():
    """
    🚫 Blacklist'teki URL'leri listele
    """
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
    """
    📋 Henüz scrape edilmemiş haberleri listele
    Debug/monitoring için
    """
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
```

---

## ✅ **EKLENEN YENİ ENDPOINT'LER:**

### **1. Android İçin Ana Endpoint'ler:**
```
GET /api/news/scraped
    ✅ Sadece tam metin haberleri döndür
    ✅ Pagination desteği (limit, offset)
    ✅ Kategori filtresi
    
GET /api/news/scraped/after?after=2025-12-08T15:00:00Z
    ✅ Belirli tarihten sonraki tam metinler
    ✅ Android Worker için
    
GET /api/news/scraped/stats
    ✅ Scraping istatistikleri
    ✅ Başarı oranı
```

### **2. Yönetici/Debug Endpoint'leri:**
```
GET /api/news/blacklist
    ✅ Blacklist sayısı
    
GET /api/news/unscraped
    ✅ Henüz scrape edilmemiş haberler
```

### **3. Güncellenmiş Endpoint'ler:**
```
GET /api/news/status
    ✅ Scraping istatistikleri eklendi
    
GET /api/news/latest
    ⚠️ ESKİ - Geriye dönük uyumluluk için korundu
