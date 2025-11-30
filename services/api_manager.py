import time
import json
import os
from datetime import datetime, timedelta
from config import Config
import logging

logger = logging.getLogger(__name__)

# -----------------------
# API Kullanım Takibi
# -----------------------
# Not: Bu veriler bellekte tutulur, ancak dosyaya da kaydedilir
# Böylece Render restart olsa bile veri kaybolmaz

API_STATE_FILE = "api_usage_state.json"

# Her API için limit bilgileri (config'den alınır)
DAILY_LIMITS = {
    api_name: api_data["daily"]
    for api_name, api_data in Config.API_LIMITS.items()
}

# Öncelik sıralaması (config'den)
API_PRIORITIES = {
    api_name: api_data["priority"]
    for api_name, api_data in Config.API_LIMITS.items()
}

# Bellekte tutulan kullanım state'i
_api_state = {}

def _init_state():
    """
    State'i başlat veya dosyadan yükle
    """
    global _api_state
    
    # Dosyadan yükle (varsa)
    if os.path.exists(API_STATE_FILE):
        try:
            with open(API_STATE_FILE, "r") as f:
                _api_state = json.load(f)
            logger.info("✅ API state dosyadan yüklendi")
            
            # Eski günlere ait state'leri temizle
            _cleanup_old_states()
            return
        except Exception as e:
            logger.warning(f"⚠️  API state dosyası okunamadı: {e}")
    
    # Dosya yoksa veya hatalıysa sıfırdan oluştur
    _api_state = {
        api: {
            "used": 0,
            "reset_at": 0,
            "last_call": 0,
            "error_count": 0
        }
        for api in DAILY_LIMITS
    }
    _save_state()
    logger.info("✅ API state sıfırdan oluşturuldu")

def _save_state():
    """
    State'i dosyaya kaydet (Render restart'ta korunur)
    """
    try:
        with open(API_STATE_FILE, "w") as f:
            json.dump(_api_state, f, indent=2)
    except Exception as e:
        logger.error(f"❌ API state kaydedilemedi: {e}")

def _cleanup_old_states():
    """
    Eski günlere ait state'leri temizle
    """
    now = time.time()
    for api in _api_state:
        reset_at = _api_state[api].get("reset_at", 0)
        if reset_at > 0 and now >= reset_at:
            _api_state[api]["used"] = 0
            _api_state[api]["reset_at"] = now + 86400
            logger.info(f"🔄 {api} limiti sıfırlandı")
    _save_state()

def _reset_if_needed(api: str):
    """
    Eğer API için reset zamanı geldiyse günlük kullanım sıfırlanır.
    
    Args:
        api: API adı (gnews, currents, vb.)
    """
    if not _api_state:
        _init_state()
    
    now = time.time()
    reset_at = _api_state[api]["reset_at"]
    
    # İlk kullanım → reset zamanını ayarla
    if reset_at == 0:
        _api_state[api]["reset_at"] = now + 86400  # 24 saat sonra
        _save_state()
        logger.debug(f"⏰ {api} için reset zamanı ayarlandı")
        return
    
    # 24 saat dolduysa reset yap
    if now >= reset_at:
        old_used = _api_state[api]["used"]
        _api_state[api]["used"] = 0
        _api_state[api]["reset_at"] = now + 86400
        _api_state[api]["error_count"] = 0  # Hata sayacını da sıfırla
        _save_state()
        
        logger.info(f"🔄 {api} günlük limiti sıfırlandı (eski: {old_used}/{DAILY_LIMITS[api]})")

def can_call(api: str, count: int = 1) -> bool:
    """
    Bu API çağrılabilir mi kontrol eder.
    
    Args:
        api: API adı
        count: Kaç istek yapılacak
    
    Returns:
        bool: Limit müsaitse True, doluysa False
    """
    if api not in DAILY_LIMITS:
        logger.error(f"❌ Bilinmeyen API adı: {api}")
        raise ValueError(f"Bilinmeyen API adı: {api}")
    
    if not _api_state:
        _init_state()
    
    _reset_if_needed(api)
    
    used = _api_state[api]["used"]
    limit = DAILY_LIMITS[api]
    available = limit - used
    
    result = (used + count) <= limit
    
    if not result:
        logger.warning(f"⚠️  {api} limiti doldu! ({used}/{limit})")
    else:
        logger.debug(f"✅ {api} kullanılabilir ({used + count}/{limit})")
    
    return result

def register_call(api: str, count: int = 1, success: bool = True):
    """
    API çağrısı yapıldıktan sonra sayaç artırılır.
    
    Args:
        api: API adı
        count: Kaç istek yapıldı
        success: İstek başarılı mı
    """
    if api not in DAILY_LIMITS:
        logger.error(f"❌ Bilinmeyen API adı: {api}")
        raise ValueError(f"Bilinmeyen API adı: {api}")
    
    if not _api_state:
        _init_state()
    
    _reset_if_needed(api)
    
    # Kullanım sayacını artır
    _api_state[api]["used"] += count
    _api_state[api]["last_call"] = time.time()
    
    # Hata sayacı
    if not success:
        _api_state[api]["error_count"] = _api_state[api].get("error_count", 0) + 1
    
    _save_state()
    
    used = _api_state[api]["used"]
    limit = DAILY_LIMITS[api]
    
    logger.info(f"📊 {api}: {used}/{limit} kullanıldı")

def get_usage(api: str) -> dict:
    """
    Belirli bir API'nin kullanım bilgisini döndürür.
    
    Args:
        api: API adı
    
    Returns:
        dict: Kullanım istatistikleri
    """
    if api not in DAILY_LIMITS:
        raise ValueError(f"Bilinmeyen API adı: {api}")
    
    if not _api_state:
        _init_state()
    
    _reset_if_needed(api)
    
    used = _api_state[api]["used"]
    limit = DAILY_LIMITS[api]
    
    return {
        "api": api,
        "priority": API_PRIORITIES.get(api, 99),
        "limit": limit,
        "used": used,
        "remaining": limit - used,
        "percentage": round((used / limit) * 100, 1) if limit > 0 else 0,
        "reset_at": _api_state[api]["reset_at"],
        "reset_in_seconds": max(0, int(_api_state[api]["reset_at"] - time.time())),
        "last_call": _api_state[api].get("last_call", 0),
        "error_count": _api_state[api].get("error_count", 0),
        "status": "available" if can_call(api) else "limit_reached"
    }

def get_all_usage() -> dict:
    """
    Tüm API'lerin kullanım durumunu döndürür.
    
    Returns:
        dict: Tüm API'lerin istatistikleri
    """
    if not _api_state:
        _init_state()
    
    result = {}
    for api in sorted(DAILY_LIMITS.keys(), key=lambda x: API_PRIORITIES.get(x, 99)):
        result[api] = get_usage(api)
    
    return result

def get_next_available_api(exclude: list = None) -> str:
    """
    Kullanılabilir bir sonraki API'yi öncelik sırasına göre döndürür.
    
    Args:
        exclude: Hariç tutulacak API'ler (başarısız olanlar)
    
    Returns:
        str: API adı veya None (hiçbiri kullanılamıyorsa)
    """
    if exclude is None:
        exclude = []
    
    # Öncelik sırasına göre sırala (1 = en yüksek öncelik)
    sorted_apis = sorted(
        DAILY_LIMITS.keys(),
        key=lambda x: API_PRIORITIES.get(x, 99)
    )
    
    for api in sorted_apis:
        if api in exclude:
            continue
        
        if can_call(api):
            logger.debug(f"🎯 Sonraki kullanılabilir API: {api}")
            return api
    
    logger.warning("⚠️  Hiçbir API kullanılamıyor!")
    return None

def reset_all():
    """
    Tüm API limitlerini zorla sıfırla (sadece test için)
    """
    global _api_state
    
    now = time.time()
    for api in _api_state:
        _api_state[api]["used"] = 0
        _api_state[api]["reset_at"] = now + 86400
        _api_state[api]["error_count"] = 0
    
    _save_state()
    logger.warning("⚠️  TÜM API LİMİTLERİ SIFIRLANDI (TEST MOD)")

def get_daily_summary() -> dict:
    """
    Günlük özet istatistik
    
    Returns:
        dict: Günlük toplam kullanım
    """
    if not _api_state:
        _init_state()
    
    total_used = sum(state["used"] for state in _api_state.values())
    total_limit = sum(DAILY_LIMITS.values())
    
    return {
        "total_requests_made": total_used,
        "total_daily_limit": total_limit,
        "remaining_requests": total_limit - total_used,
        "usage_percentage": round((total_used / total_limit) * 100, 1),
        "apis_exhausted": [
            api for api in DAILY_LIMITS
            if _api_state[api]["used"] >= DAILY_LIMITS[api]
        ]
    }

# Uygulama başlarken state'i yükle
_init_state()
