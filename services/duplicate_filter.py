from rapidfuzz import fuzz
from datetime import datetime, timedelta
from typing import List, Dict


# ------------------------------------------
# 1) Başlık benzerliği hesaplama (%0 - %100)
# ------------------------------------------
def titles_similar(t1: str, t2: str, threshold: int = 85) -> bool:
    if not t1 or not t2:
        return False
    similarity = fuzz.ratio(t1, t2)
    return similarity >= threshold


# ------------------------------------------
# 2) URL basit domain kontrolü (aynı site mi?)
# ------------------------------------------
def urls_similar(u1: str, u2: str) -> bool:
    if not u1 or not u2:
        return False

    def normalize(url: str) -> str:
        return (
            url.replace("https://", "")
            .replace("http://", "")
            .replace("www.", "")
            .split("?")[0]
            .split("#")[0]
        )

    return normalize(u1) == normalize(u2)


# ------------------------------------------
# 3) Yayın zamanı yakınsa (±15 dakika)
# ------------------------------------------
def dates_close(d1: str, d2: str) -> bool:
    try:
        dt1 = datetime.fromisoformat(d1)
        dt2 = datetime.fromisoformat(d2)
    except:
        return False

    diff = abs((dt1 - dt2).total_seconds())
    return diff <= 900  # 15 dakika


# ------------------------------------------
# 4) TEKİLLEŞTİRME — duplicate haberleri sil
# ------------------------------------------
def remove_duplicates(news_list: List[Dict]) -> List[Dict]:
    """
    Haber listesinde aynı başlık / url / zaman olanları temizler.
    """
    unique = []

    for article in news_list:
        duplicate_found = False

        for existing in unique:
            if (
                titles_similar(article.get("title"), existing.get("title"))
                or urls_similar(article.get("url"), existing.get("url"))
                or dates_close(
                    article.get("published", ""),
                    existing.get("published", "")
                )
            ):
                duplicate_found = True
                break

        if not duplicate_found:
            unique.append(article)

    return unique
