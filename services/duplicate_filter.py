from rapidfuzz import fuzz
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging
from config import Config

logger = logging.getLogger(__name__)

# ------------------------------------------
# Ayarlar (Config'den alınır)
# ------------------------------------------
SIMILARITY_THRESHOLD = Config.SIMILARITY_THRESHOLD  # %85
TIME_DIFF_THRESHOLD = Config.TIME_DIFF_THRESHOLD    # 15 dakika (900 saniye)

# ------------------------------------------
# 1) Başlık Benzerliği (Geliştirilmiş)
# ------------------------------------------
def titles_similar(t1: str, t2: str, threshold: int = None) -> bool:
    """
    İki başlığın benzer olup olmadığını kontrol eder.
    
    Args:
        t1: İlk başlık
        t2: İkinci başlık
        threshold: Benzerlik eşiği (default: config'den)
    
    Returns:
        bool: Benzerlik eşiği aşılıysa True
    """
    if not t1 or not t2:
        return False
    
    if threshold is None:
        threshold = SIMILARITY_THRESHOLD
    
    # Normalizasyon (küçük harf + whitespace temizleme)
    t1_normalized = " ".join(t1.lower().split())
    t2_normalized = " ".join(t2.lower().split())
    
    # Tam eşleşme kontrolü
    if t1_normalized == t2_normalized:
        return True
    
    # Fuzzy similarity
    similarity = fuzz.ratio(t1_normalized, t2_normalized)
    
    logger.debug(f"📊 Başlık benzerliği: {similarity}% | {threshold}%")
    
    return similarity >= threshold


# ------------------------------------------
# 2) URL Benzerliği (Geliştirilmiş)
# ------------------------------------------
def urls_similar(u1: str, u2: str) -> bool:
    """
    İki URL'nin aynı habere işaret edip etmediğini kontrol eder.
    
    Normalizasyon:
    - http/https farkını yok sayar
    - www. farkını yok sayar
    - Query string'leri (?ref=...) atar
    - Fragment'leri (#section) atar
    - Trailing slash'leri atar
    
    Args:
        u1: İlk URL
        u2: İkinci URL
    
    Returns:
        bool: Aynı URL ise True
    """
    if not u1 or not u2:
        return False
    
    def normalize(url: str) -> str:
        """URL'i normalize et"""
        normalized = (
            url.lower()
            .replace("https://", "")
            .replace("http://", "")
            .replace("www.", "")
            .split("?")[0]  # Query string at
            .split("#")[0]  # Fragment at
            .rstrip("/")    # Trailing slash at
        )
        return normalized
    
    normalized_u1 = normalize(u1)
    normalized_u2 = normalize(u2)
    
    # Tam eşleşme
    if normalized_u1 == normalized_u2:
        logger.debug(f"🔗 URL eşleşti: {normalized_u1}")
        return True
    
    # Subdomain farkı varsa bile ana URL aynı mı?
    # Örnek: m.example.com/news/123 vs example.com/news/123
    def get_path(url: str) -> str:
        """Sadece path kısmını al (domain'siz)"""
        parts = url.split("/", 1)
        return parts[1] if len(parts) > 1 else ""
    
    path1 = get_path(normalized_u1)
    path2 = get_path(normalized_u2)
    
    if path1 and path2 and path1 == path2:
        logger.debug(f"🔗 URL path eşleşti: /{path1}")
        return True
    
    return False


# ------------------------------------------
# 3) Tarih Yakınlığı (Geliştirilmiş)
# ------------------------------------------
def dates_close(d1: Optional[str], d2: Optional[str], threshold: int = None) -> bool:
    """
    İki yayın tarihinin birbirine yakın olup olmadığını kontrol eder.
    
    Args:
        d1: İlk tarih (ISO format veya timestamp)
        d2: İkinci tarih (ISO format veya timestamp)
        threshold: Zaman farkı eşiği (saniye, default: config'den)
    
    Returns:
        bool: Tarihler yakınsa True
    """
    if not d1 or not d2:
        return False
    
    if threshold is None:
        threshold = TIME_DIFF_THRESHOLD
    
    try:
        # ISO format parse etmeyi dene
        dt1 = datetime.fromisoformat(d1.replace("Z", "+00:00"))
        dt2 = datetime.fromisoformat(d2.replace("Z", "+00:00"))
        
    except (ValueError, AttributeError):
        # ISO format değilse, farklı formatlarda dene
        try:
            from dateutil import parser
            dt1 = parser.parse(d1)
            dt2 = parser.parse(d2)
        except:
            logger.debug(f"⚠️  Tarih parse edilemedi: {d1} / {d2}")
            return False
    
    # Zaman farkını hesapla
    diff_seconds = abs((dt1 - dt2).total_seconds())
    
    logger.debug(f"⏰ Tarih farkı: {diff_seconds}s | Eşik: {threshold}s")
    
    return diff_seconds <= threshold


# ------------------------------------------
# 4) TEKİLLEŞTİRME (Ana Fonksiyon)
# ------------------------------------------
def remove_duplicates(news_list: List[Dict]) -> List[Dict]:
    """
    Haber listesinde duplicate haberleri temizler.
    
    Duplicate kriterleri (herhangi biri sağlanırsa duplicate):
    1. Başlıklar %85+ benzer
    2. URL'ler aynı
    3. Yayın zamanları ±15 dakika içinde VE başlıklar %70+ benzer
    
    Args:
        news_list: Haber listesi
    
    Returns:
        Duplicate'siz haber listesi
    """
    if not news_list:
        return []
    
    unique = []
    duplicates = []
    
    for article in news_list:
        duplicate_found = False
        duplicate_reason = None
        
        for existing in unique:
            # Kriter 1: Başlık benzerliği
            if titles_similar(article.get("title", ""), existing.get("title", "")):
                duplicate_found = True
                duplicate_reason = "başlık_benzerliği"
                break
            
            # Kriter 2: URL aynılığı
            if urls_similar(article.get("url", ""), existing.get("url", "")):
                duplicate_found = True
                duplicate_reason = "url_aynı"
                break
            
            # Kriter 3: Tarih yakınlığı + başlık %70 benzer
            if dates_close(
                article.get("publishedAt", ""),
                existing.get("publishedAt", "")
            ) and titles_similar(
                article.get("title", ""),
                existing.get("title", ""),
                threshold=70  # Daha düşük eşik
            ):
                duplicate_found = True
                duplicate_reason = "zaman_ve_başlık"
                break
        
        if duplicate_found:
            duplicates.append(article)
            logger.debug(f"⏭️  Duplicate atlandı ({duplicate_reason}): {article.get('title', '')[:50]}...")
        else:
            unique.append(article)
            logger.debug(f"✅ Benzersiz haber: {article.get('title', '')[:50]}...")
    
    # İstatistik logla
    if duplicates:
        logger.info(f"🧹 Duplicate temizleme: "
                   f"{len(news_list)} → {len(unique)} haber "
                   f"({len(duplicates)} duplicate atıldı)")
    else:
        logger.info(f"✅ Duplicate yok: {len(unique)} benzersiz haber")
    
    return unique


# ------------------------------------------
# 5) İki Liste Arasında Duplicate Kontrolü
# ------------------------------------------
def filter_against_existing(new_articles: List[Dict], existing_articles: List[Dict]) -> List[Dict]:
    """
    Yeni haberleri, mevcut haberlerle karşılaştırıp duplicate olanları filtreler.
    
    Kullanım: DB'ye kaydetmeden önce yeni haberlerin duplicate olup olmadığını kontrol et
    
    Args:
        new_articles: Yeni çekilen haberler
        existing_articles: DB'de zaten var olan haberler
    
    Returns:
        Sadece gerçekten yeni olan haberler
    """
    if not existing_articles:
        return new_articles
    
    unique_new = []
    
    for new in new_articles:
        is_duplicate = False
        
        for existing in existing_articles:
            if (
                titles_similar(new.get("title", ""), existing.get("title", "")) or
                urls_similar(new.get("url", ""), existing.get("url", ""))
            ):
                is_duplicate = True
                logger.debug(f"⏭️  Zaten var: {new.get('title', '')[:50]}...")
                break
        
        if not is_duplicate:
            unique_new.append(new)
    
    logger.info(f"📊 Yeni haberler: {len(new_articles)} → {len(unique_new)} gerçekten yeni")
    
    return unique_new


# ------------------------------------------
# 6) Duplicate İstatistikleri
# ------------------------------------------
def get_duplicate_stats(news_list: List[Dict]) -> Dict:
    """
    Haber listesindeki duplicate oranını hesaplar (analiz için)
    
    Returns:
        {
            "total": int,
            "unique": int,
            "duplicates": int,
            "duplicate_rate": float
        }
    """
    total = len(news_list)
    unique = len(remove_duplicates(news_list))
    duplicates = total - unique
    
    return {
        "total": total,
        "unique": unique,
        "duplicates": duplicates,
        "duplicate_rate": round((duplicates / total * 100), 2) if total > 0 else 0
    }


# ------------------------------------------
# 7) Haber Kalitesi Skorlama (Bonus)
# ------------------------------------------
def calculate_quality_score(article: Dict) -> int:
    """
    Haberin kalitesini skorlar (0-100)
    
    Kriterler:
    - Başlık var mı? (+20)
    - Description var mı? (+20)
    - Image var mı? (+20)
    - URL var mı? (+20)
    - Tarih var mı? (+20)
    
    Returns:
        Kalite skoru (0-100)
    """
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


def filter_low_quality(news_list: List[Dict], min_score: int = 60) -> List[Dict]:
    """
    Düşük kaliteli haberleri filtreler
    
    Args:
        news_list: Haber listesi
        min_score: Minimum kalite skoru (default: 60)
    
    Returns:
        Sadece yüksek kaliteli haberler
    """
    filtered = []
    
    for article in news_list:
        score = calculate_quality_score(article)
        
        if score >= min_score:
            filtered.append(article)
            logger.debug(f"✅ Kalite OK ({score}): {article.get('title', '')[:50]}...")
        else:
            logger.debug(f"❌ Düşük kalite ({score}): {article.get('title', '')[:50]}...")
    
    logger.info(f"🎯 Kalite filtresi: {len(news_list)} → {len(filtered)} haber")
    
    return filtered
