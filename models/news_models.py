from models.db import get_db, put_db

def init_news_table():
    """
    Haberler tablosunu oluşturur.
    Eğer tablo yoksa otomatik olarak ekler.
    """
    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS haberler (
            id SERIAL PRIMARY KEY,
            baslik TEXT NOT NULL,
            aciklama TEXT,
            gorsel TEXT,
            kaynak TEXT,
            url TEXT UNIQUE NOT NULL,
            kategori TEXT,
            tarih TIMESTAMP,
            created_at TIMESTAMP DEFAULT NOW()
        );
    """)

    conn.commit()
    cur.close()
    put_db(conn)

    print("🗂️ Haberler tablosu hazır (haberler).")
