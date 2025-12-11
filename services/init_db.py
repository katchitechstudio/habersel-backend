import logging
from models.db import get_db, put_db
from models.news_models import NewsModel
# SystemInfo modeli varsa import et (Loglarda var gözüküyordu)
try:
    from models.system_models import SystemInfo
except ImportError:
    SystemInfo = None

logger = logging.getLogger(__name__)

def init_database():
    """
    Veritabanı tablolarını başlatır ve güncellemeleri kontrol eder.
    Hata veren manuel SQL'ler yerine akıllı Model yapılarını kullanır.
    """
    logger.info("=" * 70)
    logger.info("🔧 VERİTABANI BAŞLATILIYOR...")
    logger.info("=" * 70)
    
    conn = None
    try:
        # 1. NewsModel Tablolarını Oluştur (News + Blacklist)
        # Bu fonksiyon "created_at" hatasını çözer çünkü doğru sütun isimlerini kullanır.
        NewsModel.create_table()
        
        # 2. SystemInfo Tablosunu Oluştur (System)
        if SystemInfo:
            try:
                SystemInfo.create_table()
            except Exception as e:
                logger.warning(f"⚠️ SystemInfo tablosu başlatılırken uyarı: {e}")
        
        # 3. Api Usage Tablosu (Manuel SQL - Model olmadığı için koruyoruz)
        conn = get_db()
        cur = conn.cursor()
        
        logger.info("📋 api_usage tablosu kontrol ediliyor...")
        cur.execute("""
            CREATE TABLE IF NOT EXISTS api_usage (
                id SERIAL PRIMARY KEY,
                api_name TEXT NOT NULL,
                request_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                date DATE DEFAULT CURRENT_DATE,
                created_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'UTC'),
                updated_at TIMESTAMP DEFAULT (NOW() AT TIME ZONE 'UTC'),
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
        
        conn.commit()
        logger.info("✅ api_usage tablosu hazır")
        
        logger.info("=" * 70)
        logger.info("✅ VERİTABANI BAŞLATMA İŞLEMİ TAMAMLANDI")
        logger.info("=" * 70)
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Veritabanı başlatma hatası: {e}")
        if conn:
            conn.rollback()
        # Kritik hata olsa bile uygulamayı çökertmemek için raise etmiyoruz,
        # sadece logluyoruz.
        return False
        
    finally:
        if conn:
            # Cursor kapatma işlemi try bloğunda yapılmalıydı ama 
            # conn.close() connection pool için yeterli.
            try:
                cur.close()
            except:
                pass
            put_db(conn)

def verify_tables():
    """
    Tabloların varlığını basitçe doğrular.
    """
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
        
        # Beklenen tablolar
        required_tables = ['news', 'scraping_blacklist', 'api_usage']
        # 'system' veya 'system_info' olabilir, esnek kontrol
        
        missing_tables = [t for t in required_tables if t not in tables]
        
        if missing_tables:
            logger.warning(f"⚠️ Eksik tablolar olabilir: {missing_tables}")
            return False
        
        logger.info(f"✅ Tablo doğrulama başarılı. Mevcut tablolar: {tables}")
        return True
        
    except Exception as e:
        logger.error(f"❌ Tablo doğrulama hatası: {e}")
        return False
        
    finally:
        if conn:
            try:
                cur.close()
            except:
                pass
            put_db(conn)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    init_database()
    verify_tables()
