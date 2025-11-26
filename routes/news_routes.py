from flask import Blueprint, jsonify
from datetime import datetime
from models.db import get_db, put_db

# Cache'i service içinden import ediyoruz
from services.news_service import get_cached_news, CATEGORIES

news_bp = Blueprint("news", __name__, url_prefix="/api/news")


# ================================
# 1) TÜM HABERLER (En son 100)
# ================================
@news_bp.route("/latest", methods=["GET"])
def get_latest_news():
    try:
        all_news = []

        # Tüm kategorilerin önbellek verisini al
        for category in CATEGORIES:
            cat_news = get_cached_news(category)
            all_news.extend(cat_news)

        # Tarihe göre sırala (sondan → yeni)
        all_news = sorted(
            all_news, 
            key=lambda x: x.get("publishedAt", ""), 
            reverse=True
        )

        return jsonify({
            "success": True,
            "count": len(all_news),
            "news": all_news[:100]   # sadece son 100
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



# ================================
# 2) BELİRLİ KATEGORİ HABERLERİ
# ================================
@news_bp.route("/category/<category>", methods=["GET"])
def get_news_by_category(category):
    try:
        if category not in CATEGORIES:
            return jsonify({
                "success": False,
                "error": f"Kategori bulunamadı: {category}",
                "available_categories": CATEGORIES
            }), 404

        haberler = get_cached_news(category)

        return jsonify({
            "success": True,
            "category": category,
            "count": len(haberler),
            "news": haberler
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



# ================================
# 3) MANUEL HABER GÜNCELLEME (Admin)
# ================================
@news_bp.route("/update", methods=["POST", "GET"])
def update_news_manual():
    """
    Manuel çekim → Haberleri hemen RSS kaynaklarından çeker.
    """
    from services.news_service import fetch_all_news

    try:
        count = fetch_all_news()

        return jsonify({
            "success": True,
            "message": "Haberler güncellendi.",
            "fetched": count,
            "timestamp": datetime.now().isoformat()
        })

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500



# ================================
# 4) KATEGORİ LİSTESİ
# ================================
@news_bp.route("/categories", methods=["GET"])
def list_categories():
    return jsonify({
        "success": True,
        "categories": CATEGORIES
    })
