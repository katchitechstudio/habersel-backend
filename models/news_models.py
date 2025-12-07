from datetime import datetime, timedelta
from config import Config
from models.db import get_db, put_db
import logging
import pytz

logger = logging.getLogger(__name__)


class NewsModel:

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
                    full_content TEXT,
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

    @staticmethod
    def save_article(article: dict, category: str, api_source: str = "unknown") -> bool:
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            expires = datetime.now(pytz.UTC) + timedelta(days=Config.NEWS_EXPIRATION_DAYS)

            title = (article.get("title") or "").strip()
            description = (article.get("description") or "").strip()
            url = (article.get("url") or "").strip()
            image = article.get("image") or article.get("urlToImage")

            published_raw = article.get("publishedAt")

            published = None
            if isinstance(published_raw, datetime):
                if published_raw.tzinfo is None:
                    published = published_raw.replace(tzinfo=pytz.UTC)
                else:
                    published = published_raw
            elif isinstance(published_raw, str):
                try:
                    published = datetime.fromisoformat(published_raw.replace("Z", "+00:00"))
                except Exception:
                    try:
                        from dateutil import parser
                        parsed = parser.parse(published_raw)
                        if parsed.tzinfo is None:
                            published = parsed.replace(tzinfo=pytz.UTC)
                        else:
                            published = parsed
                    except:
                        published = datetime.now(pytz.UTC)
            else:
                published = datetime.now(pytz.UTC)

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
                logger.debug(f"✅ Kaydedildi: {title[:50]}... (expires: {expires.isoformat()})")
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

    @staticmethod
    def get_news(category: str = None, limit: int = 50, offset: int = 0):
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            if category:
                query = """
                    SELECT id, category, title, description, full_content,
                           url, image, source, published, saved_at
                    FROM news
                    WHERE category = %s AND expires_at > NOW()
                    ORDER BY saved_at DESC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(query, (category, limit, offset))
                logger.debug(f"🔍 Query: category={category}, limit={limit}, offset={offset}")
            else:
                query = """
                    SELECT id, category, title, description, full_content,
                           url, image, source, published, saved_at
                    FROM news
                    WHERE expires_at > NOW()
                    ORDER BY saved_at DESC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(query, (limit, offset))
                logger.debug(f"🔍 Query: ALL categories, limit={limit}, offset={offset}")

            rows = cur.fetchall()
            
            logger.info(f"📊 Query sonucu: {len(rows)} haber bulundu")
            
            if rows:
                logger.debug(f"🔍 İlk satır tipi: {type(rows[0])}")
                logger.debug(f"🔍 İlk satır: {rows[0]}")

            data = []
            for r in rows:
                try:
                    data.append({
                        "id": r[0],
                        "category": r[1],
                        "title": r[2],
                        "description": r[3],
                        "full_content": r[4],
                        "url": r[5],
                        "image": r[6],
                        "source": r[7],
                        "published": r[8].isoformat() if r[8] else None,
                        "saved_at": r[9].isoformat() if r[9] else None,
                    })
                except (KeyError, IndexError, TypeError) as e:
                    logger.error(f"❌ Satır parse hatası: {e}, row type: {type(r)}, row: {r}")
                    raise

            logger.info(f"✅ {len(data)} haber parse edildi")
            return data

        except Exception as e:
            logger.exception(f"❌ Haber getirme hatası")
            return []
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

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
            
            if result:
                count = result[0]
                logger.debug(f"📊 {category}: {count} haber")
                return count
            else:
                logger.debug(f"📊 {category}: 0 haber (result=None)")
                return 0
            
        except Exception as e:
            logger.exception(f"❌ count_by_category hatası")
            return 0
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def get_total_count():
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM news WHERE expires_at > NOW();")
            
            result = cur.fetchone()
            
            if result:
                count = result[0]
                logger.debug(f"📊 Toplam: {count} haber")
                return count
            else:
                logger.debug(f"📊 Toplam: 0 haber (result=None)")
                return 0
            
        except Exception as e:
            logger.exception(f"❌ get_total_count hatası")
            return 0
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def get_latest_update_time():
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("SELECT MAX(saved_at) FROM news;")
            
            result = cur.fetchone()
            
            if result and result[0]:
                timestamp = result[0]
                logger.debug(f"📅 Son güncelleme: {timestamp.isoformat()}")
                return timestamp
            else:
                logger.debug("📅 Henüz haber yok")
                return None
            
        except Exception as e:
            logger.exception(f"❌ get_latest_update_time hatası")
            return None
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def get_articles_without_content(limit: int = 20):
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT id, title, url, source, image
                FROM news
                WHERE full_content IS NULL AND expires_at > NOW()
                ORDER BY saved_at DESC
                LIMIT %s;
            """, (limit,))
            
            rows = cur.fetchall()
            
            articles = []
            for r in rows:
                articles.append({
                    "id": r[0],
                    "title": r[1],
                    "url": r[2],
                    "source": r[3],
                    "image": r[4]
                })
            
            return articles
            
        except Exception as e:
            logger.exception("❌ get_articles_without_content hatası")
            return []
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def update_full_content(article_id: int, full_content: str, image_url: str = None):
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            if image_url:
                cur.execute("""
                    UPDATE news
                    SET full_content = %s, image = %s
                    WHERE id = %s;
                """, (full_content, image_url, article_id))
            else:
                cur.execute("""
                    UPDATE news
                    SET full_content = %s
                    WHERE id = %s;
                """, (full_content, article_id))
            
            conn.commit()
            
        except Exception as e:
            logger.error(f"❌ update_full_content hatası: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)
