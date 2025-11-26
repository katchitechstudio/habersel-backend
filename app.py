from flask import Flask, jsonify
from flask_cors import CORS
from apscheduler.schedulers.background import BackgroundScheduler
import atexit
import random
import time
from datetime import datetime

from config import Config
from routes.news_routes import news_bp
from models.news_models import init_news_table
from services.news_service import fetch_all_news
from models.db import get_db, put_db

app = Flask(__name__)
CORS(app)

# Blueprint kaydı
app.register_blueprint(news_bp)


# ============================
# TEMİZLİK JOB'U (3 gün kuralı)
# ============================
def clean_old_news():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            DELETE FROM haberler 
            WHERE tarih < NOW() - INTERVAL '3 days';
        """)

        deleted = cur.rowcount
        conn.commit()

        cur.close()
        put_db(conn)

        print(f"🧹 Temizlik: {deleted} haber silindi")

    except Exception as e:
        print("Temizlik hatası:", e)


# ============================
# SCHEDULER BAŞLATMA
# ============================
def init_scheduler():
    scheduler = BackgroundScheduler()

    # Haberleri 10 dakikada bir güncelle
    def jittered_fetch():
        delay = random.randint(0, Config.JITTER_MAX_SECONDS)
        print(f"⏳ Jitter → {delay} saniye")
        time.sleep(delay)
        fetch_all_news()

    scheduler.add_job(
        jittered_fetch,
        "interval",
        minutes=Config.RSS_UPDATE_INTERVAL,
        id="rss_job"
    )

    # Her gün 03:00'te eski haberleri sil
    scheduler.add_job(
        clean_old_news,
        "cron",
        hour=3,
        id="cleanup_job"
    )

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())


# ============================
# HEALTH ENDPOINT
# ============================
@app.route("/health")
def health():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM haberler")
        count = cur.fetchone()["count"]

        cur.close()
        put_db(conn)

        return jsonify({
            "status": "healthy",
            "count_news": count
        })

    except Exception as e:
        return jsonify({"status": "unhealthy", "error": str(e)}), 500


# ============================
# APP BAŞLANGIÇ
# ============================
if __name__ == "__main__":
    # DB tablo oluştur
    init_news_table()

    # Scheduler başlat
    init_scheduler()

    print("🚀 Habersel Backend v2.0 Çalışıyor")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=Config.DEBUG
    )
