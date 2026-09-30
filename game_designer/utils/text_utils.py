"""Metin temizleme, işleme ve anahtar kelime yardımcıları."""

import html
import re
import unicodedata
from bs4 import BeautifulSoup

STOPWORDS = {
    # Türkçe yaygın dolgu kelimeleri
    "ve", "veya", "ile", "bir", "bu", "şu", "o", "için", "gibi", "kadar", "daha",
    "en", "çok", "az", "ama", "fakat", "ancak", "çünkü", "nasıl", "nedir", "nerede",
    "ne", "kim", "hangisi", "mı", "mi", "mu", "mü", "ise", "ya", "hem", "de", "da",
    "olarak", "tarafından", "üzerine", "göre", "doğru", "karşı", "sonra", "önce",
    # Konuşma / sorgu şablonu dolguları ve sık geçen jenerik kökler
    "oyun", "oyunlar", "oyunları", "oyunların", "oyunlarının", "oyunun", "oyunda", "oyundaki", "oyundan",
    "durum", "durumu", "durumları", "benzeri", "tarzı", "türü", "türleri", "şeklinde",
    "tasarlıyorum", "yapıyorum", "ediyorum", "çalışıyorum", "istiyorum", "yapmak", "etmek",
    "kullanıyorum", "kullandım", "kullanarak", "kullanmak", "kullanılan", "yaparken", "ederken",
    "ayarlamalıyım", "ayarlamak", "ayarlanır", "seçmeliyim", "yapmalıyım", "etmeliyim",
    "tavsiye", "tavsiyesi", "tavsiyeler", "öneri", "önerisi", "öneriler", "fikir", "fikirler",
    "hakkında", "ilgili", "ilişkin", "nelerdir", "örnek", "örneği", "örnekleri", "örnekler",
    # İngilizce yaygın stopwords
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "with",
    "about", "against", "between", "into", "through", "during", "before", "after",
    "above", "below", "from", "up", "down", "is", "are", "was", "were", "be",
    "been", "being", "have", "has", "had", "do", "does", "did", "how", "what",
    "when", "where", "which", "who", "whom", "this", "that", "these", "those",
}


def clean_text(raw_text: str) -> str:
    """Ham metni temizler, HTML etiketlerini ve fazla boşlukları kaldırır.

    Args:
        raw_text: Temizlenecek ham metin.

    Returns:
        Temizlenmiş, normalize edilmiş metin.
    """
    if not raw_text:
        return ""

    # HTML etiketlerini temizle (eğer varsa)
    if "<" in raw_text and ">" in raw_text:
        try:
            soup = BeautifulSoup(raw_text, "html.parser")
            for script_or_style in soup(["script", "style", "nav", "footer", "header", "aside"]):
                script_or_style.extract()
            text = soup.get_text(separator=" ")
        except Exception:
            text = re.sub(r"<[^>]+>", " ", raw_text)
    else:
        text = raw_text

    # HTML entity'lerini çevir (&amp; -> & vb.)
    text = html.unescape(text)

    # Unicode normalizasyonu (NFKC)
    text = unicodedata.normalize("NFKC", text)

    # Satır sonlarını düzenle
    text = re.sub(r"\r\n|\r", "\n", text)
    # 3 veya daha fazla ardışık satır boşluğunu 2'ye indir
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Yatay boşlukları tek boşluğa indir
    text = re.sub(r"[ \t]+", " ", text)

    return text.strip()


def extract_keywords(text: str, max_keywords: int = 10) -> list[str]:
    """Metinden anlamlı anahtar kelimeleri çıkarır (stopwords filtrelenir).

    Args:
        text: İncelenecek metin.
        max_keywords: Döndürülecek maksimum anahtar kelime sayısı.

    Returns:
        Anahtar kelimeler listesi.
    """
    if not text:
        return []

    words = re.findall(r"\b[a-zA-ZçğıöşüÇĞİÖŞÜ0-9_\-]{3,}\b", text.lower())
    filtered = [w for w in words if w not in STOPWORDS and not w.isdigit()]

    # Frekansa göre sırala
    freq: dict[str, int] = {}
    for word in filtered:
        freq[word] = freq.get(word, 0) + 1

    sorted_words = sorted(freq.keys(), key=lambda w: freq[w], reverse=True)
    return sorted_words[:max_keywords]


def lexical_similarity(query: str, document_text: str) -> float:
    """Sorgu ile doküman metni arasındaki kelime bazlı benzerliği hesaplar (0.0 - 1.0).

    Args:
        query: Kullanıcı sorgusu.
        document_text: Doküman metni.

    Returns:
        0.0 ile 1.0 arasında benzerlik skoru.
    """
    query_tokens = set(extract_keywords(query, max_keywords=20))
    if not query_tokens:
        # Fallback: basit kelime bölme
        query_tokens = set(re.findall(r"\b\w{2,}\b", query.lower()))
    if not query_tokens:
        return 0.0

    from game_designer.utils.language_utils import get_english_terms_for_query

    doc_lower = document_text.lower()
    matches = 0
    for token in query_tokens:
        if token in doc_lower:
            matches += 1
        else:
            en_terms = get_english_terms_for_query(token)
            if any(et.lower() in doc_lower or any(w in doc_lower for w in et.lower().split()) for et in en_terms):
                matches += 1

    return matches / len(query_tokens)


def truncate_text(text: str, max_chars: int = 500, suffix: str = "...") -> str:
    """Metni belirtilen karakter sınırında düzgünce kısaltır."""
    if len(text) <= max_chars:
        return text
    return text[: max_chars - len(suffix)].rstrip() + suffix
