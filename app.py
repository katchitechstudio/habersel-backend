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

# Blueprint kaydı
app.register_blueprint(news_bp)


# ============================
# 1) 3 GÜNDEN ESKİ HABERLERİ TEMİZLE
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
# 2) SCHEDULER (Haber Çekme + Temizlik)
# ============================
def init_scheduler():
    scheduler = BackgroundScheduler()

    # Her 30 dakikada bir haber çek
    scheduler.add_job(
        fetch_and_save_news,
        trigger="interval",
        minutes=30,
        id="fetch_job"
    )

    # Her gün saat 03:00'te eski haberleri sil
    scheduler.add_job(
        clean_old_news,
        trigger="cron",
        hour=3,
        minute=0,
        id="clean_job"
    )

    scheduler.start()
    atexit.register(lambda: scheduler.shutdown())


# ============================
# 3) HEALTH ENDPOINT
# ============================
@app.route("/health")
def health():
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) AS cnt FROM haberler")
        row = cur.fetchone()
        count = row["cnt"] if row else 0

        cur.close()
        put_db(conn)

        return jsonify({
            "status": "healthy",
            "news_count": count
        })

    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e)
        }), 500


# ============================
# 4) APP START
# ============================
if __name__ == "__main__":
    # Tabloyu oluştur (Render prod modda da çalışsın)
    try:
        init_news_table()
    except Exception as e:
        print("Tablo init hatası:", e)

    # Scheduler başlat
    init_scheduler()

    print("🚀 Habersel Backend Çalışıyor")

    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", 5000)),
        debug=False
    )
