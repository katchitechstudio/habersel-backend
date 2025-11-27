from flask import Blueprint, jsonify
from models.db import get_db, put_db
from services.news_service import fetch_and_save_news

news_bp = Blueprint("news", __name__, url_prefix="/api/news")


# ============================
# 1) En yeni haberler (limit: 100)
# ============================
@news_bp.route("/latest", methods=["GET"])
def get_latest_news():
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id, baslik, aciklama, gorsel, kaynak, url, tarih 
        FROM haberler
        ORDER BY tarih DESC NULLS LAST
        LIMIT 100;
    """)

    news = cur.fetchall()

    put_db(conn)

    return jsonify({
        "success": True,
        "count": len(news),
        "news": news
    })


# ============================
# 2) Manuel haber güncelleme (Admin)
# ============================
@news_bp.route("/update", methods=["POST", "GET"])
def update_news_manual():
    try:
        added_count = fetch_and_save_news()
        return jsonify({
            "success": True,
            "message": "Haberler RSS kaynaklarından güncellendi.",
            "added": added_count
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ============================
# 3) Sağlık kontrolü
# ============================
@news_bp.route("/health", methods=["GET"])
def health():
    return jsonify({"success": True, "status": "OK"})
