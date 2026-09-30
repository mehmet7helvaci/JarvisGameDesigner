"""Güvenilirlik puanlama sistemi (Confidence Scorer)."""

import re
from game_designer.config import Settings, get_settings
from game_designer.models.document import DocumentMetadata
from game_designer.models.query import RetrievedChunk
from game_designer.models.response import ConfidenceBreakdown
from game_designer.utils.language_utils import get_english_terms_for_query
from game_designer.utils.text_utils import extract_keywords


class ConfidenceScorer:
    """RAG cevaplarının güvenilirlik skorunu hesaplayan sınıf."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def calculate_confidence(
        self,
        retrieval_scores: list[float],
        source_tiers: list[int],
        chunk_count: int,
        context_coverage: float,
    ) -> ConfidenceBreakdown:
        """Formüle göre güvenilirlik skoru ve ayrıntılarını hesaplar.

        Ağırlıklar (kurallar.md):
        - Retrieval kalitesi: %35
        - Kaynak güvenilirliği: %25
        - Çoklu kaynak desteği: %20
        - Context coverage: %20
        """
        cfg = self.settings.confidence

        if not retrieval_scores or not source_tiers or chunk_count == 0:
            return ConfidenceBreakdown(
                avg_retrieval=0.0,
                avg_tier=0.0,
                multi_source_bonus=0.0,
                context_coverage=0.0,
                final_score=0.0,
                level="Çok Düşük / Yetersiz: Bilgi tabanında yeterli veri yok",
                badge="🔴 %0.0",
            )

        avg_retrieval = max(0.0, min(1.0, sum(retrieval_scores) / len(retrieval_scores)))
        # Tier 1-5 arası -> 0-1 arası normalizasyon
        avg_tier = max(0.0, min(1.0, (sum(source_tiers) / len(source_tiers)) / 5.0))
        # 5 veya daha fazla kaynak tam bonus (1.0)
        multi_source_bonus = min(chunk_count / 5.0, 1.0)
        coverage = max(0.0, min(1.0, context_coverage))

        score = (
            avg_retrieval * cfg.retrieval_weight +
            avg_tier * cfg.source_tier_weight +
            multi_source_bonus * cfg.multi_source_weight +
            coverage * cfg.coverage_weight
        ) * 100.0

        final_score = round(score, 1)
        final_score = max(0.0, min(100.0, final_score))

        if final_score >= 90.0:
            level = "Yüksek Güvenilirlik: Birden fazla güvenilir kaynakla doğrulanmış"
            badge = f"🟢 %{final_score}"
        elif final_score >= 70.0:
            level = "Orta Güvenilirlik: Tek kaynak veya kısmen desteklenmiş"
            badge = f"🟡 %{final_score}"
        elif final_score >= 50.0:
            level = "Düşük Güvenilirlik: Sınırlı kaynak, dikkatli değerlendir"
            badge = f"🟠 %{final_score}"
        else:
            level = "Çok Düşük / Yetersiz: Bilgi tabanında yeterli veri yok"
            badge = f"🔴 %{final_score}"

        return ConfidenceBreakdown(
            avg_retrieval=round(avg_retrieval, 4),
            avg_tier=round(avg_tier, 4),
            multi_source_bonus=round(multi_source_bonus, 4),
            context_coverage=round(coverage, 4),
            final_score=final_score,
            level=level,
            badge=badge,
        )

    def evaluate_chunks(self, query: str, chunks: list[RetrievedChunk]) -> ConfidenceBreakdown:
        """Alınan chunk listesini ve kullanıcı sorgusunu analiz ederek skoru türetir."""
        if not chunks:
            return self.calculate_confidence([], [], 0, 0.0)

        retrieval_scores = [c.score for c in chunks]
        source_tiers = [c.metadata.reliability_tier for c in chunks]
        chunk_count = len(chunks)

        # Context coverage tahmini: Sorgunun anahtar kelimelerinin ne kadarı chunk'larda geçiyor?
        core_query = query.split(" - ")[0].strip()
        query_kw = extract_keywords(core_query, max_keywords=8)
        if not query_kw:
            query_kw = extract_keywords(query, max_keywords=8)
        if not query_kw:
            basic_stop = {"ve", "veya", "ile", "bir", "bu", "şu", "o", "mı", "mi", "mu", "mü", "de", "da", "the", "a", "an", "is", "in", "to"}
            query_kw = [w for w in re.findall(r"\b[a-zA-ZçğıöşüÇĞİÖŞÜ0-9_\-]{3,}\b", query.lower()) if w not in basic_stop][:8]

        if not query_kw:
            coverage = 0.5
        else:
            all_chunks_text = " ".join([
                f"{c.text} {c.metadata.source_title} {' '.join(c.metadata.tags)} {c.metadata.subcategory}".lower()
                for c in chunks
            ])
            matched = 0
            for kw in query_kw:
                kw_lower = kw.lower()
                if kw_lower in all_chunks_text:
                    matched += 1
                else:
                    en_terms = get_english_terms_for_query(kw_lower)
                    if any(et.lower() in all_chunks_text or any(w in all_chunks_text for w in et.lower().split()) for et in en_terms):
                        matched += 1
            coverage = matched / len(query_kw)


        return self.calculate_confidence(
            retrieval_scores=retrieval_scores,
            source_tiers=source_tiers,
            chunk_count=chunk_count,
            context_coverage=coverage,
        )
