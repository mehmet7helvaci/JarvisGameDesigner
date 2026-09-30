"""Etkileşim modu yönlendirici (Mode Router)."""

import re
from typing import Literal

SupportedMode = Literal[
    "qa",
    "analyze_game",
    "brainstorm",
    "compare",
    "create_gdd",
    "brief",
    "advise",
    "market_analysis",
]

MODE_PATTERNS: list[tuple[SupportedMode, list[str]]] = [
    (
        "create_gdd",
        [
            r"\bgdd\b",
            r"oyun dökümanı",
            r"tasarım belgesi",
            r"gdd hazırla",
            r"gdd oluştur",
            r"game design document",
        ],
    ),
    (
        "compare",
        [
            r"\bvs\b",
            r"karşılaştır",
            r"arasındaki fark",
            r"hangisi daha iyi",
            r"farkları neler",
            r"versus",
        ],
    ),
    (
        "market_analysis",
        [
            r"pazar durumu",
            r"pazar analizi",
            r"market analizi",
            r"piyasa durumu",
            r"steam trend",
            r"sektör durumu",
            r"satış rakamları",
        ],
    ),
    (
        "analyze_game",
        [
            r"analiz et",
            r"mekaniklerini incele",
            r"mda analizi",
            r"oyun incelemesi",
            r"derinlemesine incele",
            r"analizi yap",
        ],
    ),
    (
        "brainstorm",
        [
            r"fikir ver",
            r"beyin fırtınası",
            r"nasıl geliştirilebilir",
            r"önerilerin neler",
            r"yaratıcı fikir",
            r"mekanik öner",
            r"fikir üret",
        ],
    ),
    (
        "advise",
        [
            r"şu an .+ yapıyorum",
            r"üzerinde çalışıyorum",
            r"geliştiriyorum",
            r"tavsiye ver",
            r"ne yapmalıyım",
            r"doğru mu yapıyorum",
            r"projemde",
        ],
    ),
    (
        "brief",
        [
            r"brifing ver",
            r"özetle",
            r"özet geç",
            r"kısaca anlat",
            r"hızlı özet",
            r"özet bilgi",
        ],
    ),
]


class ModeRouter:
    """Kullanıcı sorgusuna en uygun etkileşim modunu tayin eden yönlendirici."""

    def route(self, query: str, explicit_mode: str | None = None) -> SupportedMode:
        """Sorgu metnini veya belirtilen açık modu değerlendirerek modu seçer.

        Args:
            query: Kullanıcı sorgusu.
            explicit_mode: Kullanıcının veya çağıran metodun açıkça belirttiği mod.

        Returns:
            Seçilen mod adı.
        """
        # Eğer açık bir mod belirtilmişse ve geçerliyse onu kullan
        if explicit_mode:
            normalized = explicit_mode.lower().strip()
            # Eşleme kısayolları
            mode_aliases: dict[str, SupportedMode] = {
                "qa": "qa",
                "analysis": "analyze_game",
                "analyze_game": "analyze_game",
                "brainstorm": "brainstorm",
                "compare": "compare",
                "gdd": "create_gdd",
                "create_gdd": "create_gdd",
                "brief": "brief",
                "briefing": "brief",
                "advise": "advise",
                "advisor": "advise",
                "market": "market_analysis",
                "market_analysis": "market_analysis",
            }
            if normalized in mode_aliases:
                return mode_aliases[normalized]

        query_lower = query.lower().strip()

        for mode, patterns in MODE_PATTERNS:
            for pat in patterns:
                if re.search(pat, query_lower):
                    return mode

        # Varsayılan mod Soru-Cevap (QA)
        return "qa"
