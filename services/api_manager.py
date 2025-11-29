import time

# Günlük API limitleri
DAILY_LIMITS = {
    "gnews": 100,
    "currents": 20,
    "newsapi_ai": 7,
    "mediastack": 3,
    "newsdata": 3,  # yedek olarak kullanılacak
}

# Bellekte sayaç tutan state
_api_state = {
    api: {
        "used": 0,
        "reset_at": 0  # epoch time (sıfırsa henüz reset kurulmadı demektir)
    }
    for api in DAILY_LIMITS
}


def _reset_if_needed(api: str):
    """
    Eğer API için reset zamanı geldiyse günlük kullanım sıfırlanır.
    """
    now = time.time()
    reset_at = _api_state[api]["reset_at"]

    # İlk kullanım anında reset süresi kurulmamışsa → 24 saat sonrası olarak ayarla
    if reset_at == 0:
        _api_state[api]["reset_at"] = now + 86400
        return

    # 24 saat dolduysa reset yap
    if now >= reset_at:
        _api_state[api]["used"] = 0
        _api_state[api]["reset_at"] = now + 86400


def can_call(api: str, count: int = 1) -> bool:
    """
    Bu API çağrılabilir mi?
    Günlük limit aşılacaksa False döner.
    """
    if api not in DAILY_LIMITS:
        raise ValueError(f"Bilinmeyen API adı: {api}")

    _reset_if_needed(api)

    used = _api_state[api]["used"]
    limit = DAILY_LIMITS[api]

    return (used + count) <= limit


def register_call(api: str, count: int = 1):
    """
    API çağrısı yaptıktan sonra sayaç artırılır.
    """
    if api not in DAILY_LIMITS:
        raise ValueError(f"Bilinmeyen API adı: {api}")

    _reset_if_needed(api)

    _api_state[api]["used"] += count


def get_usage(api: str) -> dict:
    """
    Debug / izleme amaçlı kullanım verisi döndürür.
    """
    if api not in DAILY_LIMITS:
        raise ValueError(f"Bilinmeyen API adı: {api}")

    _reset_if_needed(api)

    return {
        "api": api,
        "limit": DAILY_LIMITS[api],
        "used": _api_state[api]["used"],
        "remaining": DAILY_LIMITS[api] - _api_state[api]["used"],
        "reset_at": _api_state[api]["reset_at"],
    }


def get_all_usage() -> dict:
    """
    Tüm API'lerin durumunu döndürür. Test/debug için çok faydalı.
    """
    return {api: get_usage(api) for api in DAILY_LIMITS}
