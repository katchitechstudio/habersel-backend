import psycopg
from psycopg.rows import dict_row
from config import Config


def get_db():
    """
    PostgreSQL veritabanı bağlantısı (psycopg3).
    dict_row sayesinde sonuçlar JSON-friendly dict olarak döner.
    """
    try:
        conn = psycopg.connect(
            Config.DB_URL,
            row_factory=dict_row
        )
        return conn

    except Exception as e:
        print("❌ DB bağlantı hatası:", e)
        raise


def put_db(conn):
    """
    Veritabanı bağlantısını kapatır.
    """
    try:
        if conn:
            conn.close()
    except Exception as e:
        print("❌ DB kapatma hatası:", e)
