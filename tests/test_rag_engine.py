"""RAG Engine ve sorgu işleme entegrasyon testleri."""

import pytest
from game_designer.core.query_rewriter import QueryRewriter
from game_designer.core.rag_engine import RagEngine
from game_designer.data.chroma_manager import ChromaManager
from game_designer.data.document_processor import DocumentProcessor
from game_designer.data.embedding_manager import EmbeddingManager
from game_designer.data.user_profile import UserProfileStore
from game_designer.models.document import RawDocument
from game_designer.models.taxonomy import Category, SourceType
from game_designer.models.user_profile import ActiveProject


def test_query_rewriter_intent_and_terms():
    rewriter = QueryRewriter()
    res = rewriter.rewrite("Platformer bir oyunda bölüm tasarımı ve tempo nasıl ayarlanır?")

    assert res.detected_language == "tr"
    assert res.detected_category == Category.LEVEL_DESIGN
    assert any("level design" in q.lower() for q in res.search_queries)
    assert any("pacing" in q.lower() for q in res.search_queries)


def test_query_rewriter_detect_engine_and_genre():
    rewriter = QueryRewriter()
    res = rewriter.rewrite("Unity motorunda Roguelike oyun için kalıcı ilerleme nasıl yapılır?")

    assert res.detected_engine == "Unity"
    assert res.detected_genre == "Roguelike"
    assert res.detected_category == Category.GAME_SYSTEMS


def test_rag_engine_fallback_when_empty(test_settings):
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    user_store = UserProfileStore(test_settings)

    rag = RagEngine(test_settings, chroma_mgr, user_store)

    # Hiç veri yokken bilinmeyen soru sorulduğunda
    response = rag.process_query("Kuantum fiziğinde dolanıklık nedir?")
    assert response.is_fallback is True
    assert response.confidence < 50.0
    assert "bilgi tabanımda doğrulanmış yeterli veri bulunmamaktadır" in response.text


def test_rag_engine_end_to_end_grounded(test_settings, sample_raw_doc):
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    doc_proc = DocumentProcessor(test_settings)
    user_store = UserProfileStore(test_settings)

    # Örnek dokümanı ekle
    chunks = doc_proc.process_document(sample_raw_doc)
    chroma_mgr.add_chunks(chunks)

    rag = RagEngine(test_settings, chroma_mgr, user_store)

    response = rag.process_query("Celeste oyununda jump ve coyote time nasıl tasarlanmış?")
    assert response.is_fallback is False
    assert response.confidence >= 50.0
    assert len(response.sources) >= 1
    assert "Celeste Movement and Game Feel Analysis" in response.sources[0].title
    assert "coyote time" in response.text.lower()
