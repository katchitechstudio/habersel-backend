import re


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


def test_cleaning_functions():
    print("🧪 TEMİZLEME FONKSİYONLARI TEST EDİLİYOR...\n")
    
    test1 = "FOSİL KARABORSASI VAR EMEKLI PROFESÖR AÇIKLADI"
    print(f"Test 1 - Büyük Harf Düzeltme:")
    print(f"Önce:  {test1}")
    print(f"Sonra: {fix_all_caps_text(test1)}\n")
    
    test2 = "ŞOKA UĞRAYACAKSINIZ! Bu haber sosyal medyayı salladı TIKLAYIN!"
    print(f"Test 2 - Clickbait Temizleme:")
    print(f"Önce:  {test2}")
    print(f"Sonra: {remove_clickbait_phrases(test2)}\n")
    
    test3 = "Harika bir gelişme #teknoloji @johnDoe https://t.co/abc123 — @user (01.12.2025)"
    print(f"Test 3 - Sosyal Medya Temizleme:")
    print(f"Önce:  {test3}")
    print(f"Sonra: {remove_social_media_artifacts(test3)}\n")
    
    test4 = "Merhaba , nasılsın ?Ben iyiyim,teşekkürler !"
    print(f"Test 4 - Noktalama Düzeltme:")
    print(f"Önce:  {test4}")
    print(f"Sonra: {fix_punctuation_spacing(test4)}\n")
    
    test5 = """FOSİL KARABORSASI VAR EMEKLI PROFESÖR AÇIKLADI
    
    ŞOKA UĞRAYACAKSINIZ! Bu haber    çok önemli  ,  dikkat  !
    
    Kaynak: Reuters
    Editör: Ahmet Yılmaz
    
    https://t.co/abc123 @user #haber
    """
    print(f"Test 5 - Tam Pipeline:")
    print(f"Önce:\n{test5}")
    print(f"\nSonra:\n{enhanced_clean_pipeline(test5)}\n")


if __name__ == "__main__":
    test_cleaning_functions()
