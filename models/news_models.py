from datetime import datetime, timedelta
from config import Config
from models.db import get_db, put_db
import logging

logger = logging.getLogger(__name__)

class NewsModel:
    """
    Haber veritabanı işlemleri
    - Tablo oluşturma
    - Haber kaydetme (duplicate kontrolü ile)
    - Süresi geçmiş haberleri silme
    - Kategori bazlı listeleme
    """
    
    @staticmethod
    def create_table():
        """
        Haber tablosu yoksa oluşturur.
        
        Özellikler:
        - UNIQUE(title, url) → Aynı haberin tekrar eklenmesini engeller
        - expires_at → 3 gün sonra otomatik silinecek
        - INDEX → Kategori ve tarih bazlı sorgular hızlı olur
        """
        conn = get_db()
        cur = conn.cursor()
        
        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS news (
                    id SERIAL PRIMARY KEY,
                    category VARCHAR(50) NOT NULL,
                    title TEXT NOT NULL,
                    description TEXT,
                    url TEXT NOT NULL,
                    image TEXT,
                    source VARCHAR(100),
                    published TIMESTAMP,
                    saved_at TIMESTAMP DEFAULT NOW(),
                    expires_at TIMESTAMP NOT NULL,
                    
                    -- Duplicate engelleme
                    CONSTRAINT unique_news UNIQUE (title, url)
                );
                
                -- İndeksler (Performans için)
                CREATE INDEX IF NOT EXISTS idx_category ON news(category);
                CREATE INDEX IF NOT EXISTS idx_saved_at ON news(saved_at DESC);
                CREATE INDEX IF NOT EXISTS idx_expires_at ON news(expires_at);
            """)
            
            conn.commit()
            logger.info("✅ Haber tablosu hazır")
            
        except Exception as e:
            logger.error(f"❌ Tablo oluşturma hatası: {e}")
            conn.rollback()
            raise
        finally:
            put_db(conn)
    
    @staticmethod
    def save_article(article: dict, category: str, api_source: str = "unknown"):
        """
        Tek bir haberi veritabanına kaydeder.
        
        Args:
            article: Haber verisi (dict)
            category: Kategori (technology, sports, vb.)
            api_source: Hangi API'den geldi (gnews, currents, vb.)
        
        Returns:
            bool: Başarılı ise True, duplicate ise False
        """
        conn = get_db()
        cur = conn.cursor()
        
        # Expire süresi hesapla (şu andan 3 gün sonra)
        expires = datetime.utcnow() + timedelta(days=Config.NEWS_EXPIRATION_DAYS)
        
        try:
            # Haber kaydetme
            cur.execute("""
                INSERT INTO news (
                    category, 
                    title, 
                    description, 
                    url, 
                    image, 
                    source, 
                    published, 
                    expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (title, url) DO NOTHING
                RETURNING id;
            """, (
                category,
                article.get("title", "").strip(),
                article.get("description", "").strip(),
                article.get("url", "").strip(),
                article.get("image") or article.get("urlToImage"),  # API'lere göre farklı
                api_source,
                article.get("publishedAt") or datetime.utcnow(),
                expires
            ))
            
            result = cur.fetchone()
            conn.commit()
            
            if result:
                logger.debug(f"✅ Yeni haber eklendi: {article.get('title', '')[:50]}...")
                return True
            else:
                logger.debug(f"⏭️  Duplicate haber atlandı: {article.get('title', '')[:50]}...")
                return False
                
        except Exception as e:
            logger.error(f"❌ Haber kaydedilemedi: {e}")
            logger.error(f"   Haber: {article.get('title', 'N/A')[:50]}")
            conn.rollback()
            return False
        finally:
            put_db(conn)
    
    @staticmethod
    def save_bulk(articles: list, category: str, api_source: str = "unknown"):
        """
        Birden fazla haberi toplu kaydet
        
        Args:
            articles: Haber listesi
            category: Kategori
            api_source: API kaynağı
        
        Returns:
            dict: {"saved": int, "duplicates": int, "errors": int}
        """
        stats = {"saved": 0, "duplicates": 0, "errors": 0}
        
        for article in articles:
            if not article.get("title") or not article.get("url"):
                stats["errors"] += 1
                continue
            
            result = NewsModel.save_article(article, category, api_source)
            
            if result:
                stats["saved"] += 1
            else:
                stats["duplicates"] += 1
        
        logger.info(f"📊 {api_source} → {category}: "
                   f"{stats['saved']} yeni, "
                   f"{stats['duplicates']} duplicate, "
                   f"{stats['errors']} hata")
        
        return stats
    
    @staticmethod
    def delete_expired():
        """
        Süresi geçmiş haberleri siler
        Returns: Silinen haber sayısı
        """
        conn = get_db()
        cur = conn.cursor()
        
        try:
            cur.execute("DELETE FROM news WHERE expires_at < NOW() RETURNING id;")
            deleted_rows = cur.fetchall()
            deleted_count = len(deleted_rows)
            
            conn.commit()
            
            if deleted_count > 0:
                logger.info(f"🗑️  {deleted_count} eski haber silindi")
            else:
                logger.debug("✅ Silinecek eski haber yok")
            
            return deleted_count
            
        except Exception as e:
            logger.error(f"❌ Eski haber silme hatası: {e}")
            conn.rollback()
            return 0
        finally:
            put_db(conn)
    
    @staticmethod
    def get_news(category: str = None, limit: int = 50, offset: int = 0):
        """
        Haberleri getir (Android app için)
        
        Args:
            category: Kategori filtresi (None ise tümü)
            limit: Kaç haber
            offset: Sayfalama için offset
        
        Returns:
            list: Haber listesi (dict formatında)
        """
        conn = get_db()
        cur = conn.cursor()
        
        try:
            if category:
                query = """
                    SELECT 
                        id, category, title, description, 
                        url, image, source, published, saved_at
                    FROM news
                    WHERE category = %s AND expires_at > NOW()
                    ORDER BY saved_at DESC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(query, (category, limit, offset))
            else:
                query = """
                    SELECT 
                        id, category, title, description, 
                        url, image, source, published, saved_at
                    FROM news
                    WHERE expires_at > NOW()
                    ORDER BY saved_at DESC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(query, (limit, offset))
            
            rows = cur.fetchall()
            
            # Dict formatına çevir
            news_list = []
            for row in rows:
                news_list.append({
                    "id": row[0],
                    "category": row[1],
                    "title": row[2],
                    "description": row[3],
                    "url": row[4],
                    "image": row[5],
                    "source": row[6],
                    "published": row[7].isoformat() if row[7] else None,
                    "saved_at": row[8].isoformat() if row[8] else None
                })
            
            return news_list
            
        except Exception as e:
            logger.error(f"❌ Haber getirme hatası: {e}")
            return []
        finally:
            put_db(conn)
    
    @staticmethod
    def get_by_category(category: str, limit: int = 50):
        """
        Kategoriye göre haber getir (geriye uyumluluk için)
        """
        return NewsModel.get_news(category=category, limit=limit)
    
    @staticmethod
    def count_by_category(category: str):
        """
        Belirli bir kategoride kaç haber var?
        
        Returns:
            int: Haber sayısı
        """
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT COUNT(*) 
                FROM news 
                WHERE category = %s AND expires_at > NOW();
            """, (category,))
            
            result = cur.fetchone()
            cur.close()
            
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"❌ Count hatası: {e}")
            return 0
        finally:
            if conn:
                put_db(conn)
    
    @staticmethod
    def get_total_count():
        """
        Toplam haber sayısı
        """
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM news WHERE expires_at > NOW();")
            
            result = cur.fetchone()
            cur.close()
            
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"❌ Total count hatası: {e}")
            return 0
        finally:
            if conn:
                put_db(conn)
    
    @staticmethod
    def get_latest_update_time():
        """
        En son haber ekleme zamanı
        """
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("SELECT MAX(saved_at) FROM news;")
            
            result = cur.fetchone()
            cur.close()
            
            return result[0] if result and result[0] else None
            
        except Exception as e:
            logger.error(f"❌ Latest update time hatası: {e}")
            return None
        finally:
            if conn:
                put_db(conn)
