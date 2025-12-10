import logging
from models.db import get_db, put_db

logger = logging.getLogger(__name__)


def init_database():
    logger.info("=" * 70)
    logger.info("🔧 VERİTABANI BAŞLATILIYOR...")
    logger.info("=" * 70)
    
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        
        logger.info("📋 scraping_blacklist tablosu kontrol ediliyor...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS scraping_blacklist (
                id SERIAL PRIMARY KEY,
                url TEXT UNIQUE NOT NULL,
                fail_count INTEGER DEFAULT 1,
                reason TEXT,
                first_failed TIMESTAMP DEFAULT NOW(),
                last_failed TIMESTAMP DEFAULT NOW(),
                created_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_blacklist_url 
            ON scraping_blacklist(url);
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_blacklist_fail_count 
            ON scraping_blacklist(fail_count);
        """)
        logger.info("✅ scraping_blacklist tablosu hazır")
        
        logger.info("📋 news tablosu kontrol ediliyor...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS news (
                id SERIAL PRIMARY KEY,
                title TEXT NOT NULL,
                description TEXT,
                url TEXT UNIQUE NOT NULL,
                image TEXT,
                published TIMESTAMP,
                category TEXT,
                source TEXT,
                api_source TEXT,
                full_content TEXT,
                is_scraped BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_category 
            ON news(category);
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_published 
            ON news(published DESC);
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_is_scraped 
            ON news(is_scraped);
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_created_at 
            ON news(created_at DESC);
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_news_url 
            ON news(url);
        """)
        logger.info("✅ news tablosu hazır")
        
        logger.info("📋 system tablosu kontrol ediliyor...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS system (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TIMESTAMP DEFAULT NOW()
            );
        """)
        logger.info("✅ system tablosu hazır")
        
        logger.info("📋 api_usage tablosu kontrol ediliyor...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id SERIAL PRIMARY KEY,
                api_name TEXT NOT NULL,
                request_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                date DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT NOW(),
                updated_at TIMESTAMP DEFAULT NOW(),
                UNIQUE(api_name, date)
            );
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_usage_date 
            ON api_usage(date DESC);
        """)
        
        cur.execute("""
            CREATE INDEX IF NOT EXISTS idx_api_usage_api_name 
            ON api_usage(api_name);
        """)
        logger.info("✅ api_usage tablosu hazır")
        
        conn.commit()
        cur.close()
        
        logger.info("=" * 70)
        logger.info("✅ VERİTABANI BAŞLATMA TAMAMLANDI")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Veritabanı başlatma hatası: {e}")
        if conn:
            conn.rollback()
        raise
        
    finally:
        if conn:
            put_db(conn)


def verify_tables():
    conn = None
    try:
        conn = get_db()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT table_name 
            FROM information_schema.tables 
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """)
        
        tables = [row[0] for row in cur.fetchall()]
        
        required_tables = ['news', 'scraping_blacklist', 'system', 'api_usage']
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            logger.warning(f"⚠️  Eksik tablolar: {missing_tables}")
            return False
        
        logger.info(f"✅ Tüm tablolar mevcut: {tables}")
        cur.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Tablo doğrulama hatası: {e}")
        return False
        
    finally:
        if conn:
            put_db(conn)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    init_database()
    verify_tables()
