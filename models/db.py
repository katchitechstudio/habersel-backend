import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config


def get_db():
    """
    PostgreSQL veritabanı bağlantısı kurar.
    Otomatik reconnect destekler.
    """
    try:
        conn = psycopg2.connect(
            Config.DB_URL,
            cursor_factory=RealDictCursor
        )
        return conn
    except Exception as e:
        print("❌ DB bağlantı hatası:", e)
        raise


def put_db(conn):
    """
    Açık bağlantıyı güvenli şekilde kapatır.
    """
    try:
        if conn:
            conn.close()
    except Exception as e:
        print("❌ DB kapatma hatası:", e)
