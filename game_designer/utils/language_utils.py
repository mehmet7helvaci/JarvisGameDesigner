"""Dil tespiti ve oyun tasarımı terim sözlüğü yardımcıları."""

import re

# Oyun tasarımı terimleri sözlüğü (Türkçe -> İngilizce karşılıkları)
GAME_DESIGN_TERM_MAP: dict[str, list[str]] = {
    "döngü": ["core loop", "gameplay loop", "compulsion loop"],
    "oyun döngüsü": ["core gameplay loop", "game loop design"],
    "mekanik": ["game mechanics", "mechanics design", "player actions"],
    "mekanikleri": ["game mechanics", "systems mechanics"],
    "bölüm tasarımı": ["level design", "environment design", "level pacing"],
    "seviye tasarımı": ["level design", "difficulty curve", "pacing"],
    "ilerleme": ["progression system", "player progression", "meta-progression", "skill tree"],
    "ekonomi": ["game economy", "in-game currency", "faucet and sink", "monetization"],
    "denge": ["game balance", "asymmetric balance", "tuning", "power curve"],
    "dengeleme": ["game balancing", "stat scaling", "balance tuning"],
    "oyun hissi": ["game feel", "juice", "screen shake", "haptics", "audio feedback"],
    "tempo": ["pacing", "flow state", "tension and release"],
    "akış": ["flow channel", "flow state Csikszentmihalyi"],
    "zorluk eğrisi": ["difficulty curve", "rubber banding", "dynamic difficulty adjustment"],
    "yol bulma": ["pathfinding", "navmesh", "A* algorithm"],
    "yapay zeka": ["game AI", "behavior trees", "finite state machines", "utility AI"],
    "hikaye": ["narrative design", "environmental storytelling", "branching narrative"],
    "anlatı": ["narrative structure", "ludonarrative dissonance", "environmental storytelling"],
    "arayüz": ["user interface", "UI design", "diegetic UI", "HUD"],
    "deneyim": ["user experience", "game UX", "affordance", "signifiers"],
    "erişilebilirlik": ["game accessibility", "colorblind mode", "subtitles", "input remapping"],
    "monetizasyon": ["monetization", "free to play", "battle pass", "gacha mechanics"],
    "gelir modeli": ["monetization model", "F2P design", "in-app purchases"],
    "prototip": ["rapid prototyping", "grayboxing", "paper prototyping"],
    "oyun testi": ["playtesting", "user research", "playtest feedback"],
    "belge": ["game design document", "GDD", "one-page design"],
    "döküman": ["GDD template", "feature specification"],
    "kayıt sistemi": ["save system", "checkpoints", "permadeath"],
    "öldürme kalıcı": ["permadeath", "roguelike progression"],
    "savaş": ["combat system", "action combat", "turn-based combat"],
    "envanter": ["inventory management", "grid inventory", "encumbrance"],
    "pazar": ["market", "market trends", "industry landscape"],
    "pazar durumu": ["market overview", "market analysis", "market share", "market trends"],
    "pazar analizi": ["market analysis", "industry trends", "market share"],
    "indirme": ["downloads", "download", "installs"],
    "indirmeler": ["downloads", "installations"],
    "trend": ["market trends", "emerging trends", "industry direction", "trends"],
    "trendler": ["market trends", "emerging trends", "trends"],
    "trendleri": ["market trends", "emerging trends", "trends"],
    "rekabet": ["competitive analysis", "market competitors", "gap analysis"],
    "analiz": ["analysis", "game design breakdown", "system analysis"],
    "analizi": ["analysis", "system mechanics breakdown"],
    "karakter": ["character", "player", "player character", "controller"],
    "sistem": ["system", "game systems", "mechanics"],
    "sistemi": ["system", "mechanics", "system design"],
    "sistemleri": ["systems", "game systems", "mechanics"],
    "zıplama": ["jump mechanics", "jumping", "aerial control", "coyote time", "jump"],
    "zıpla": ["jump", "jumping"],
    "koşma": ["locomotion", "running", "movement mechanics"],
    "yürüme": ["locomotion", "walking", "character movement", "movement"],
    "yürü": ["walk", "locomotion", "movement"],
    "animasyon": ["animation", "character animation", "game feel", "juice"],
    "animasyonlar": ["animations", "character animation", "procedural animation"],
    "animasyonları": ["animations", "character animation"],
    "animasyonlarını": ["animations", "character animation", "locomotion"],
    "kinematics": ["inverse kinematics", "procedural animation", "physics", "ik"],
    "inverse kinematics": ["inverse kinematics", "procedural animation", "locomotion", "ik"],
    "kinematik": ["inverse kinematics", "procedural animation", "kinematics"],
    "hareket": ["movement", "locomotion", "character movement", "traversal"],
    "duvar": ["wall", "wall run", "wall jump"],
    "duvarda": ["wall", "wall run", "wall jump"],
    "duvarda koşma": ["wall run", "wall jump", "movement system"],
    "açı": ["angle", "surface normal", "normals", "angles"],
    "açıları": ["angles", "surface normals", "thresholds"],
    "karşılaştır": ["compare", "comparison", "tradeoffs"],
    "karşılaştırma": ["comparison", "vs", "tradeoffs matrix"],
    "fark": ["difference", "contrast", "tradeoffs"],
    "brifing": ["briefing", "overview", "summary"],
    "özet": ["summary", "core principles", "executive summary"],
    "tavsiye": ["advice", "best practices", "guidelines", "pitfalls"],
    "tasarım": ["game design", "design patterns"],
    "tasarımı": ["game design", "systems design"],
    "tasarla": ["design", "game system design"],
    "gelir": ["revenue", "monetization", "arpu"],
    "tutundurma": ["retention", "d1 retention", "d7 retention"],
}


TURKISH_CHAR_PATTERN = re.compile(r"[çğıöşüÇĞİÖŞÜ]")


def detect_language(text: str) -> str:
    """Metnin Türkçe mi İngilizce mi olduğunu tespit eder.

    Args:
        text: İncelenecek metin.

    Returns:
        'tr' veya 'en'.
    """
    if not text:
        return "tr"

    # Türkçe özel karakterler kontrolü
    if TURKISH_CHAR_PATTERN.search(text):
        return "tr"

    # Türkçe yaygın ekler ve kelimeler kontrolü
    words = re.findall(r"\b[a-zA-ZçğıöşüÇĞİÖŞÜ]+\b", text.lower())
    turkish_common = {"bir", "bu", "şu", "nasıl", "nedir", "için", "ile", "ve", "veya", "yapılır", "etmek", "oyun"}
    match_count = sum(1 for w in words if w in turkish_common)

    if match_count >= 1:
        return "tr"

    return "en"


def get_english_terms_for_query(query: str) -> list[str]:
    """Sorgudaki Türkçe oyun tasarımı terimlerinin İngilizce karşılıklarını bulur.

    Args:
        query: Türkçe veya karma dildeki sorgu.

    Returns:
        İlgili İngilizce terimler listesi.
    """
    query_lower = query.lower()
    matched_terms: list[str] = []

    for tr_term, en_terms in GAME_DESIGN_TERM_MAP.items():
        if tr_term in query_lower:
            matched_terms.extend(en_terms)

    # Benzersiz yap ama sırayı koru
    seen = set()
    unique_terms = []
    for t in matched_terms:
        if t not in seen:
            seen.add(t)
            unique_terms.append(t)

    return unique_terms
