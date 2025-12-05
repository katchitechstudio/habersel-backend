from datetime import datetime, timedelta
from config import Config
from models.db import get_db, put_db
import logging

logger = logging.getLogger(__name__)


class NewsModel:
    """
    Haber veritabanı işlemleri
    """

    # -------------------------------------------------------
    # TABLO
    # -------------------------------------------------------
    @staticmethod
    def create_table():
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

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
                    CONSTRAINT unique_news UNIQUE (title, url)
                );

                CREATE INDEX IF NOT EXISTS idx_news_category ON news(category);
                CREATE INDEX IF NOT EXISTS idx_news_saved_at ON news(saved_at DESC);
                CREATE INDEX IF NOT EXISTS idx_news_expires_at ON news(expires_at);
                CREATE INDEX IF NOT EXISTS idx_news_published ON news(published DESC);
            """)

            conn.commit()
            logger.info("✅ news tablosu hazır")

        except Exception as e:
            logger.error(f"❌ Tablo oluşturma hatası: {e}")
            if conn:
                conn.rollback()
            raise
        finally:
            if conn:
                put_db(conn)

    # -------------------------------------------------------
    # TEK HABER KAYDETME
    # -------------------------------------------------------
    @staticmethod
    def save_article(article: dict, category: str, api_source: str = "unknown") -> bool:
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            expires = datetime.utcnow() + timedelta(days=Config.NEWS_EXPIRATION_DAYS)

            title = (article.get("title") or "").strip()
            description = (article.get("description") or "").strip()
            url = (article.get("url") or "").strip()
            image = article.get("image") or article.get("urlToImage")

            published_raw = article.get("publishedAt")

            # Yayın tarihi normalize edilmesi
            published = None
            if isinstance(published_raw, datetime):
                published = published_raw
            elif isinstance(published_raw, str):
                try:
                    published = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                except Exception:
                    try:
                        from dateutil import parser
                        published = parser.parse(published_raw)
                    except:
                        published = datetime.utcnow()
            else:
                published = datetime.utcnow()

            # Zorunlu alan kontrolü
            if not title or not url:
                logger.warning("⚠️  Boş title veya url yüzünden haber atlandı")
                return False

            cur.execute("""
                INSERT INTO news (
                    category, title, description, url,
                    image, source, published, expires_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (title, url) DO NOTHING
                RETURNING id;
            """, (
                category,
                title,
                description,
                url,
                image,
                api_source,
                published,
                expires
            ))

            result = cur.fetchone()
            conn.commit()

            if result:
                logger.debug(f"✅ Kaydedildi: {title[:50]}...")
                return True
            else:
                logger.debug(f"⏭️ Duplicate atlandı: {title[:50]}...")
                return False

        except Exception as e:
            logger.error(f"❌ Haber kaydedilemedi: {e}")
            if conn:
                conn.rollback()
            return False
        finally:
            if conn:
                put_db(conn)

    # -------------------------------------------------------
    # BİR ÇOK HABERİ TOPLU KAYDETME
    # -------------------------------------------------------
    @staticmethod
    def save_bulk(articles: list, category: str, api_source: str = "unknown"):
        stats = {"saved": 0, "duplicates": 0, "errors": 0}

        for a in articles:
            if not a.get("title") or not a.get("url"):
                stats["errors"] += 1
                continue

            ok = NewsModel.save_article(a, category, api_source)

            if ok:
                stats["saved"] += 1
            else:
                stats["duplicates"] += 1

        logger.info(
            f"📊 {api_source} / {category}: "
            f"{stats['saved']} kaydedildi, "
            f"{stats['duplicates']} duplicate, "
            f"{stats['errors']} hata"
        )

        return stats

    # -------------------------------------------------------
    # SÜRESİ GEÇEN HABERLERİ SİLME
    # -------------------------------------------------------
    @staticmethod
    def delete_expired():
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            cur.execute("DELETE FROM news WHERE expires_at < NOW() RETURNING id;")
            rows = cur.fetchall()
            conn.commit()

            count = len(rows)
            if count > 0:
                logger.info(f"🗑️  {count} eski haber silindi")

            return count

        except Exception as e:
            logger.error(f"❌ Eski haber silme hatası: {e}")
            if conn:
                conn.rollback()
            return 0
        finally:
            if conn:
                put_db(conn)

    # -------------------------------------------------------
    # HABER GETİRME (ANDROID TARAFI)
    # -------------------------------------------------------
    @staticmethod
    def get_news(category: str = None, limit: int = 50, offset: int = 0):
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            if category:
                query = """
                    SELECT id, category, title, description,
                           url, image, source, published, saved_at
                    FROM news
                    WHERE category = %s AND expires_at > NOW()
                    ORDER BY saved_at DESC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(query, (category, limit, offset))
            else:
                query = """
                    SELECT id, category, title, description,
                           url, image, source, published, saved_at
                    FROM news
                    WHERE expires_at > NOW()
                    ORDER BY saved_at DESC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(query, (limit, offset))

            rows = cur.fetchall()

            data = []
            for r in rows:
                data.append({
                    "id": r[0],
                    "category": r[1],
                    "title": r[2],
                    "description": r[3],
                    "url": r[4],
                    "image": r[5],
                    "source": r[6],
                    "published": r[7].isoformat() if r[7] else None,
                    "saved_at": r[8].isoformat() if r[8] else None,
                })

            return data

        except Exception as e:
            logger.error(f"❌ Haber getirme hatası: {e}")
            return []
        finally:
            if conn:
                put_db(conn)

    # -------------------------------------------------------
    # CATEGORY COUNT (DÜZELTİLMİŞ)
    # -------------------------------------------------------
    @staticmethod
    def count_by_category(category: str):
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT COUNT(*) FROM news
                WHERE category = %s AND expires_at > NOW();
            """, (category,))
            
            result = cur.fetchone()
            cur.close()
            
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"❌ count_by_category hatası: {e}")
            return 0
        finally:
            if conn:
                put_db(conn)

    # -------------------------------------------------------
    # TOTAL COUNT (DÜZELTİLMİŞ)
    # -------------------------------------------------------
    @staticmethod
    def get_total_count():
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM news WHERE expires_at > NOW();")
            
            result = cur.fetchone()
            cur.close()
            
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"❌ get_total_count hatası: {e}")
            return 0
        finally:
            if conn:
                put_db(conn)

    # -------------------------------------------------------
    # EN SON EKLENME ZAMANI (DÜZELTİLMİŞ)
    # -------------------------------------------------------
    @staticmethod
    def get_latest_update_time():
        conn = None  # ✅ EN ÖNEMLİ DÜZELTİLME!
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("SELECT MAX(saved_at) FROM news;")
            
            result = cur.fetchone()
            cur.close()
            
            return result[0] if result and result[0] else None
            
        except Exception as e:
            logger.error(f"❌ get_latest_update_time hatası: {e}")
            return None
        finally:
            if conn:
                put_db(conn)
