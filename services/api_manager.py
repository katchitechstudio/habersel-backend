import time
import json
import os
from datetime import datetime
from config import Config
import logging

logger = logging.getLogger(__name__)

# ----------------------------------------------------
# API USAGE STATE (Restart sonrası da korunur)
# ----------------------------------------------------

API_STATE_FILE = "api_usage_state.json"

# Config’ten limit ve öncelikler alınır
DAILY_LIMITS = {
    api_name: api_data["daily"]
    for api_name, api_data in Config.API_LIMITS.items()
}

API_PRIORITIES = {
    api_name: api_data["priority"]
    for api_name, api_data in Config.API_LIMITS.items()
}

# Bellek state
_api_state = {}


# ----------------------------------------------------
# STATE INIT
# ----------------------------------------------------

def _init_state():
    """Dosyadan yükle veya sıfırdan başlat."""
    global _api_state

    if os.path.exists(API_STATE_FILE):
        try:
            with open(API_STATE_FILE, "r") as f:
                _api_state = json.load(f)
            logger.info("✅ API state dosyadan yüklendi")
            _cleanup_old_states()
            return
        except Exception as e:
            logger.warning(f"⚠️ API state okunamadı: {e}")

    # Yeni state oluştur
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
    logger.info("🔧 API state sıfırdan oluşturuldu")


def _save_state():
    """State'i dosyaya kaydet."""
    try:
        with open(API_STATE_FILE, "w") as f:
            json.dump(_api_state, f, indent=2)
    except Exception as e:
        logger.error(f"❌ API state kaydedilemedi: {e}")


def _cleanup_old_states():
    """Süresi geçmiş reset zamanlarını yeniler."""
    now = time.time()
    for api in _api_state:
        reset_at = _api_state[api].get("reset_at", 0)
        if reset_at > 0 and now >= reset_at:
            _api_state[api]["used"] = 0
            _api_state[api]["reset_at"] = now + 86400
            _api_state[api]["error_count"] = 0
            logger.info(f"🔄 {api} günlük limit sıfırlandı")

    _save_state()


def _reset_if_needed(api: str):
    """Günlük limit sıfırlama kontrolü."""
    if not _api_state:
        _init_state()

    now = time.time()
    reset_at = _api_state[api]["reset_at"]

    if reset_at == 0:
        _api_state[api]["reset_at"] = now + 86400
        _save_state()
        return

    if now >= reset_at:
        old_used = _api_state[api]["used"]
        _api_state[api]["used"] = 0
        _api_state[api]["reset_at"] = now + 86400
        _api_state[api]["error_count"] = 0
        _save_state()
        logger.info(f"🔄 {api} sıfırlandı (eski: {old_used}/{DAILY_LIMITS[api]})")


# ----------------------------------------------------
# LIMIT CHECKER
# ----------------------------------------------------

def can_call(api: str, count: int = 1) -> bool:
    """API limiti uygun mu?"""
    if api not in DAILY_LIMITS:
        raise ValueError(f"Bilinmeyen API: {api}")

    if not _api_state:
        _init_state()

    _reset_if_needed(api)

    used = _api_state[api]["used"]
    limit = DAILY_LIMITS[api]

    if used + count > limit:
        logger.warning(f"⚠️ {api} limiti doldu! ({used}/{limit})")
        return False

    return True


def register_call(api: str, count: int = 1, success: bool = True):
    """İstek yapıldıktan sonra sayaç güncelle."""
    if api not in DAILY_LIMITS:
        raise ValueError(f"Bilinmeyen API: {api}")

    if not _api_state:
        _init_state()

    _reset_if_needed(api)

    _api_state[api]["used"] += count
    _api_state[api]["last_call"] = time.time()

    if not success:
        _api_state[api]["error_count"] += 1

    _save_state()
    logger.info(f"📊 {api}: {_api_state[api]['used']}/{DAILY_LIMITS[api]}")


# ----------------------------------------------------
# KULLANIM BİLGİSİ
# ----------------------------------------------------

def get_usage(api: str) -> dict:
    """Bir API’nin durumunu döndürür."""
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
        "percentage": round((used / limit) * 100, 1),
        "reset_at": _api_state[api]["reset_at"],
        "last_call": _api_state[api]["last_call"],
        "error_count": _api_state[api]["error_count"],
        "status": "available" if can_call(api) else "limit_reached"
    }


def get_all_usage() -> dict:
    """Tüm API durumları."""
    if not _api_state:
        _init_state()

    result = {}
    for api in sorted(DAILY_LIMITS.keys(), key=lambda x: API_PRIORITIES[x]):
        result[api] = get_usage(api)

    return result


# ----------------------------------------------------
# FALLBACK: Sıradaki uygun API
# ----------------------------------------------------

def get_next_available_api(exclude: list = None) -> str:
    """Öncelik + limit + hata sayısına göre en uygun API."""
    if exclude is None:
        exclude = []

    sorted_apis = sorted(DAILY_LIMITS.keys(), key=lambda x: API_PRIORITIES[x])

    for api in sorted_apis:
        if api in exclude:
            continue

        if can_call(api):
            logger.debug(f"🎯 Kullanılabilir API bulundu: {api}")
            return api

    logger.warning("⚠️ Hiçbir API uygun değil!")
    return None


# ----------------------------------------------------
# GÜNLÜK ÖZET
# ----------------------------------------------------

def get_daily_summary() -> dict:
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


# Initialize on start
_init_state()
