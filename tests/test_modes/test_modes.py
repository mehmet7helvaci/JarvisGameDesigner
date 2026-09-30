"""Etkileşim modları testleri."""

import pytest
from game_designer.core.mode_router import ModeRouter
from game_designer.core.rag_engine import RagEngine
from game_designer.data.chroma_manager import ChromaManager
from game_designer.data.document_processor import DocumentProcessor
from game_designer.data.embedding_manager import EmbeddingManager
from game_designer.data.user_profile import UserProfileStore
from game_designer.modes import MODES_REGISTRY


def test_mode_router_patterns():
    router = ModeRouter()
    assert router.route("Hades oyununu analiz et") == "analyze_game"
    assert router.route("Roguelike bir oyunda kalıcı ilerleme için fikir ver") == "brainstorm"
    assert router.route("F2P vs Premium gelir modellerini karşılaştır") == "compare"
    assert router.route("Projem için bir GDD oluştur") == "create_gdd"
    assert router.route("MDA framework hakkında brifing ver") == "brief"
    assert router.route("Şu an boss savaşı mekanikleri üzerinde çalışıyorum, tavsiye ver") == "advise"
    assert router.route("Deckbuilder türünün pazar durumu ve trendleri") == "market_analysis"
    assert router.route("Core loop nasıl tasarlanır?") == "qa"


def test_all_registered_modes_execution(test_settings, sample_raw_doc):
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    doc_proc = DocumentProcessor(test_settings)
    user_store = UserProfileStore(test_settings)

    chunks = doc_proc.process_document(sample_raw_doc)
    chroma_mgr.add_chunks(chunks)

    rag = RagEngine(test_settings, chroma_mgr, user_store)

    modes_to_test = [
        ("qa", "Celeste mekanikleri nelerdir?"),
        ("analyze_game", "Celeste oyununu analiz et"),
        ("brainstorm", "Platformer oyunu için fikir ver"),
        ("compare", "Coyote time vs Normal jump karşılaştır"),
        ("create_gdd", "Platformer GDD oluştur"),
        ("brief", "Game feel hakkında brifing ver"),
        ("advise", "Şu an platformer zıplama mekaniği üzerinde çalışıyorum"),
        ("market_analysis", "Platformer oyunlarının pazar durumu"),
    ]

    for mode_name, query in modes_to_test:
        mode_instance = MODES_REGISTRY[mode_name]
        resp = mode_instance.execute(query=query, rag_engine=rag)
        assert resp is not None
        assert resp.mode == mode_name
        assert len(resp.text) > 0
