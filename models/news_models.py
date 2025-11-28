from models.db import get_db, put_db

def init_news_table():
    """
    Haberler tablosunu oluşturur.
    Eğer tablo yoksa otomatik olarak ekler.
    """
    conn = get_db()
    cur = conn.cursor()
    
    # 1. Tabloyu oluştur (eğer yoksa)
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
    
    # 2. Eski UNIQUE constraint'i kaldır (eğer varsa)
    try:
        cur.execute("""
            ALTER TABLE haberler DROP CONSTRAINT IF EXISTS haberler_baslik_key;
        """)
        print("✅ Başlık UNIQUE constraint'i kaldırıldı")
    except Exception as e:
        print(f"⚠️ Constraint kaldırma hatası (normal olabilir): {e}")
    
    # 3. URL UNIQUE constraint'i ekle (eğer yoksa)
    try:
        cur.execute("""
            DO $$ 
            BEGIN
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint 
                    WHERE conname = 'haberler_url_key'
                ) THEN
                    ALTER TABLE haberler ADD CONSTRAINT haberler_url_key UNIQUE (url);
                END IF;
            END $$;
        """)
        print("✅ URL UNIQUE constraint'i eklendi")
    except Exception as e:
        print(f"⚠️ URL constraint ekleme hatası: {e}")
    
    # 4. Index'leri oluştur (performans için)
    try:
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_haberler_tarih ON haberler(tarih DESC);
        """)
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_haberler_kaynak ON haberler(kaynak);
        """)
        print("✅ Index'ler oluşturuldu")
    except Exception as e:
        print(f"⚠️ Index oluşturma hatası: {e}")
    
    conn.commit()
    cur.close()
    put_db(conn)
    
    print("🗂️ Haberler tablosu hazır (haberler).")
