from flask import Flask, jsonify
from models.news_models import NewsModel
from config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # ---------------------------------------------
    # İlk çalıştırmada veritabanı tablosunu oluştur
    # ---------------------------------------------
    try:
        print("📦 Haber tablosu kontrol ediliyor / oluşturuluyor...")
        NewsModel.create_table()
        print("✅ Haber tablosu hazır.")
    except Exception as e:
        print("❌ Tablo oluşturma hatası:", e)

    # ---------------------------------------------
    # HEALTH CHECK (UptimeRobot için)
    # ---------------------------------------------
    @app.route("/health")
    def health():
        return jsonify({"status": "ok"}), 200

    # ---------------------------------------------
    # (İleride) Android uygulaması için endpoint eklenecek
    # - /news?category=technology
    # - /categories
    # ---------------------------------------------

    return app


# ------------------------------------------------
# Flask uygulamasını başlat
# ------------------------------------------------
if __name__ == "__main__":
    app = create_app()
    app.run(host="0.0.0.0", port=10000)
