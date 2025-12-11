import re
import time
import logging
from datetime import datetime, timedelta
from typing import Optional, Callable, Any
from functools import wraps
import pytz
from config import Config

logger = logging.getLogger(__name__)


def get_local_timezone():
    return pytz.timezone(Config.TIMEZONE)


def utc_to_local(utc_time: datetime) -> datetime:
    if utc_time.tzinfo is None:
        utc_time = pytz.utc.localize(utc_time)
    
    local_tz = get_local_timezone()
    return utc_time.astimezone(local_tz)


def local_to_utc(local_time: datetime) -> datetime:
    local_tz = get_local_timezone()
    
    if local_time.tzinfo is None:
        local_time = local_tz.localize(local_time)
    
    return local_time.astimezone(pytz.utc)


def parse_datetime(date_str: str) -> Optional[datetime]:
    if not date_str:
        return None
    
    try:
        normalized = date_str.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except (ValueError, AttributeError):
        pass
    
    try:
        timestamp = float(date_str)
        return datetime.fromtimestamp(timestamp, tz=pytz.utc)
    except (ValueError, TypeError):
        pass
    
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
    now = datetime.now(pytz.utc)
    
    if timestamp.tzinfo is None:
        timestamp = pytz.utc.localize(timestamp)
    
    diff = now - timestamp
    seconds = diff.total_seconds()
    
    if seconds < 0:
        return "gelecekte"
    
    if seconds < 60:
        return "az önce"
    
    if seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} dakika önce"
    
    if seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} saat önce"
    
    if seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} gün önce"
    
    if seconds < 2592000:
        weeks = int(seconds / 604800)
        return f"{weeks} hafta önce"
    
    return format_date(timestamp, format_type="short")


def format_date(dt: datetime, format_type: str = "full") -> str:
    if dt.tzinfo is None:
        dt = pytz.utc.localize(dt)
    
    local_dt = utc_to_local(dt)
    
    if format_type == "full":
        return local_dt.strftime("%d %B %Y, %A %H:%M")
    
    elif format_type == "short":
        return local_dt.strftime("%d %b %Y")
    
    elif format_type == "time_only":
        return local_dt.strftime("%H:%M")
    
    else:
        return local_dt.isoformat()


def clean_text(text: str) -> str:
    if not text:
        return ""
    
    text = text.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    text = " ".join(text.split())
    text = text.strip()
    
    return text


def truncate_text(text: str, max_length: int = 100, suffix: str = "...") -> str:
    if not text:
        return ""
    
    if len(text) <= max_length:
        return text
    
    truncated = text[:max_length].rsplit(" ", 1)[0]
    return truncated + suffix


def remove_html_tags(text: str) -> str:
    if not text:
        return ""
    
    clean = re.sub(r'<[^>]+>', '', text)
    
    clean = clean.replace("&nbsp;", " ")
    clean = clean.replace("&amp;", "&")
    clean = clean.replace("&lt;", "<")
    clean = clean.replace("&gt;", ">")
    clean = clean.replace("&quot;", '"')
    clean = clean.replace("&#39;", "'")
    
    return clean_text(clean)


def remove_emojis(text: str) -> str:
    if not text:
        return ""
    
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "]+",
        flags=re.UNICODE
    )
    
    return emoji_pattern.sub('', text)


def sanitize_filename(filename: str) -> str:
    if not filename:
        return "unnamed"
    
    safe = re.sub(r'[<>:"/\\|?*]', '', filename)
    safe = safe.replace(" ", "_")
    
    turkish_map = {
        'ç': 'c', 'ğ': 'g', 'ı': 'i', 'ö': 'o', 'ş': 's', 'ü': 'u',
        'Ç': 'C', 'Ğ': 'G', 'İ': 'I', 'Ö': 'O', 'Ş': 'S', 'Ü': 'U'
    }
    
    for turkish, english in turkish_map.items():
        safe = safe.replace(turkish, english)
    
    return safe.lower()


def extract_domain(url: str) -> Optional[str]:
    if not url:
        return None
    
    domain = url.replace("https://", "").replace("http://", "")
    domain = domain.replace("www.", "")
    domain = domain.split("/")[0]
    domain = domain.split(":")[0]
    
    return domain.lower()


def fix_all_caps_text(text: str) -> str:
    if not text:
        return ""
    
    lines = text.split('\n')
    fixed_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            fixed_lines.append('')
            continue
        
        if line.isupper():
            abbreviations = re.findall(r'\b[A-ZĞÜŞÖÇI]{2,5}\b', line)
            fixed = line.title()
            
            for abbr in abbreviations:
                known_abbrs = ['NATO', 'AB', 'TRT', 'BBC', 'CNN', 'AKP', 'CHP', 'MHP', 
                              'İYİ', 'HDP', 'PKK', 'YPG', 'IŞİD', 'DEAŞ', 'ABD', 'AB',
                              'TBMM', 'AİHM', 'UEFA', 'FIFA', 'NBA', 'NFL']
                
                if abbr in known_abbrs:
                    fixed = fixed.replace(abbr.title(), abbr)
            
            fixed_lines.append(fixed)
        else:
            fixed_lines.append(line)
    
    return '\n'.join(fixed_lines)


def remove_clickbait_phrases(text: str) -> str:
    if not text:
        return ""
    
    clickbait_patterns = [
        r'TIKLAYIN[!\s]*',
        r'ŞOKA UĞRAYACAKSINIZ[!\s]*',
        r'İNANILMAZ[!\s]*',
        r'MUTLAKA İZLEYİN[!\s]*',
        r'SOSYAL MEDYAYI SALLADI[!\s]*',
        r'PAYLAŞIM REKORU KIRDI[!\s]*',
        r'VİRAL OLDU[!\s]*',
        r'ORTALIK KARIŞTI[!\s]*',
        r'BU HABER BOMBA GİBİ[!\s]*',
        r'SIR DEŞİFRE OLDU[!\s]*',
        r'FLAŞ[!\s]*',
        r'SON DAKİKA[!\s]*(?!:)',
        r'ACİL[!\s]*',
    ]
    
    for pattern in clickbait_patterns:
        text = re.sub(pattern, '', text, flags=re.IGNORECASE)
    
    return text


def normalize_whitespace(text: str) -> str:
    if not text:
        return ""
    
    text = text.replace('\t', ' ')
    text = re.sub(r' +', ' ', text)
    
    lines = text.split('\n')
    lines = [line.strip() for line in lines]
    
    text = '\n'.join(lines)
    text = re.sub(r'\n{3,}', '\n\n', text)
    
    return text.strip()


def fix_punctuation_spacing(text: str) -> str:
    if not text:
        return ""
    
    text = re.sub(r'\s+([.,!?;:])', r'\1', text)
    text = re.sub(r'([.,!?;:])([A-Za-zğüşıöçĞÜŞİÖÇ])', r'\1 \2', text)
    text = re.sub(r'\s+([)\]])', r'\1', text)
    text = re.sub(r'([([])\s+', r'\1', text)
    
    return text


def remove_metadata_lines(text: str) -> str:
    if not text:
        return ""
    
    metadata_patterns = [
        r'^Yazar\s*[:=]\s*.*$',
        r'^Editör\s*[:=]\s*.*$',
        r'^Editor\s*[:=]\s*.*$',
        r'^Kaynak\s*[:=]\s*.*$',
        r'^Source\s*[:=]\s*.*$',
        r'^Foto\s*[:=]\s*.*$',
        r'^Photo\s*[:=]\s*.*$',
        r'^Fotoğraf\s*[:=]\s*.*$',
        r'^Görsel\s*[:=]\s*.*$',
        r'^Tarih\s*[:=]\s*.*$',
        r'^Date\s*[:=]\s*.*$',
        r'^Güncelleme\s*[:=]\s*.*$',
        r'^Update\s*[:=]\s*.*$',
    ]
    
    lines = text.split('\n')
    cleaned_lines = []
    
    for line in lines:
        is_metadata = False
        for pattern in metadata_patterns:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                is_metadata = True
                break
        
        if not is_metadata:
            cleaned_lines.append(line)
    
    return '\n'.join(cleaned_lines)


def remove_social_media_artifacts(text: str) -> str:
    if not text:
        return ""
    
    text = re.sub(r'https?://t\.co/\w+', '', text)
    text = re.sub(r'https?://(?:www\.)?instagram\.com/\S+', '', text)
    text = re.sub(r'https?://(?:www\.)?facebook\.com/\S+', '', text)
    text = re.sub(r'—\s*@\w+\s*\([^)]+\)', '', text)
    text = re.sub(r'@\w+', '', text)
    text = re.sub(r'#[\wğüşıöçĞÜŞİÖÇ]+', '', text)
    text = re.sub(r'Bu içerik \w+ alınmıştır\.?', '', text, flags=re.IGNORECASE)
    
    return text


def enhanced_clean_pipeline(text: str) -> str:
    if not text:
        return ""
    
    text = remove_social_media_artifacts(text)
    text = remove_metadata_lines(text)
    text = remove_clickbait_phrases(text)
    text = fix_all_caps_text(text)
    text = normalize_whitespace(text)
    text = fix_punctuation_spacing(text)
    
    return text


def clean_news_content(content: Optional[str]) -> Optional[str]:
    if not content:
        return None
    
    text = content
    
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
        r"https?://t\.co/\w+",
        r"—\s*@\w+\s+\([^)]+\)",
        r"@\w+",
        r"#[\wğüşıöçĞÜŞİÖÇ]+",
        r"\[.*?\]",
        r"\(Fotoğraf:.*?\)",
        r"\(Foto:.*?\)",
        r"İlan\s*\d+",
        r"Reklam\s*\d*",
    ]
    
    for pattern in remove_patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    
    text = remove_html_tags(text)
    text = re.sub(r' +', ' ', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    text = text.strip()
    
    paragraphs = text.split('\n\n')
    formatted_paragraphs = []
    
    for para in paragraphs:
        para = para.strip()
        if not para or len(para) < 10:
            continue
        
        sentences = re.split(r'(?<=[.!?])\s+', para)
        
        if len(sentences) > 5:
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
    
    result = '\n\n'.join(formatted_paragraphs)
    
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
    
    lines = result.split('\n')
    lines = [line.strip() for line in lines if line.strip()]
    result = '\n\n'.join(lines)
    
    return result if result else None


def clean_news_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    
    text = title.strip()
    
    text = re.sub(r'\[.*?\]', '', text)
    text = re.sub(r'\(.*?\)', '', text)
    text = re.sub(r'#[\wğüşıöçĞÜŞİÖÇ]+', '', text)
    
    text = remove_html_tags(text)
    text = re.sub(r'\s+', ' ', text)
    
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
    
    if len(text) > 150:
        text = text[:147] + "..."
    
    return text.strip() if text.strip() else None


def format_news_date(date_str: Optional[str]) -> Optional[str]:
    if not date_str:
        return None
    
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%d.%m.%Y')
    except:
        pass
    
    try:
        dt = datetime.strptime(date_str, '%Y-%m-%d %H:%M:%S')
        return dt.strftime('%d.%m.%Y')
    except:
        pass
    
    return date_str


def detect_and_format_subheadings(content: str) -> str:
    if not content:
        return ""
    
    lines = content.split('\n')
    formatted_lines = []
    
    for line in lines:
        line = line.strip()
        if not line:
            formatted_lines.append('')
            continue
        
        word_count = len(line.split())
        is_all_caps = line.isupper()
        is_short = len(line) < 100 and word_count < 15
        
        if is_all_caps and is_short and word_count > 2:
            formatted_lines.append(f"**{line.title()}**")
        else:
            formatted_lines.append(line)
    
    return '\n'.join(formatted_lines)


def remove_duplicate_paragraphs(text: str) -> str:
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
    
    cleaned_title = clean_news_title(title)
    
    if content:
        cleaned_content = clean_news_content(content)
        
        if cleaned_content:
            cleaned_content = enhanced_clean_pipeline(cleaned_content)
            cleaned_content = remove_duplicate_paragraphs(cleaned_content)
            cleaned_content = detect_and_format_subheadings(cleaned_content)
    else:
        cleaned_content = None
    
    if description:
        cleaned_desc = clean_news_content(description)
        if cleaned_desc and len(cleaned_desc) > 500:
            cleaned_desc = cleaned_desc[:497] + "..."
    else:
        cleaned_desc = None
    
    formatted_date = format_news_date(date)
    
    return {
        'title': cleaned_title,
        'content': cleaned_content,
        'description': cleaned_desc,
        'date': formatted_date
    }


def is_valid_url(url: str) -> bool:
    if not url or not isinstance(url, str):
        return False
    
    url_pattern = re.compile(
        r'^https?://'
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'
        r'localhost|'
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'
        r'(?::\d+)?'
        r'(?:/?|[/?]\S+)$',
        re.IGNORECASE
    )
    
    return bool(url_pattern.match(url))


def is_valid_email(email: str) -> bool:
    if not email or not isinstance(email, str):
        return False
    
    email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    return bool(email_pattern.match(email))


def is_valid_article(article: dict) -> bool:
    if not article or not isinstance(article, dict):
        return False
    
    title = article.get("title", "").strip()
    if not title or len(title) < 5:
        logger.debug("⚠️ Geçersiz haber: Başlık yok veya çok kısa")
        return False
    
    url = article.get("url", "").strip()
    if not is_valid_url(url):
        logger.debug("⚠️ Geçersiz haber: URL formatı hatalı")
        return False
    
    return True


def sanitize_url(url: str) -> str:
    if not url:
        return ""
    
    url = url.strip()
    
    if url.startswith("http://"):
        url = url.replace("http://", "https://", 1)
    
    if not url.startswith("https://"):
        url = "https://" + url
    
    return url


def validate_category(category: str) -> bool:
    if not category:
        return False
    
    return category.lower() in [c.lower() for c in Config.NEWS_CATEGORIES]


def retry(
    max_attempts: int = 3,
    delay: float = 2.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
):
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


def safe_dict_get(data: dict, *keys, default=None):
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
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def generate_unique_id() -> str:
    import uuid
    return str(uuid.uuid4())


def bytes_to_human_readable(bytes_size: int) -> str:
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if bytes_size < 1024.0:
            return f"{bytes_size:.1f} {unit}"
        bytes_size /= 1024.0
    return f"{bytes_size:.1f} PB"


def mask_sensitive_data(text: str, mask_char: str = "*") -> str:
    if not text or len(text) <= 8:
        return mask_char * len(text)
    
    visible_chars = 4
    masked_section = mask_char * (len(text) - 2 * visible_chars)
    
    return text[:visible_chars] + masked_section + text[-visible_chars:]


def calculate_percentage(part: float, total: float) -> float:
    if total == 0:
        return 0.0
    
    return round((part / total) * 100, 2)




















