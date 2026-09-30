from datetime import date
from game_designer.models.query import RetrievedChunk
from game_designer.models.response import ConfidenceBreakdown, GameDesignerResponse, SourceCitation
from game_designer.models.taxonomy import SourceType


class ResponseFormatter:
    """Üretilen cevabı, güvenilirlik rozetini ve kaynakçayı standartlaştıran sınıf."""

    def format_citations(self, chunks: list[RetrievedChunk], mode: str = "qa") -> list[SourceCitation]:
        """Chunk listesinden benzersiz kaynak referansları listesi çıkarır."""
        citations: list[SourceCitation] = []
        seen_titles = set()
        today = date.today()

        for c in chunks:
            meta = c.metadata
            if meta.source_title not in seen_titles:
                seen_titles.add(meta.source_title)

                is_stale = False
                if meta.publication_date:
                    days_diff = (today - meta.publication_date).days
                    if days_diff > 365:
                        is_stale = True

                citations.append(
                    SourceCitation(
                        title=meta.source_title,
                        url=meta.source_url,
                        source_type=meta.source_type,
                        reliability_tier=meta.reliability_tier,
                        chunk_id=c.chunk_id,
                        publication_date=meta.publication_date,
                        is_stale=is_stale,
                    )
                )

        return citations

    def format_final_text(
        self,
        raw_text: str,
        confidence: ConfidenceBreakdown,
        citations: list[SourceCitation],
        is_fallback: bool = False,
        mode: str = "qa",
    ) -> str:
        """Kullanıcıya sunulacak nihai Markdown metnini inşa eder."""
        header = f"> **{confidence.badge} Güvenilirlik** — *{confidence.level}*\n\n"

        stale_market_warning = ""
        has_stale_source = any(cit.is_stale for cit in citations)
        if mode == "market_analysis" and has_stale_source and not is_fallback:
            stale_market_warning = (
                "> ⚠️ **Pazar Verisi Uyarısı:** İncelenen kaynakların bir kısmı 1 yıldan eski tarihli olduğundan "
                "güncel pazar dinamiklerini tam yansıtmayabilir.\n\n"
            )

        body = raw_text.strip()

        sources_section = ""
        if citations and not is_fallback:
            sources_section = "\n\n---\n### 📚 Doğrulanmış Kaynaklar\n"
            for idx, cit in enumerate(citations, 1):
                link = f"[{cit.title}]({cit.url})" if cit.url else f"**{cit.title}**"
                stale_tag = " *(⚠️ Güncel olmayabilir - 1 yıldan eski)*" if cit.is_stale else ""
                sources_section += f"{idx}. {link} *(Tier {cit.reliability_tier} - {cit.source_type.value})*{stale_tag}\n"

        return f"{header}{stale_market_warning}{body}{sources_section}"


    def build_fallback_response(
        self,
        query: str,
        confidence: ConfidenceBreakdown,
        partial_chunks: list[RetrievedChunk] | None = None,
        mode: str = "qa",
    ) -> GameDesignerResponse:
        """Yetersiz bilgi durumunda kural 7.4 'Bilmiyorum' politikasını uygulayan cevap üretir."""
        partial_chunks = partial_chunks or []
        citations = self.format_citations(partial_chunks)

        text = (
            "Bu konuda bilgi tabanımda doğrulanmış yeterli veri bulunmamaktadır.\n\n"
            "**Neden kesin cevap veremiyorum?**\n"
            "- Bilgi tabanında bu mekanik/konu ile doğrudan eşleşen GDC, kitap veya akademik kaynak eşiği geçemedi.\n"
            "- Halüsinasyon ve yanıltıcı tasarım tavsiyelerini önlemek amacıyla doğrulanmamış bilgi üretilmemektedir.\n\n"
            "**Önerilen Adımlar:**\n"
            "1. İlgili konuyu daha spesifik anahtar kelimelerle veya oyun motoru/tür belirterek tekrar sorabilirsiniz.\n"
            "2. Elinizdeki güvenilir kaynak/dokümanları bilgi tabanına seed olarak ekleyebilirsiniz.\n"
            "3. Web tarayıcısı (Scraper) modülü ile bu konudaki GDC ve dev blog içeriklerini taramamı isteyebilirsiniz."
        )

        formatted_text = self.format_final_text(
            raw_text=text,
            confidence=confidence,
            citations=citations,
            is_fallback=True,
        )

        return GameDesignerResponse(
            text=formatted_text,
            confidence=confidence.final_score,
            confidence_breakdown=confidence,
            sources=citations,
            mode=mode,
            is_fallback=True,
            suggested_followups=[
                "Bu konuda internette araştırma yap",
                "Farklı bir oyun türü ile karşılaştır",
                "Örnek bir oyun üzerinden sor",
            ],
        )
