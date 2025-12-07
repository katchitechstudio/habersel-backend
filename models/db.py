import psycopg2
from psycopg2 import pool
from config import Config
import logging
import time

logger = logging.getLogger(__name__)

# -----------------------
# Connection Pool (Bağlantı Havuzu)
# -----------------------
# Render ücretsiz planında max 5 bağlantı var
# Pool kullanarak verimli bağlantı yönetimi yapıyoruz

_connection_pool = None

def init_connection_pool():
    """
    PostgreSQL bağlantı havuzunu başlatır.
    
    Avantajları:
    - Her istekte yeni bağlantı açmak yerine havuzdan alır
    - Bağlantı sayısını kontrol eder
    - Performansı artırır
    """
    global _connection_pool
    
    if _connection_pool is not None:
        logger.debug("✅ Connection pool zaten mevcut")
        return _connection_pool
    
    try:
        _connection_pool = psycopg2.pool.SimpleConnectionPool(
            minconn=1,      # Minimum 1 bağlantı
            maxconn=5,      # Maksimum 5 bağlantı (Render free tier limiti)
            dsn=Config.DB_URL
            # ✅ cursor_factory KALDIRILDI! Normal tuple cursor kullanacağız
        )
        
        logger.info("✅ PostgreSQL connection pool oluşturuldu")
        return _connection_pool
        
    except Exception as e:
        logger.error(f"❌ Connection pool oluşturulamadı: {e}")
        raise

def get_db():
    """
    Veritabanı bağlantısı getirir.
    
    Connection pool kullanır:
    - Havuzdan boş bağlantı alır
    - Yoksa yeni oluşturur
    - Otomatik reconnect destekler
    
    Returns:
        psycopg2.connection: PostgreSQL bağlantısı
    """
    global _connection_pool
    
    # Pool yoksa oluştur
    if _connection_pool is None:
        init_connection_pool()
    
    try:
        # Havuzdan bağlantı al
        conn = _connection_pool.getconn()
        
        # Bağlantı test et
        if conn.closed:
            logger.warning("⚠️  Bağlantı kapalı, yeniden açılıyor...")
            _connection_pool.putconn(conn)
            conn = _connection_pool.getconn()
        
        return conn
        
    except psycopg2.pool.PoolError as e:
        logger.error(f"❌ Connection pool hatası: {e}")
        # Pool dolu → yeni bağlantı aç
        try:
            conn = psycopg2.connect(Config.DB_URL)
            logger.warning("⚠️  Pool dolu, direkt bağlantı açıldı")
            return conn
        except Exception as direct_error:
            logger.error(f"❌ Direkt bağlantı da başarısız: {direct_error}")
            raise
    
    except Exception as e:
        logger.error(f"❌ DB bağlantı hatası: {e}")
        
        # Retry mekanizması (3 deneme)
        for attempt in range(Config.MAX_RETRIES):
            try:
                logger.info(f"🔄 Yeniden deneniyor... ({attempt + 1}/{Config.MAX_RETRIES})")
                time.sleep(Config.RETRY_DELAY)
                
                conn = psycopg2.connect(Config.DB_URL)
                logger.info("✅ Bağlantı başarılı (retry)")
                return conn
                
            except Exception as retry_error:
                if attempt == Config.MAX_RETRIES - 1:
                    logger.error(f"❌ Tüm denemeler başarısız: {retry_error}")
                    raise
                continue

def put_db(conn):
    """
    Bağlantıyı güvenli şekilde havuza geri koyar veya kapatır.
    
    Args:
        conn: PostgreSQL bağlantısı
    """
    global _connection_pool
    
    if conn is None:
        return
    
    try:
        # Eğer pool varsa, bağlantıyı havuza geri koy
        if _connection_pool is not None:
            _connection_pool.putconn(conn)
            logger.debug("✅ Bağlantı havuza geri kondu")
        else:
            # Pool yoksa direkt kapat
            conn.close()
            logger.debug("✅ Bağlantı kapatıldı")
            
    except Exception as e:
        logger.error(f"❌ Bağlantı kapatma hatası: {e}")
        # Zorla kapat
        try:
            conn.close()
        except:
            pass

def close_all_connections():
    """
    Tüm bağlantıları kapat (Uygulama kapanırken çağrılır)
    """
    global _connection_pool
    
    if _connection_pool is not None:
        try:
            _connection_pool.closeall()
            logger.info("✅ Tüm veritabanı bağlantıları kapatıldı")
        except Exception as e:
            logger.error(f"❌ Bağlantıları kapatma hatası: {e}")
        finally:
            _connection_pool = None

def test_connection():
    """
    Veritabanı bağlantısını test eder
    
    Returns:
        bool: Bağlantı başarılı ise True
    """
    try:
        conn = get_db()
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        result = cur.fetchone()
        cur.close()
        put_db(conn)
        
        if result:
            logger.info("✅ Veritabanı bağlantısı başarılı")
            return True
        else:
            logger.error("❌ Veritabanı sorgu hatası")
            return False
            
    except Exception as e:
        logger.error(f"❌ Veritabanı test hatası: {e}")
        return False

def get_pool_status():
    """
    Connection pool durumunu döndürür (debug için)
    
    Returns:
        dict: Pool istatistikleri
    """
    global _connection_pool
    
    if _connection_pool is None:
        return {"status": "not_initialized"}
    
    try:
        # Pool'daki bağlantı sayılarını hesapla
        # Not: SimpleConnectionPool bu bilgiyi direkt vermez,
        # bu yüzden manuel takip gerekebilir
        
        return {
            "status": "active",
            "min_connections": 1,
            "max_connections": 5,
            "pool_type": "SimpleConnectionPool"
        }
    except Exception as e:
        logger.error(f"❌ Pool status hatası: {e}")
        return {"status": "error", "error": str(e)}
