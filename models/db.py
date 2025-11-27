import psycopg2
from psycopg2.extras import RealDictCursor
from config import Config


def get_db():
    """
    PostgreSQL veritabanı bağlantısı kurar.
    Bağlantı koparsa yeniden bağlanır.
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


def query_db(query, params=None, fetchone=False):
    """
    Sorgu çalıştırmak için yardımcı fonksiyon.
    Her sorguda cursor oluştur → sorgu çalıştır → cursor kapanır.
    """
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(query, params or [])

        if fetchone:
            result = cur.fetchone()
        else:
            result = cur.fetchall()

        conn.commit()
        return result

    except Exception as e:
        print("❌ Sorgu hatası:", e)
        raise

    finally:
        if conn:
            conn.close()


def put_db(conn):
    """
    Açık bağlantıyı kapatır.
    """
    try:
        if conn:
            conn.close()
    except Exception as e:
        print("❌ DB kapatma hatası:", e)
