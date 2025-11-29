from datetime import datetime, timedelta
from config import Config
from models.db import get_db, put_db


class NewsModel:

    @staticmethod
    def create_table():
        """
        Haber tablosu yoksa oluşturur.
        UNIQUE(title, url) → Aynı haberin tekrar eklenmesini engeller.
        """
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id SERIAL PRIMARY KEY,
                category VARCHAR(50),
                title TEXT,
                description TEXT,
                url TEXT,
                image TEXT,
                source VARCHAR(50),
                published TIMESTAMP,
                saved_at TIMESTAMP DEFAULT NOW(),
                expires_at TIMESTAMP,
                CONSTRAINT unique_news UNIQUE (title, url)
            );
        """)

        conn.commit()
        put_db(conn)

    @staticmethod
    def save_article(article: dict, category: str):
        """
        Tek bir haberi veritabanına kaydeder.
        Duplicate olursa hata fırlatmaz → yok sayar.
        """
        conn = get_db()
        cur = conn.cursor()

        expires = datetime.utcnow() + timedelta(days=Config.NEWS_EXPIRATION_DAYS)

        try:
            cur.execute("""
                INSERT INTO news (category, title, description, url, image, source, published, expires_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (title, url) DO NOTHING;
            """, (
                category,
                article.get("title"),
                article.get("description"),
                article.get("url"),
                article.get("image"),
                article.get("source"),
                datetime.utcnow(),
                expires
            ))
        except Exception as e:
            print("❌ Haber kaydedilemedi:", e)
        finally:
            conn.commit()
            put_db(conn)

    @staticmethod
    def delete_expired():
        """ Süresi geçmiş haberleri siler. """
        conn = get_db()
        cur = conn.cursor()

        cur.execute("DELETE FROM news WHERE expires_at < NOW();")

        conn.commit()
        put_db(conn)

    @staticmethod
    def get_by_category(category: str, limit: int = 50):
        """ Android uygulamasına dönecek haberleri getirir. """
        conn = get_db()
        cur = conn.cursor()

        cur.execute("""
            SELECT id, category, title, description, url, image, source, published
            FROM news
            WHERE category = %s
            ORDER BY saved_at DESC
            LIMIT %s;
        """, (category, limit))

        rows = cur.fetchall()
        put_db(conn)

        return rows
