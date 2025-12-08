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
                CREATE INDEX IF NOT EXISTS idx_news_full_content ON news(full_content) WHERE full_content IS NOT NULL;
                
                -- Blacklist tablosu
                CREATE TABLE IF NOT EXISTS scraping_blacklist (
                    id SERIAL PRIMARY KEY,
                    url TEXT NOT NULL UNIQUE,
                    fail_count INTEGER DEFAULT 1,
                    last_attempt TIMESTAMP DEFAULT NOW(),
                    reason TEXT
                );
                
                CREATE INDEX IF NOT EXISTS idx_blacklist_url ON scraping_blacklist(url);
            """)
            
            cur.execute("""
                DO $$ 
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.columns 
                        WHERE table_name='news' AND column_name='full_content'
                    ) THEN
                        ALTER TABLE news ADD COLUMN full_content TEXT;
                    END IF;
                END $$;
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
        """
        TÜM haberleri getir (eski metot - geriye dönük uyumluluk için)
        ⚠️ Android için artık get_scraped_only() kullanılmalı
        """
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

    # ========================================
    # 🎯 YENİ METODLAR - SADECE SCRAPE EDİLMİŞ HABERLER
    # ========================================

    @staticmethod
    def get_scraped_only(category: str = None, limit: int = 50, offset: int = 0):
        """
        ✅ SADECE scrape edilmiş (tam metin) haberleri getir
        Android için kullan - boş içerikli haber dönmez
        """
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            if category:
                query = """
                    SELECT id, category, title, description, full_content,
                           url, image, source, published, saved_at
                    FROM news
                    WHERE category = %s 
                      AND expires_at > NOW()
                      AND full_content IS NOT NULL
                      AND LENGTH(full_content) > 100
                    ORDER BY saved_at DESC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(query, (category, limit, offset))
                logger.debug(f"🔍 Scraped query: category={category}, limit={limit}, offset={offset}")
            else:
                query = """
                    SELECT id, category, title, description, full_content,
                           url, image, source, published, saved_at
                    FROM news
                    WHERE expires_at > NOW()
                      AND full_content IS NOT NULL
                      AND LENGTH(full_content) > 100
                    ORDER BY saved_at DESC
                    LIMIT %s OFFSET %s;
                """
                cur.execute(query, (limit, offset))
                logger.debug(f"🔍 Scraped query: ALL categories, limit={limit}, offset={offset}")

            rows = cur.fetchall()
            
            logger.info(f"📊 Scrape edilmiş {len(rows)} haber bulundu")

            data = []
            for r in rows:
                try:
                    data.append({
                        "id": r[0],
                        "category": r[1],
                        "title": r[2],
                        "description": r[3],
                        "full_content": r[4],  # ✅ Kesinlikle dolu
                        "url": r[5],
                        "image": r[6],
                        "source": r[7],
                        "published": r[8].isoformat() if r[8] else None,
                        "saved_at": r[9].isoformat() if r[9] else None,
                    })
                except (KeyError, IndexError, TypeError) as e:
                    logger.error(f"❌ Satır parse hatası: {e}")
                    raise

            logger.info(f"✅ {len(data)} tam metin haber parse edildi")
            return data

        except Exception as e:
            logger.exception(f"❌ Scraped haberler getirme hatası")
            return []
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def get_scraped_after(after_date: str, category: str = None, limit: int = 50):
        """
        ✅ Belirli tarihten sonra scrape edilmiş haberleri getir
        Android Worker için - sadece yeni tam metin haberler
        
        Args:
            after_date: ISO format (örn: "2025-12-08T15:00:00+00:00")
            category: Kategori filtresi (opsiyonel)
            limit: Maksimum haber sayısı
        """
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            # Tarih parse
            try:
                after_dt = datetime.fromisoformat(after_date.replace("Z", "+00:00"))
            except:
                logger.error(f"❌ Geçersiz tarih formatı: {after_date}")
                return []

            if category:
                query = """
                    SELECT id, category, title, description, full_content,
                           url, image, source, published, saved_at
                    FROM news
                    WHERE category = %s
                      AND saved_at > %s
                      AND expires_at > NOW()
                      AND full_content IS NOT NULL
                      AND LENGTH(full_content) > 100
                    ORDER BY saved_at DESC
                    LIMIT %s;
                """
                cur.execute(query, (category, after_dt, limit))
            else:
                query = """
                    SELECT id, category, title, description, full_content,
                           url, image, source, published, saved_at
                    FROM news
                    WHERE saved_at > %s
                      AND expires_at > NOW()
                      AND full_content IS NOT NULL
                      AND LENGTH(full_content) > 100
                    ORDER BY saved_at DESC
                    LIMIT %s;
                """
                cur.execute(query, (after_dt, limit))

            rows = cur.fetchall()
            
            logger.info(f"📊 {after_date} sonrası {len(rows)} scrape edilmiş haber")

            data = []
            for r in rows:
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

            return data

        except Exception as e:
            logger.exception(f"❌ get_scraped_after hatası")
            return []
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def get_unscraped(limit: int = 15, exclude_blacklist: bool = True):
        """
        ✅ Henüz scrape edilmemiş haberleri getir
        Scraper için kullan - blacklist'tekileri atla
        
        Args:
            limit: Kaç haber çekilecek
            exclude_blacklist: Blacklist'teki URL'leri atla mı?
        """
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()

            if exclude_blacklist:
                query = """
                    SELECT id, title, url, source, image
                    FROM news
                    WHERE (full_content IS NULL OR LENGTH(full_content) < 100)
                      AND expires_at > NOW()
                      AND url NOT IN (SELECT url FROM scraping_blacklist)
                    ORDER BY saved_at DESC
                    LIMIT %s;
                """
            else:
                query = """
                    SELECT id, title, url, source, image
                    FROM news
                    WHERE (full_content IS NULL OR LENGTH(full_content) < 100)
                      AND expires_at > NOW()
                    ORDER BY saved_at DESC
                    LIMIT %s;
                """
            
            cur.execute(query, (limit,))
            rows = cur.fetchall()
            
            logger.info(f"📊 {len(rows)} scrape edilmemiş haber bulundu")
            
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
            logger.exception("❌ get_unscraped hatası")
            return []
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def update_full_content(article_id: int, full_content: str, image_url: str = None):
        """
        ✅ Scraping sonucunu kaydet
        """
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
            logger.debug(f"✅ Haber #{article_id} full_content güncellendi ({len(full_content)} karakter)")
            
        except Exception as e:
            logger.error(f"❌ update_full_content hatası: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    # ========================================
    # 🚫 BLACKLIST YÖNETİMİ
    # ========================================

    @staticmethod
    def add_to_blacklist(url: str, reason: str = "scraping_failed"):
        """
        ✅ URL'i blacklist'e ekle veya fail_count'u artır
        """
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("""
                INSERT INTO scraping_blacklist (url, fail_count, reason, last_attempt)
                VALUES (%s, 1, %s, NOW())
                ON CONFLICT (url) 
                DO UPDATE SET 
                    fail_count = scraping_blacklist.fail_count + 1,
                    last_attempt = NOW(),
                    reason = EXCLUDED.reason
                RETURNING fail_count;
            """, (url, reason))
            
            result = cur.fetchone()
            conn.commit()
            
            if result:
                fail_count = result[0]
                if fail_count >= 3:
                    logger.warning(f"🚫 {url[:60]}... blacklist'e eklendi ({fail_count} başarısız)")
                else:
                    logger.debug(f"⚠️ {url[:60]}... başarısız sayısı: {fail_count}")
            
        except Exception as e:
            logger.error(f"❌ add_to_blacklist hatası: {e}")
            if conn:
                conn.rollback()
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def is_blacklisted(url: str, threshold: int = 3) -> bool:
        """
        ✅ URL blacklist'te mi kontrol et
        
        Args:
            url: Kontrol edilecek URL
            threshold: Kaç başarısızlıktan sonra blacklist sayılsın (varsayılan 3)
        """
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT fail_count FROM scraping_blacklist
                WHERE url = %s;
            """, (url,))
            
            result = cur.fetchone()
            
            if result and result[0] >= threshold:
                return True
            return False
            
        except Exception as e:
            logger.error(f"❌ is_blacklisted hatası: {e}")
            return False
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def get_blacklist_count() -> int:
        """
        ✅ Blacklist'teki toplam URL sayısını getir
        """
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("SELECT COUNT(*) FROM scraping_blacklist WHERE fail_count >= 3;")
            result = cur.fetchone()
            
            return result[0] if result else 0
            
        except Exception as e:
            logger.error(f"❌ get_blacklist_count hatası: {e}")
            return 0
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    # ========================================
    # 📊 İSTATİSTİK METODLARI (Değişiklik Yok)
    # ========================================

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
        """
        ⚠️ ESKİ METOT - Artık get_unscraped() kullanın
        Geriye dönük uyumluluk için bırakıldı
        """
        return NewsModel.get_unscraped(limit=limit, exclude_blacklist=False)

    @staticmethod
    def count_scraped():
        """
        ✅ Scrape edilmiş haber sayısını getir
        """
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT COUNT(*) FROM news
                WHERE full_content IS NOT NULL 
                  AND LENGTH(full_content) > 100
                  AND expires_at > NOW();
            """)
            
            result = cur.fetchone()
            return result[0] if result else 0
            
        except Exception as e:
            logger.exception(f"❌ count_scraped hatası")
            return 0
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)

    @staticmethod
    def count_unscraped():
        """
        ✅ Henüz scrape edilmemiş haber sayısını getir
        """
        conn = None
        try:
            conn = get_db()
            cur = conn.cursor()
            
            cur.execute("""
                SELECT COUNT(*) FROM news
                WHERE (full_content IS NULL OR LENGTH(full_content) < 100)
                  AND expires_at > NOW();
            """)
            
            result = cur.fetchone()
            return result[0] if result else 0
            
        except Exception as e:
            logger.exception(f"❌ count_unscraped hatası")
            return 0
        finally:
            if conn:
                cur.close() if 'cur' in locals() else None
                put_db(conn)
