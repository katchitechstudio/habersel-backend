"""
Habersel Backend - Yardımcı Fonksiyonlar
=========================================

Bu modül genel amaçlı yardımcı fonksiyonlar içerir:
- Timezone dönüşümleri
- String işlemleri
- Validation (doğrulama)
- Retry mekanizması
- Haber içerik temizleme (YENİ)
- Diğer utility fonksiyonlar
"""

import re
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from functools import wraps
import pytz
from config import Config

logger = logging.getLogger(__name__)

# ============================================
# 1️⃣ TIMEZONE DÖNÜŞÜM FONKSİYONLARI
# ============================================

def get_local_timezone():
    """Türkiye saat dilimini döndürür"""
    return pytz.timezone(Config.TIMEZONE)


def utc_to_local(utc_time: datetime) -> datetime:
    """
    UTC zamanını Türkiye saatine çevirir
    
    Args:
        utc_time: UTC datetime objesi
    
    Returns:
        Türkiye saatinde datetime
    """
    if utc_time.tzinfo is None:
        utc_time = pytz.utc.localize(utc_time)
    
    local_tz = get_local_timezone()
    return utc_time.astimezone(local_tz)


def local_to_utc(local_time: datetime) -> datetime:
    """
    Türkiye saatini UTC'ye çevirir
    
    Args:
        local_time: Türkiye saatinde datetime
    
    Returns:
        UTC datetime
    """
    local_tz = get_local_timezone()
    
    if local_time.tzinfo is None:
        local_time = local_tz.localize(local_time)
    
    return local_time.astimezone(pytz.utc)


def parse_datetime(date_str: str) -> Optional[datetime]:
    """
    Çeşitli formatlardaki tarih string'ini datetime'a çevirir
    
    Desteklenen formatlar:
    - ISO 8601: "2025-11-30T14:30:00Z"
    - RFC 2822: "Sat, 30 Nov 2025 14:30:00 GMT"
    - Timestamp: "1732976400"
    
    Args:
        date_str: Tarih string'i
    
    Returns:
        datetime objesi veya None
    """
    if not date_str:
        return None
    
    # ISO 8601 format
    try:
        # Z'yi +00:00'a çevir
        normalized = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, AttributeError):
        pass
    
    # Unix timestamp
    try:
        timestamp = float(date_str)
        return datetime.fromtimestamp(timestamp, tz=pytz.utc)
    except (ValueError, TypeError):
        pass
    
    # dateutil ile diğer formatlar (opsiyonel)
    try:
        from dateutil import parser
        return parser.parse(date_str)
    except ImportError:
        logger.warning("dateutil paketi yok, bazı tarih formatları parse edilemeyebilir")
    except Exception:
        pass
    
    logger.warning(f"⚠️ Tarih parse edilemedi: {date_str}")
    return None


def get_time_ago(timestamp: datetime) -> str:
    """
    Verilen zamanın şimdiden ne kadar önce olduğunu hesaplar
    
    Args:
        timestamp: datetime objesi
    
    Returns:
        "5 dakika önce", "3 saat önce", "2 gün önce" formatında string
    """
    now = datetime.now(pytz.utc)
    
    # Timezone kontrolü
    if timestamp.tzinfo is None:
        timestamp = pytz.utc.localize(timestamp)
    
    diff = now - timestamp
    seconds = diff.total_seconds()
    
    if seconds < 0:
        return "gelecekte"
    
    if seconds < 60:
        return "az önce"
    
    if seconds < 3600:  # 1 saat
        minutes = int(seconds / 60)
        return f"{minutes} dakika önce"
    
    if seconds < 86400:  # 1 gün
        hours = int(seconds / 3600)
        return f"{hours} saat önce"
    
    if seconds < 604800:  # 1 hafta
        days = int(seconds / 86400)
        return f"{days} gün önce"
    
    if seconds < 2592000:  # 30 gün
        weeks = int(seconds / 604800)
        return f"{weeks} hafta önce"
    
    # 30 günden eski ise tarih göster
    return format_date(timestamp, format_type="short")


def format_date(dt: datetime, format_type: str = "full") -> str:
    """
    Tarihi okunabilir formatta döndürür
    
    Args:
        dt: datetime objesi
        format_type: "full", "short", "time_only"
    
    Returns:
        Formatlanmış tarih string'i
    """
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    
    # Türkiye saatine çevir
    local_dt = utc_to_local(dt)
    
    if format_type == "full":
        # "30 Kasım 2025, Pazar 14:30"
        return local_dt.strftime("%d %B %Y, %A %H:%M")
    
    elif format_type == "short":
        # "30 Kas 2025"
        return local_dt.strftime("%d %b %Y")
    
    elif format_type == "time_only":
        # "14:30"
        return local_dt.strftime("%H:%M")
    
    else:
        # Default: ISO format
        return local_dt.isoformat()


# ============================================
# 2️⃣ STRING YARDIMCI FONKSİYONLARI
# ============================================

def clean_text(text: str) -> str:
    """
    Metni temizler ve normalize eder
    
    - Extra boşlukları kaldırır
    - Başındaki/sonundaki boşlukları atar
    - Çift boşlukları tek yapar
    - Satır başı/sonu karakterlerini temizler
    
    Args:
        text: Temizlenecek metin
    
    Returns:
        Temizlenmiş metin
    """
    if not text:
        return ""
    
    # Satır başı/sonu karakterlerini kaldır
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    
    # Çoklu boşlukları tek boşluğa indir
    text = " ".join(text.split())
    
    # Başındaki ve sonundaki boşlukları at
    text = text.strip()
    
    return text


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    """
    Metni belirli uzunlukta keser
    
    Args:
        text: Kesilecek metin
        max_length: Maksimum uzunluk
        suffix: Sona eklenecek (varsayılan: "...")
    
    Returns:
        Kısaltılmış metin
    """
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    # Son kelimeyi bölmemek için son boşluğa kadar kes
    truncated = text[:max_length].rsplit(" ", 1)[0]
    return truncated + suffix


def remove_html_tags(text: str) -> str:
    """
    HTML tag'lerini temizler
    
    Args:
        text: HTML içeren metin
    
    Returns:
        Sadece düz metin
    """
    if not text:
        return ""
    
    # HTML tag'lerini kaldır
    clean = re.sub(r'<[^>]+>', '', text)
    
    # HTML entity'leri decode et
    clean = clean.replace("&nbsp;", " ")
    clean = clean.replace("&amp;", "&")
    clean = clean.replace("&lt;", "<")
    clean = clean.replace("&gt;", ">")
    clean = clean.replace("&quot;", '"')
    clean = clean.replace("&#39;", "'")
    
    return clean_text(clean)


def remove_emojis(text: str) -> str:
    """
    Emoji'leri kaldırır
    
    Args:
        text: Emoji içeren metin
    
    Returns:
        Emoji'siz metin
    """
    if not text:
        return ""
    
    # Emoji regex pattern
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"  # emoticons
        "\U0001F300-\U0001F5FF"  # symbols & pictographs
        "\U0001F680-\U0001F6FF"  # transport & map symbols
        "\U0001F1E0-\U0001F1FF"  # flags
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    
    return emoji_pattern.sub('', text)


def sanitize_filename(filename: str) -> str:
    """
    Dosya adını güvenli hale getirir
    
    Args:
        filename: Dosya adı
    
    Returns:
        Güvenli dosya adı
    """
    if not filename:
        return "unnamed"
    
    # Özel karakterleri kaldır
    safe = re.sub(r'[<>:"/\\|?*]', '', filename)
    
    # Boşlukları alt çizgi yap
    safe = safe.replace(" ", "_")
    
    # Türkçe karakterleri düzelt
    turkish_map = {
        'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
        'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'
    }
    
    for turkish, english in turkish_map.items():
        safe = safe.replace(turkish, english)
    
    return safe.lower()


def extract_domain(url: str) -> Optional[str]:
    """
    URL'den domain adını çıkarır
    
    Args:
        url: URL string'i
    
    Returns:
        Domain adı (örn: "example.com")
    """
    if not url:
        return None
    
    # Protocol'ü kaldır
    domain = url.replace("https://", "").replace("http://", "")
    
    # www. kaldır
    domain = domain.replace("www.", "")
    
    # Path'i kaldır
    domain = domain.split("/")[0]
    
    # Port numarasını kaldır
    domain = domain.split(":")[0]
    
    return domain.lower()


# ============================================
# 🆕 HABER İÇERİK TEMİZLEME FONKSİYONLARI
# ============================================

def clean_news_content(content: Optional[str]) -> Optional[str]:
    """
    Haber içeriğini temizler ve düzenler
    
    🧹 Temizleme işlemleri:
    - "Haberin Devamı", "Gözden Kaçmasın" gibi kalıpları siler
    - Twitter embed artıklarını (t.co linkleri, kullanıcı adları) kaldırır
    - Hashtagleri temizler
    - Çift boşlukları düzeltir
    - Paragrafları düzenler
    - Türkçe karakter hatalarını düzeltir
    
    Args:
        content: Ham haber metni
        
    Returns:
        Temizlenmiş ve düzenlenmiş metin
    """
    if not content:
        return None
    
    text = content
    
    # 1️⃣ Gereksiz kalıpları sil
    remove_patterns = [
        r"Haberin Devamı[:\s]*",
        r"Gözden Kaçmasın[:\s]*",
        r"Haberi görüntüle[:\s]*",
        r"İlgili Haber[:\s]*",
        r"Önerilen Haber[:\s]*",
        r"Devamını Oku[:\s]*",
        r"Tıklayınız[:\s]*",
        r"Kaynak\s*:\s*\w+",
        r"Editör\s*:\s*\w+",
        r"https?://t\.co/\w+",  # Twitter kısa linkleri
        r"—\s*@\w+\s+\([^)]+\)",  # Twitter kullanıcı adları (— @user (date))
        r"@\w+",  # Diğer mention'lar
        r"#[\wğüşıöçĞÜŞİÖÇ]+",  # Hashtagler (Türkçe karakterli)
        r"\[.*?\]",  # Köşeli parantez içi metinler
        r"\(Fotoğraf:.*?\)",  # Fotoğraf notları
        r"\(Foto:.*?\)",
        r"İlan\s*\d+",  # İlan numaraları
        r"Reklam\s*\d*",
    ]
    
    for pattern in remove_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    
    # 2️⃣ HTML tag'lerini temizle
    text = remove_html_tags(text)
    
    # 3️⃣ Çift boşlukları tek boşluğa indir
    text = re.sub(r' +', ' ', text)
    
    # 4️⃣ Çoklu satır sonlarını düzenle (3+ boş satır → 2 boş satır)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    
    # 5️⃣ Baş ve son boşlukları temizle
    text = text.strip()
    
    # 6️⃣ Paragrafları düzenle (uzun paragrafları böl)
    paragraphs = text.split('\n\n')
    formatted_paragraphs = []
    
    for para in paragraphs:
        para = para.strip()
        if not para or len(para) < 10:  # Çok kısa satırları atla
            continue
        
        # Çok uzun paragrafları böl (5+ cümle varsa)
        sentences = re.split(r'(?<=[.!?])\s+', para)
        
        if len(sentences) > 5:
            # Her 3-4 cümleyi yeni paragrafa dönüştür
            temp_para = []
            for i, sentence in enumerate(sentences):
                temp_para.append(sentence)
                if (i + 1) % 4 == 0 and i < len(sentences) - 1:
                    formatted_paragraphs.append(' '.join(temp_para))
                    temp_para = []
            if temp_para:
                formatted_paragraphs.append(' '.join(temp_para))
        else:
            formatted_paragraphs.append(para)
    
    # 7️⃣ Paragrafları birleştir
    result = '\n\n'.join(formatted_paragraphs)
    
    # 8️⃣ Türkçe karakter düzeltmeleri (encoding hataları)
    turkish_fixes = {
        'Ä±': 'ı', 'Ä°': 'İ',
        'Åž': 'Ş', 'ÅŸ': 'ş',
        'Ã§': 'ç', 'Ã‡': 'Ç',
        'Ã¶': 'ö', 'Ã–': 'Ö',
        'Ã¼': 'ü', 'Ãœ': 'Ü',
        'ÄŸ': 'ğ', 'Ä': 'Ğ',
    }
    
    for wrong, correct in turkish_fixes.items():
        result = result.replace(wrong, correct)
    
    # 9️⃣ Boş satırları temizle
    lines = result.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    result = '\n\n'.join(lines)
    
    return result if result else None


def clean_news_title(title: Optional[str]) -> Optional[str]:
    """
    Haber başlığını temizler
    
    Args:
        title: Ham başlık
        
    Returns:
        Temizlenmiş başlık
    """
    if not title:
        return None
    
    text = title.strip()
    
    # Gereksiz kalıpları sil
    text = re.sub(r'\[.*?\]', '', text)  # [Özel Haber] gibi etiketler
    text = re.sub(r'\(.*?\)', '', text)  # (Videolu) gibi notlar
    text = re.sub(r'#[\wğüşıöçĞÜŞİÖÇ]+', '', text)  # Hashtagler
    
    # HTML tag'lerini temizle
    text = remove_html_tags(text)
    
    # Çift boşlukları düzelt
    text = re.sub(r'\s+', ' ', text)
    
    # Türkçe karakter düzeltmeleri
    turkish_fixes = {
        'Ä±': 'ı', 'Ä°': 'İ',
        'Åž': 'Ş', 'ÅŸ': 'ş',
        'Ã§': 'ç', 'Ã‡': 'Ç',
        'Ã¶': 'ö', 'Ã–': 'Ö',
        'Ã¼': 'ü', 'Ãœ': 'Ü',
        'ÄŸ': 'ğ', 'Ä': 'Ğ',
    }
    
    for wrong, correct in turkish_fixes.items():
        text = text.replace(wrong, correct)
    
    # Başlık çok uzunsa kısalt (150 karakterden uzun olmamalı)
    if len(text) > 150:
        text = text[:147] + "..."
    
    return text.strip() if text.strip() else None


def format_news_date(date_str: Optional[str]) -> Optional[str]:
    """
    Haber tarihini dd.MM.yyyy formatına çevirir
    
    Args:
        date_str: Ham tarih string (ISO format veya başka)
        
    Returns:
        dd.MM.yyyy formatında tarih (örn: "07.12.2025")
    """
    if not date_str:
        return None
    
    try:
        # ISO format deneme
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%d.%m.%Y')
    except:
        pass
    
    try:
        # Diğer formatlar
        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%d.%m.%Y')
    except:
        pass
    
    # Parse edilemezse orijinali döndür
    return date_str


def detect_and_format_subheadings(content: str) -> str:
    """
    İçerikteki alt başlıkları algılar ve bold formatlar
    
    Algılama kuralları:
    - Tamamen büyük harfli ve 100 karakterden kısa satırlar
    - 15 kelimeden az olan satırlar
    
    Args:
        content: Haber içeriği
        
    Returns:
        Alt başlıkları **bold** formatında işaretlenmiş içerik
    """
    if not content:
        return ""
    
    lines = content.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            formatted_lines.append('')
            continue
        
        # Tamamen büyük harfli ve kısa satırları alt başlık olarak işaretle
        word_count = len(line.split())
        is_all_caps = line.isupper()
        is_short = len(line) < 100 and word_count < 15
        
        if is_all_caps and is_short and word_count > 2:
            # Title case yap ve bold işaretle
            formatted_lines.append(f"**{line.title()}**")
        else:
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)


def remove_duplicate_paragraphs(text: str) -> str:
    """
    Tekrar eden paragrafları/cümleleri kaldırır
    
    Args:
        text: Haber metni
        
    Returns:
        Tekrarları kaldırılmış metin
    """
    if not text:
        return ""
    
    paragraphs = text.split('\n\n')
    seen = set()
    unique_paragraphs = []
    
    for para in paragraphs:
        para_clean = para.strip().lower()
        if para_clean and para_clean not in seen and len(para_clean) > 20:
            seen.add(para_clean)
            unique_paragraphs.append(para.strip())
    
    return '\n\n'.join(unique_paragraphs)


def full_clean_news_pipeline(
    title: str,
    content: Optional[str],
    description: Optional[str] = None,
    date: Optional[str] = None
) -> dict:
    """
    🎯 TAM TEMİZLEME PİPELINE - Tüm işlemleri birleştirir
    
    Bu fonksiyonu scraping sırasında kullan!
    
    Args:
        title: Ham başlık
        content: Ham tam içerik (full_content)
        description: Ham özet/açıklama
        date: Ham tarih
        
    Returns:
        Temizlenmiş veri dict'i:
        {
            'title': 'Temiz başlık',
            'content': 'Temiz tam içerik',
            'description': 'Temiz özet',
            'date': '07.12.2025'
        }
    """
    cleaned_title = clean_news_title(title)
    
    # İçeriği tamamen temizle
    if content:
        cleaned_content = clean_news_content(content)
        if cleaned_content:
            cleaned_content = remove_duplicate_paragraphs(cleaned_content)
            cleaned_content = detect_and_format_subheadings(cleaned_content)
    else:
        cleaned_content = None
    
    # Description'ı temizle
    if description:
        cleaned_desc = clean_news_content(description)
        # Description çok uzunsa kısalt (500 karakter)
        if cleaned_desc and len(cleaned_desc) > 500:
            cleaned_desc = cleaned_desc[:497] + "..."
    else:
        cleaned_desc = None
    
    # Tarihi formatla
    formatted_date = format_news_date(date)
    
    return {
        'title': cleaned_title,
        'content': cleaned_content,
        'description': cleaned_desc,
        'date': formatted_date
    }


# ============================================
# 3️⃣ VALIDATION (DOĞRULAMA) FONKSİYONLARI
# ============================================

def is_valid_url(url: str) -> bool:
    """
    URL formatının geçerli olup olmadığını kontrol eder
    
    Args:
        url: Kontrol edilecek URL
    
    Returns:
        Geçerli ise True
    """
    if not url or not isinstance(url, str):
        return False
    
    # Basit URL regex
    url_pattern = re.compile(
        r'^https?://'  # http:// veya https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain
        r'localhost|'  # localhost
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # IP
        r'(?::\d+)?'  # port (opsiyonel)
        r'(?:/?|[/?]\S+)$',  # path
        re.IGNORECASE
    )
    
    return bool(url_pattern.match(url))


def is_valid_email(email: str) -> bool:
    """
    Email formatının geçerli olup olmadığını kontrol eder
    
    Args:
        email: Kontrol edilecek email
    
    Returns:
        Geçerli ise True
    """
    if not email or not isinstance(email, str):
        return False
    
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    return bool(email_pattern.match(email))


def is_valid_article(article: dict) -> bool:
    """
    Haber verisinin geçerli olup olmadığını kontrol eder
    
    Gerekli alanlar:
    - title (boş olmamalı)
    - url (geçerli URL formatında)
    
    Args:
        article: Haber dict'i
    
    Returns:
        Geçerli ise True
    """
    if not article or not isinstance(article, dict):
        return False
    
    # Title kontrolü
    title = article.get("title", "").strip()
    if not title or len(title) < 5:
        logger.debug("⚠️ Geçersiz haber: Başlık yok veya çok kısa")
        return False
    
    # URL kontrolü
    url = article.get("url", "").strip()
    if not is_valid_url(url):
        logger.debug("⚠️ Geçersiz haber: URL formatı hatalı")
        return False
    
    return True


def sanitize_url(url: str) -> str:
    """
    URL'i düzeltir ve normalize eder
    
    - http → https yapar
    - www. ekler (yoksa)
    - Trailing slash ekler
    
    Args:
        url: Düzeltilecek URL
    
    Returns:
        Düzeltilmiş URL
    """
    if not url:
        return ""
    
    url = url.strip()
    
    # http → https
    if url.startswith("http://"):
        url = url.replace("http://", "https://", 1)
    
    # https:// yoksa ekle
    if not url.startswith("https://"):
        url = "https://" + url
    
    return url


def validate_category(category: str) -> bool:
    """
    Kategori adının geçerli olup olmadığını kontrol eder
    
    Args:
        category: Kategori adı
    
    Returns:
        Geçerli ise True
    """
    if not category:
        return False
    
    return category.lower() in [c.lower() for c in Config.NEWS_CATEGORIES]


# ============================================
# 4️⃣ RETRY DECORATOR (TEKRAR DENEME)
# ============================================

def retry(
    max_attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
    """
    Fonksiyonu hata durumunda otomatik tekrar dener
    
    Args:
        max_attempts: Maksimum deneme sayısı
        delay: İlk bekleme süresi (saniye)
        backoff: Her denemede bekleme süresini çarpan
        exceptions: Yakalanacak exception türleri
    
    Usage:
        @retry(max_attempts=3, delay=2)
        def fetch_api():
            return requests.get("https://api.example.com")
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            attempt = 0
            current_delay = delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    attempt += 1
                    
                    if attempt >= max_attempts:
                        logger.error(
                            f"❌ {func.__name__} başarısız oldu "
                            f"({max_attempts} deneme sonrası): {e}"
                        )
                        raise
                    
                    logger.warning(
                        f"⚠️ {func.__name__} başarısız (deneme {attempt}/{max_attempts}), "
                        f"{current_delay:.1f}s bekleniyor... Hata: {e}"
                    )
                    
                    time.sleep(current_delay)
                    current_delay *= backoff
            
        return wrapper
    return decorator


# ============================================
# 5️⃣ DİĞER YARDIMCI FONKSİYONLAR
# ============================================

def safe_dict_get(data: dict, *keys, default=None):
    """
    İç içe dict'ten güvenli şekilde veri alır
    
    Args:
        data: Ana dict
        keys: İç içe key'ler
        default: Bulunamazsa döndürülecek değer
    
    Returns:
        Bulunan değer veya default
    
    Example:
        data = {"user": {"profile": {"name": "Ali"}}}
        name = safe_dict_get(data, "user", "profile", "name")
        # "Ali"
    """
    current = data
    
    for key in keys:
        if isinstance(current, dict):
            current = current.get(key)
            if current is None:
                return default
        else:
            return default
    
    return current if current is not None else default


def chunk_list(lst: list, chunk_size: int) -> list:
    """
    Listeyi belirli boyutta parçalara böler
    
    Args:
        lst: Bölünecek liste
        chunk_size: Parça boyutu
    
    Returns:
        Parçalara bölünmüş liste
    
    Example:
        chunk_list([1,2,3,4,5], 2)
        # [[1,2], [3,4], [5]]
    """
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def generate_unique_id() -> str:
    """
    Benzersiz ID üretir (timestamp bazlı)
    
    Returns:
        Unique ID string'i
    """
    import uuid
    return str(uuid.uuid4())


def bytes_to_human_readable(bytes_size: int) -> str:
    """
    Byte'ı okunabilir formata çevirir
    
    Args:
        bytes_size: Byte cinsinden boyut
    
    Returns:
        "1.5 MB", "250 KB" formatında string
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def mask_sensitive_data(text: str, mask_char: str = "*") -> str:
    """
    Hassas veriyi maskeler (API key, şifre vb.)
    
    Args:
        text: Maskelenecek metin
        mask_char: Maskeleme karakteri
    
    Returns:
        İlk 4 ve son 4 karakter hariç maskeli metin
    
    Example:
        mask_sensitive_data("sk_1234567890abcdef")
        # "sk_1***********cdef"
    """
    if not text or len(text) <= 8:
        return mask_char * len(text)
    
    visible_chars = 4
    masked_section = mask_char * (len(text) - 2 * visible_chars)
    
    return text[:visible_chars] + masked_section + text[-visible_chars:]


def calculate_percentage(part: float, total: float) -> float:
    """
    Yüzde hesaplar
    
    Args:
        part: Kısım
        total: Toplam
    
    Returns:
        Yüzde değeri (0-100)
    """
    if total == 0:
        return 0.0
    
    return round((part / total) * 100, 2)
