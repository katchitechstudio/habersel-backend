import os
from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import atexit

from routes.news_routes import news_bp
from models.news_models import init_news_table
from services.news_service import fetch_and_save_news
from models.db import get_db, put_db


app = Flask(__name__)
CORS(app)

# Blueprint
app.register_blueprint(news_bp)


# ============================
# 1) SCHEDULER
# ============================
def init_scheduler():
    scheduler = BackgroundScheduler()

    # Haberleri her 30 dakikada bir çek
    scheduler.add_job(
        fetch_and_save_news,
        "interval",
        minutes=30,
        id="rss_fetch_job"
    )

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())


# ============================
# 2) HEALTH ENDPOINT
# ============================
@app.route("/health")
def health():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM haberler")
        count = cur.fetchone()[0]

        cur.close()
        put_db(conn)

        return jsonify({
            "status": "healthy",
            "news_count": count
        })

    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


# ============================
# 3) APP START
# ============================
if __name__ == "__main__":
    # Tabloyu oluştur
    init_news_table()

    # Scheduler başlat
    init_scheduler()

    print("🚀 Habersel Backend Çalışıyor")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=True
    )
