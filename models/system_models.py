from models.db import get_db, put_db
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class SystemModel:
    """
    Sistem ile ilgili meta verileri tutan model.
    - last_update: Haberlerin en son ne zaman güncellendiği
    """

    @staticmethod
    def create_table():
        """
        system_info tablosunu oluşturur ve varsayılan tek kaydı ekler.
        """
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS system_info (
                    id INTEGER PRIMARY KEY,
                    last_update TIMESTAMP
                );
            """)
            conn.commit()

            # ID=1 satırı yoksa ekleyelim
            cur.execute("SELECT id FROM system_info WHERE id = 1;")
            exists = cur.fetchone()

            if not exists:
                cur.execute("""
                    INSERT INTO system_info (id, last_update)
                    VALUES (1, NULL);
                """)
                conn.commit()
                logger.info("🟢 system_info tablosu oluşturuldu ve varsayılan kayıt eklendi.")
            else:
                logger.info("✅ system_info tablosu zaten mevcut.")

        except Exception as e:
            logger.error(f"❌ system_info tablo oluşturma hatası: {e}")
            conn.rollback()
            raise

        finally:
            put_db(conn)

    # ----------------------------------------------------------
    # LAST UPDATE DEĞERİ
    # ----------------------------------------------------------

    @staticmethod
    def get_last_update():
        """
        En son güncelleme zamanını döndürür.
        Returns:
            datetime | None
        """
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("SELECT last_update FROM system_info WHERE id = 1;")
            row = cur.fetchone()

            if row and row[0]:
                return row[0]
            return None

        except Exception as e:
            logger.error(f"❌ last_update okunamadı: {e}")
            return None

        finally:
            put_db(conn)

    @staticmethod
    def set_last_update(dt: datetime):
        """
        last_update değerini günceller.
        Args:
            dt: datetime (UTC)
        """
        conn = get_db()
        cur = conn.cursor()

        try:
            cur.execute("""
                UPDATE system_info
                SET last_update = %s
                WHERE id = 1;
            """, (dt,))

            conn.commit()
            logger.info(f"💾 last_update güncellendi → {dt.isoformat()}")

        except Exception as e:
            logger.error(f"❌ last_update yazılamadı: {e}")
            conn.rollback()

        finally:
            put_db(conn)
