import psycopg2
from psycopg2 import pool
from psycopg2.extras import RealDictCursor
from config import Config
import logging
import time

logger = logging.getLogger(__name__)

_connection_pool = None

def init_connection_pool():
    global _connection_pool
    
    if _connection_pool is not None:
        logger.debug("✅ Connection pool zaten mevcut")
        return _connection_pool
    
    try:
        _connection_pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=2,
            maxconn=10,
            dsn=Config.DB_URL,
            connect_timeout=10,
            options="-c statement_timeout=30000"
        )
        
        logger.info("✅ PostgreSQL connection pool oluşturuldu (ThreadedConnectionPool)")
        return _connection_pool
        
    except Exception as e:
        logger.error(f"❌ Connection pool oluşturulamadı: {e}")
        raise

def get_db():
    global _connection_pool
    
    if _connection_pool is None:
        init_connection_pool()
    
    max_attempts = 3
    attempt = 0
    
    while attempt < max_attempts:
        try:
            conn = _connection_pool.getconn()
            
            if conn.closed:
                logger.warning("⚠️  Bağlantı kapalı, yeniden açılıyor...")
                _connection_pool.putconn(conn, close=True)
                conn = _connection_pool.getconn()
            
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1")
                return conn
            except (psycopg2.OperationalError, psycopg2.InterfaceError) as e:
                logger.warning(f"⚠️  Bağlantı test başarısız, yenileniyor: {e}")
                _connection_pool.putconn(conn, close=True)
                attempt += 1
                time.sleep(1)
                continue
            
        except psycopg2.pool.PoolError as e:
            logger.error(f"❌ Connection pool hatası: {e}")
            try:
                conn = psycopg2.connect(
                    Config.DB_URL,
                    connect_timeout=10,
                    options="-c statement_timeout=30000"
                )
                logger.warning("⚠️  Pool dolu, direkt bağlantı açıldı")
                return conn
            except Exception as direct_error:
                logger.error(f"❌ Direkt bağlantı da başarısız: {direct_error}")
                attempt += 1
                time.sleep(2)
                continue
        
        except Exception as e:
            logger.error(f"❌ DB bağlantı hatası: {e}")
            attempt += 1
            if attempt < max_attempts:
                logger.info(f"🔄 Yeniden deneniyor... ({attempt}/{max_attempts})")
                time.sleep(Config.RETRY_DELAY)
            else:
                raise

def put_db(conn):
    global _connection_pool
    
    if conn is None:
        return
    
    try:
        if conn.closed:
            logger.debug("⚠️  Kapalı bağlantı tespit edildi")
            if _connection_pool is not None:
                try:
                    _connection_pool.putconn(conn, close=True)
                except:
                    pass
            return
        
        if _connection_pool is not None:
            try:
                _connection_pool.putconn(conn)
                logger.debug("✅ Bağlantı havuza geri kondu")
            except Exception as e:
                logger.warning(f"⚠️  Havuza geri koyma başarısız, kapatılıyor: {e}")
                try:
                    conn.close()
                except:
                    pass
        else:
            conn.close()
            logger.debug("✅ Bağlantı kapatıldı")
            
    except Exception as e:
        logger.error(f"❌ Bağlantı kapatma hatası: {e}")
        try:
            if not conn.closed:
                conn.close()
        except:
            pass

def close_all_connections():
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
    global _connection_pool
    
    if _connection_pool is None:
        return {"status": "not_initialized"}
    
    try:
        return {
            "status": "active",
            "min_connections": 2,
            "max_connections": 10,
            "pool_type": "ThreadedConnectionPool"
        }
    except Exception as e:
        logger.error(f"❌ Pool status hatası: {e}")
        return {"status": "error", "error": str(e)}
