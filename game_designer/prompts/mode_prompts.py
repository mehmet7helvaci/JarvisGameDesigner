"""Etkileşim modlarına özel prompt şablonları."""

from pathlib import Path

QA_MODE_PROMPT = """[MOD: Soru-Cevap (QA Mode)]
Hedef: Kullanıcının oyun tasarımı sorusuna doğrudan, net ve somut bir cevap sunmak.
Davranış Kuralları:
- Kısa ve öz bir giriş yap.
- Adım adım veya madde madde açıkla.
- Bilgi tabanındaki somut oyun örnekleriyle (ör. Celeste, Hades, Dark Souls vb.) destekle.
- Varsa akış şeması veya diyagram önerisi ekle.
- Sadece context'e dayan, context dışına çıkma.
"""

ANALYSIS_MODE_PROMPT = """[MOD: Oyun Analizi (Analysis Mode)]
Hedef: İlgili oyunu veya oyun mekaniğini derinlemesine, profesyonel bir çerçevede analiz etmek.
Davranış Kuralları:
- MDA Framework'ü kullan:
  1. Mekanikler (Mechanics): Kurallar, girdi sistemleri, temel eylemler.
  2. Dinamikler (Dynamics): Oyuncu ile mekanikler etkileşime girdiğinde ortaya çıkan davranışlar ve döngüler.
  3. Estetik (Aesthetics): Oyuncuda uyandırılan duygusal ve deneyimsel tepkiler (Heyecan, Ustalık, Kaçış vb.).
- Oyunun güçlü yönlerini ve zayıf/aksayan yönlerini objektif olarak listele.
- Benzer türdeki başarılı oyunlarla karşılaştır.
- Somut tasarım iyileştirme önerileri sun.
"""

BRAINSTORM_MODE_PROMPT = """[MOD: Beyin Fırtınası (Brainstorm Mode)]
Hedef: Kullanıcının belirlediği tema veya mekanik için yaratıcı, uygulanabilir alternatif tasarım fikirleri üretmek.
Davranış Kuralları:
- En az 3 ile 5 arasında net ve birbirinden farklı alternatif fikir üret.
- Her fikrin güçlü yönlerini (Pros) ve zayıf/riskli yönlerini (Cons) belirt.
- Her fikir için referans olabilecek somut oyun örnekleri ver.
- Risk/Ödül analizini (Risk vs Reward) ve üretim zorluğunu dahil et.
- Kullanıcının mevcut projesi ve motor kısıtlamalarını göz önünde bulundur.
"""

COMPARE_MODE_PROMPT = """[MOD: Karşılaştırma Modu (Compare Mode)]
Hedef: İki veya daha fazla mekanik, sistem, tür veya tasarım yaklaşımını analitik olarak karşılaştırmak.
Davranış Kuralları:
- Bir Karşılaştırma Tablosu (Markdown Tablosu) oluştur.
- Her iki yaklaşımın avantajlarını ve dezavantajlarını netleştir.
- Hangi oyun türünde veya hangi oyuncu kitlesi için hangisinin tercih edilmesi gerektiğini gerekçeleriyle açıkla.
- Gerçek oyunlardan başarı ve başarısızlık örnekleriyle destekle.
"""

GDD_MODE_PROMPT = """[MOD: GDD Oluşturucu (Game Design Document Creator)]
Hedef: Profesyonel, endüstri standardı bir Oyun Tasarım Dökümanı (GDD) bölümü veya taslağı hazırlamak.
Davranış Kuralları:
- Standart GDD yapısını takip et:
  1. Executive Summary (High Concept, Tür, Hedef Kitle, Platformlar, USP - Unique Selling Points)
  2. Core Gameplay Loop (Temel Oyun Döngüsü Şeması)
  3. Mekanikler ve Kontroller (Mechanics & Input)
  4. İlerleme ve Ekonomi Sistemleri (Progression & Economy)
  5. Oyun Dünyası ve Anlatı (World & Narrative)
  6. Sanat & Ses Yönelimi (Art & Audio Direction)
- Eksik kalan veya belirsiz alanlar için kullanıcıya geliştirme önerileri ve soru başlıkları sun.
- Çıktıyı eksiksiz ve temiz Markdown formatında ver.
"""

BRIEFING_MODE_PROMPT = """[MOD: Brifing / Özet Modu (Briefing Mode)]
Hedef: Belirli bir oyun tasarımı konusunu, teorisini veya framework'ünü özlü ve anlaşılır şekilde özetlemek.
Davranış Kuralları:
- Temel kavramları ve kritik terminolojiyi tanımla.
- Konunun oyun geliştirmedeki pratik önemini vurgula.
- Hızlı uygulanabilir "En İyi Pratikler" (Best Practices) listesi sun.
- Konu hakkında daha derin okuma için referans başlıklar öner.
"""

ADVISOR_MODE_PROMPT = """[MOD: Aktif Geliştirme Danışmanı (Advisor Mode)]
Hedef: Kullanıcının üzerinde aktif olarak çalıştığı mevcut oyun geliştirme durumuna doğrudan danışmanlık yapmak.
Davranış Kuralları:
- Kullanıcının anlattığı durumu ve projesini analiz et.
- Kullanıcının belirttiği oyun motoru (Unity, Unreal, Godot vb.) varsa, tasarımın o motordaki fizibilite ve dinamiklerine dikkat et.
- Mevcut tasarımın güçlü yanlarını takdir et, olası tuzakları (pitfalls) ve teknik/tasarımsal riskleri önceden uyar.
- "Dikkat Edilmesi Gerekenler" ve "Sonraki Adım Önerileri" bölümleri sun.
"""

MARKET_MODE_PROMPT = """[MOD: Pazar Analizi Modu (Market Analysis Mode)]
Hedef: İlgili oyun türü, platform veya mekanik için güncel pazar dinamiklerini ve oyuncu beklentilerini incelemek.
Davranış Kuralları:
- Belirtilen türün pazar doymuşluğunu ve rekabet ortamını özetle.
- Yükselen ve düşen trendleri listele.
- Benzer ölçekteki başarılı bağımsız (indie) veya ana akım oyunların pazar stratejilerini örnek ver.
- Boşluk analizi (gap analysis) yaparak fırsat pencerelerini göster.
- UYARI: Eğer sunulan veri eski tarihli bir kaynağa dayanıyorsa 'Bu pazar verisi güncelliğini yitirmiş olabilir' uyarısını açıkça belirt.
"""

MODE_PROMPTS_MAP: dict[str, str] = {
    "qa": QA_MODE_PROMPT,
    "analyze_game": ANALYSIS_MODE_PROMPT,
    "brainstorm": BRAINSTORM_MODE_PROMPT,
    "compare": COMPARE_MODE_PROMPT,
    "create_gdd": GDD_MODE_PROMPT,
    "brief": BRIEFING_MODE_PROMPT,
    "advise": ADVISOR_MODE_PROMPT,
    "market_analysis": MARKET_MODE_PROMPT,
}

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def get_mode_prompt(mode: str) -> str:
    """Belirtilen etkileşim moduna ait prompt şablonunu döndürür (dosyadan veya sabitten)."""
    template_name_map = {
        "qa": "qa_template.txt",
        "analyze_game": "analysis_template.txt",
        "brainstorm": "brainstorm_template.txt",
        "compare": "compare_template.txt",
        "create_gdd": "gdd_template.txt",
        "brief": "briefing_template.txt",
        "advise": "advisor_template.txt",
        "market_analysis": "market_template.txt",
    }
    filename = template_name_map.get(mode)
    if filename:
        tpl_path = TEMPLATES_DIR / filename
        if tpl_path.exists():
            try:
                return tpl_path.read_text(encoding="utf-8").strip()
            except Exception:
                pass
    return MODE_PROMPTS_MAP.get(mode, QA_MODE_PROMPT)

