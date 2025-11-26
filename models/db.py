import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config


def get_db():
    """
    PostgreSQL veritabanı bağlantısı kurar.
    psycopg2-binary ile Render’da sorunsuz çalışır.
    """
    try:
        conn = psycopg2.connect(
            dsn=Config.DB_URL,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print("❌ DB bağlantı hatası:", e)
        raise


def put_db(conn):
    """
    Açık bağlantıyı kapatır.
    """
    try:
        if conn:
            conn.close()
    except Exception as e:
        print("❌ DB kapatma hatası:", e)
