from rapidfuzz import fuzz
from datetime import datetime
from typing import List, Dict, Optional
import logging
from config import Config

logger = logging.getLogger(__name__)

# ------------------------------------------
# Ayarlar (Config)
# ------------------------------------------
SIMILARITY_THRESHOLD = Config.SIMILARITY_THRESHOLD      # Başlık %85
TIME_DIFF_THRESHOLD = Config.TIME_DIFF_THRESHOLD        # 15 dk (900 sn)


# -----------------------------------------------------------
# 1) Başlık Benzerliği (Zarif & Stabil)
# -----------------------------------------------------------
def titles_similar(t1: str, t2: str, threshold: int = None) -> bool:
    if not t1 or not t2:
        return False

    threshold = threshold or SIMILARITY_THRESHOLD

    t1_norm = " ".join(t1.lower().split())
    t2_norm = " ".join(t2.lower().split())

    if t1_norm == t2_norm:
        return True

    similarity = fuzz.ratio(t1_norm, t2_norm)
    return similarity >= threshold


# -----------------------------------------------------------
# 2) URL Benzerliği (Ultra Güçlü Normalizasyon)
# -----------------------------------------------------------
def urls_similar(u1: str, u2: str) -> bool:
    if not u1 or not u2:
        return False

    def clean(url: str) -> str:
        url = (
            url.lower()
            .replace("https://", "")
            .replace("http://", "")
            .replace("www.", "")
            .split("?")[0]
            .split("#")[0]
            .rstrip("/")
        )
        return url

    u1c = clean(u1)
    u2c = clean(u2)

    if u1c == u2c:
        return True

    # m.example.com/news/123 ≈ example.com/news/123
    def get_path(url: str) -> str:
        parts = url.split("/", 1)
        return parts[1] if len(parts) > 1 else ""

    return get_path(u1c) == get_path(u2c)


# -----------------------------------------------------------
# 3) Tarih Yakınlığı (± TIME_DIFF_THRESHOLD saniye)
# -----------------------------------------------------------
def dates_close(d1: Optional[str], d2: Optional[str], threshold: int = None) -> bool:
    if not d1 or not d2:
        return False

    threshold = threshold or TIME_DIFF_THRESHOLD

    try:
        dt1 = datetime.fromisoformat(d1.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(d2.replace("Z", "+00:00"))
    except:
        try:
            from dateutil import parser
            dt1 = parser.parse(d1)
            dt2 = parser.parse(d2)
        except:
            return False

    diff = abs((dt1 - dt2).total_seconds())
    return diff <= threshold


# -----------------------------------------------------------
# 4) Duplicate Temizleyici (Ana Motor)
# -----------------------------------------------------------
def remove_duplicates(news_list: List[Dict]) -> List[Dict]:
    if not news_list:
        return []

    unique = []
    deleted = 0

    for article in news_list:
        a_title = article.get("title", "")
        a_url = article.get("url", "")
        a_date = article.get("publishedAt", "")

        is_dup = False

        for existing in unique:
            e_title = existing.get("title", "")
            e_url = existing.get("url", "")
            e_date = existing.get("publishedAt", "")

            # 1) Başlık %85+
            if titles_similar(a_title, e_title):
                is_dup = True
                break

            # 2) URL aynı
            if urls_similar(a_url, e_url):
                is_dup = True
                break

            # 3) Tarih yakın + başlık %70+
            if dates_close(a_date, e_date) and titles_similar(a_title, e_title, threshold=70):
                is_dup = True
                break

        if not is_dup:
            unique.append(article)
        else:
            deleted += 1

    logger.info(f"🧹 Duplicate temizleme: {len(news_list)} → {len(unique)} "
                f"({deleted} duplicate)")

    return unique


# -----------------------------------------------------------
# 5) Mevcut Haberlerle Karşılaştırma (DB Kontrolü)
# -----------------------------------------------------------
def filter_against_existing(new_articles: List[Dict], existing_articles: List[Dict]) -> List[Dict]:
    if not existing_articles:
        return new_articles

    result = []
    for new in new_articles:
        is_dup = False

        for old in existing_articles:
            if titles_similar(new.get("title", ""), old.get("title", "")):
                is_dup = True
                break
            if urls_similar(new.get("url", ""), old.get("url", "")):
                is_dup = True
                break

        if not is_dup:
            result.append(new)

    return result


# -----------------------------------------------------------
# 6) Duplicate İstatistikleri (Analiz)
# -----------------------------------------------------------
def get_duplicate_stats(news_list: List[Dict]) -> Dict:
    total = len(news_list)
    unique_count = len(remove_duplicates(news_list))
    dup_count = total - unique_count

    return {
        "total": total,
        "unique": unique_count,
        "duplicates": dup_count,
        "duplicate_rate": round((dup_count / total * 100), 2) if total else 0,
    }


# -----------------------------------------------------------
# 7) Haber Kalite Skoru (0–100)
# -----------------------------------------------------------
def calculate_quality_score(article: Dict) -> int:
    score = 0

    if article.get("title") and len(article["title"]) > 10:
        score += 20
    if article.get("description") and len(article["description"]) > 20:
        score += 20
    if article.get("image"):
        score += 20
    if article.get("url"):
        score += 20
    if article.get("publishedAt"):
        score += 20

    return score


# -----------------------------------------------------------
# 8) Düşük Kalite Filtreleyici
# -----------------------------------------------------------
def filter_low_quality(news_list: List[Dict], min_score: int = 60) -> List[Dict]:
    result = []
    for n in news_list:
        s = calculate_quality_score(n)
        if s >= min_score:
            result.append(n)

    logger.info(f"🎯 Kalite filtresi: {len(news_list)} → {len(result)}")
    return result
