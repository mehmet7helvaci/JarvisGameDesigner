"""QAMode birim ve entegrasyon testleri."""

import pytest
from game_designer.core.rag_engine import RagEngine
from game_designer.data.chroma_manager import ChromaManager
from game_designer.data.document_processor import DocumentProcessor
from game_designer.data.embedding_manager import EmbeddingManager
from game_designer.data.user_profile import UserProfileStore
from game_designer.models.taxonomy import Category
from game_designer.modes.qa_mode import QAMode


def test_qa_mode_properties():
    mode = QAMode()
    assert mode.name == "qa"
    assert mode.default_temperature == 0.3
    assert mode.default_max_tokens == 4096


def test_qa_mode_execute_grounded(test_settings, sample_raw_doc):
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    doc_proc = DocumentProcessor(test_settings)
    user_store = UserProfileStore(test_settings)

    chunks = doc_proc.process_document(sample_raw_doc)
    chroma_mgr.add_chunks(chunks)

    rag = RagEngine(test_settings, chroma_mgr, user_store)
    mode = QAMode()

    response = mode.execute(
        query="Celeste oyununda coyote time neden önemlidir?",
        rag_engine=rag,
        category=Category.CORE_MECHANICS,
    )

    assert response is not None
    assert response.mode == "qa"
    assert response.confidence >= 50.0
    assert response.is_fallback is False
    assert len(response.sources) >= 1
    assert "coyote time" in response.text.lower()


def test_qa_mode_fallback_on_unrelated_query(test_settings):
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    user_store = UserProfileStore(test_settings)

    rag = RagEngine(test_settings, chroma_mgr, user_store)
    mode = QAMode()

    response = mode.execute(
        query="Kuantum mekaniğinde süperpozisyon ilkesi nedir?",
        rag_engine=rag,
    )

    assert response is not None
    assert response.mode == "qa"
    assert response.is_fallback is True
    assert "bilgi tabanımda doğrulanmış yeterli veri bulunmamaktadır" in response.text
