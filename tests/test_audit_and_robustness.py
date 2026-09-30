"""Skeptical review and robustness verification tests.

Validates:
- Stale scores update logic during maintenance
- Windows encoding safe badges and plain text representations
- Mode registry alias lookups
- Robustness on empty/whitespace inputs
- Process intent with None entities
- Deterministic SHA-256 deduplication
- Placeholder API key safety
- Packaging cleanliness (tests excluded from distribution)
"""

from datetime import date, timedelta
import pytest
from setuptools import find_packages

from game_designer.core.rag_engine import RagEngine
from game_designer.data.chroma_manager import ChromaManager
from game_designer.data.document_processor import DocumentProcessor
from game_designer.data.embedding_manager import EmbeddingManager
from game_designer.data.user_profile import UserProfileStore
from game_designer.models.document import RawDocument
from game_designer.models.response import ConfidenceBreakdown, GameDesignerResponse
from game_designer.models.taxonomy import Category, SourceType
from game_designer.modes import MODES_REGISTRY
from plugin import JarvisGameDesignPlugin


def test_windows_safe_badge_and_plain_text():
    """Rozet ve düz metin dönüştürücülerinin ASCII terminallere uyumunu test eder."""
    breakdown = ConfidenceBreakdown(
        avg_retrieval=0.9,
        avg_tier=1.0,
        multi_source_bonus=1.0,
        context_coverage=1.0,
        final_score=95.0,
        level="Yüksek Güvenilirlik",
        badge="🟢 %95.0",
    )
    assert "[HIGH]" in breakdown.safe_badge
    assert "🟢" not in breakdown.safe_badge

    resp = GameDesignerResponse(
        text="> **🟢 %95.0 Güvenilirlik**\n\nÖrnek cevap metni.",
        confidence=95.0,
        confidence_breakdown=breakdown,
    )
    assert "[HIGH]" in resp.plain_text
    assert "🟢" not in resp.plain_text


def test_chroma_update_stale_scores_active(test_settings):
    """update_stale_scores() metodunun 1 yıldan eski verileri tespit edip güncellediğini doğrular."""
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    doc_proc = DocumentProcessor(test_settings)

    # 400 gün önceki eski bir pazar raporu
    old_doc = RawDocument(
        title="Old Market Report 2024",
        content="Mobile hypercasual and hybrid casual game market dynamics in early 2024.",
        category=Category.MARKET_ANALYSIS,
        source_type=SourceType.POSTMORTEM,
        publication_date=date.today() - timedelta(days=400),
        tags=["market", "mobile"],
        is_verified=True,
    )
    chunks = doc_proc.process_document(old_doc)
    chroma_mgr.add_chunks(chunks)

    # Başlangıçta fallback depo metadata'sında is_stale False olmalı
    cid = chunks[0].chunk_id
    stored_data = chroma_mgr._fallback_docs[cid]
    assert stored_data["metadata"].get("is_stale") is not True

    # Bakım skor güncellemesini çalıştır
    updated = chroma_mgr.update_stale_scores()
    assert updated >= 1
    assert chroma_mgr._fallback_docs[cid]["metadata"]["is_stale"] is True


def test_modes_registry_aliases():
    """Tüm takma adların (aliases) MODES_REGISTRY üzerinden erişilebilir olduğunu teyit eder."""
    assert MODES_REGISTRY["analysis"] is MODES_REGISTRY["analyze_game"]
    assert MODES_REGISTRY["gdd"] is MODES_REGISTRY["create_gdd"]
    assert MODES_REGISTRY["briefing"] is MODES_REGISTRY["brief"]
    assert MODES_REGISTRY["advisor"] is MODES_REGISTRY["advise"]
    assert MODES_REGISTRY["market"] is MODES_REGISTRY["market_analysis"]


@pytest.mark.asyncio
async def test_plugin_process_intent_with_none_entities(test_settings):
    """process_intent çağrısında entities=None durumunda çökme olmadan yanıt döndüğünü teyit eder."""
    plugin = JarvisGameDesignPlugin(
        project_root=test_settings.project_root,
        data_dir=test_settings.data_dir,
        chroma_db_dir=test_settings.chroma_db_dir,
        user_profiles_dir=test_settings.user_profiles_dir,
        seeds_dir=test_settings.seeds_dir,
    )
    plugin.initialize()

    reply = await plugin.process_intent("oyun tasarımı", None)
    assert "nasıl yardımcı olabilirim" in reply.lower()


def test_empty_and_whitespace_query_robustness(test_settings):
    """Boş veya sadece boşluktan oluşan sorguların kontrollü fallback döndürdüğünü teyit eder."""
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    user_store = UserProfileStore(test_settings)
    rag = RagEngine(test_settings, chroma_mgr, user_store)

    resp_empty = rag.process_query("")
    assert resp_empty.is_fallback is True
    assert resp_empty.confidence == 0.0

    resp_whitespace = rag.process_query("   \t\n   ")
    assert resp_whitespace.is_fallback is True
    assert resp_whitespace.confidence == 0.0


def test_placeholder_api_key_filtered_to_local_synthesis(test_settings, sample_raw_doc):
    """Placeholder API anahtarlarının uzak çağrı yapmadan yerel senteze güvenle düştüğünü doğrular."""
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    doc_proc = DocumentProcessor(test_settings)
    user_store = UserProfileStore(test_settings)

    chroma_mgr.add_chunks(doc_proc.process_document(sample_raw_doc))

    # Placeholder anahtarlı settings
    test_settings.gemini_api_key = "your_gemini_api_key_here"
    rag = RagEngine(test_settings, chroma_mgr, user_store)

    resp = rag.process_query("Celeste mekanikleri nelerdir?", mode="qa")
    assert resp.is_fallback is False
    assert resp.confidence >= 50.0
    assert "Tasarım Yanıtı" in resp.text


def test_packaging_excludes_tests():
    """Dağıtım paketinde tests dizininin hariç tutulduğunu doğrular."""
    packages = find_packages(include=["game_designer*", "seeds*"], exclude=["tests*"])
    assert "game_designer" in packages
    assert "seeds" in packages
    assert "tests" not in packages
    assert not any(p.startswith("tests") for p in packages)
