"""İleri düzey mimari gereksinimler ve uç durum testleri."""

import json
from datetime import date, timedelta
from pathlib import Path
import pytest

from game_designer.config import Settings
from game_designer.core.rag_engine import RagEngine
from game_designer.core.response_formatter import ResponseFormatter
from game_designer.data.chroma_manager import ChromaManager
from game_designer.data.document_processor import DocumentProcessor
from game_designer.data.embedding_manager import EmbeddingManager
from game_designer.data.user_profile import UserProfileStore
from game_designer.models.document import RawDocument
from game_designer.models.query import RetrievedChunk
from game_designer.models.taxonomy import Category, SourceType
from game_designer.prompts.mode_prompts import get_mode_prompt
from game_designer.scraper.scheduler import ScraperScheduler


def test_settings_load_from_yaml(tmp_path: Path):
    yaml_file = tmp_path / "config.yaml"
    yaml_file.write_text(
        """
app_name: "Custom Game Designer"
version: "2.0.0"
generation:
  temperature: 0.1
  model: "gemini-test"
""",
        encoding="utf-8",
    )

    settings = Settings.load(config_path=yaml_file)
    assert settings.app_name == "Custom Game Designer"
    assert settings.version == "2.0.0"
    assert settings.generation.temperature == 0.1
    assert settings.generation.model == "gemini-test"


def test_settings_load_from_json(tmp_path: Path):
    json_file = tmp_path / "config.json"
    json_file.write_text(
        json.dumps({
            "app_name": "JSON Game Designer",
            "version": "1.5.0",
        }),
        encoding="utf-8",
    )

    settings = Settings.load(config_path=json_file)
    assert settings.app_name == "JSON Game Designer"
    assert settings.version == "1.5.0"


def test_document_processor_enforces_tags_rule(test_settings):
    processor = DocumentProcessor(test_settings)

    # 1. Sıfır etiket verildiğinde otomatik olarak en az 2 etiket üretilmeli
    raw_doc_no_tags = RawDocument(
        title="Tagless Game Mechanics",
        content="Core mechanics dictate player actions and rules.",
        category=Category.CORE_MECHANICS,
        subcategory="rules",
        tags=[],
    )
    chunks = processor.process_document(raw_doc_no_tags)
    assert len(chunks) >= 1
    assert len(chunks[0].metadata.tags) >= 2
    assert "core_mechanics" in chunks[0].metadata.tags

    # 2. 15 etiket verildiğinde maksimum 10 etikete kırpılmalı
    many_tags = [f"tag_{i}" for i in range(15)]
    raw_doc_many_tags = RawDocument(
        title="Many Tags Doc",
        content="Multi-tag systems in modern games.",
        category=Category.GAME_SYSTEMS,
        tags=many_tags,
    )
    chunks_many = processor.process_document(raw_doc_many_tags)
    assert len(chunks_many) >= 1
    assert len(chunks_many[0].metadata.tags) == 10


def test_hybrid_search_and_keyword_search(test_settings):
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    doc_proc = DocumentProcessor(test_settings)

    doc = RawDocument(
        title="Specific Keyword Document",
        content="This document specifically analyzes the exotic term XenobladeAffinityChartSystem in detail.",
        category=Category.GAME_SYSTEMS,
        tags=["xenoblade", "affinity"],
    )
    chunks = doc_proc.process_document(doc)
    chroma_mgr.add_chunks(chunks)

    # Doğrudan anahtar kelime araması
    kw_results = chroma_mgr.keyword_search("XenobladeAffinityChartSystem")
    assert len(kw_results) >= 1
    assert "XenobladeAffinityChartSystem" in kw_results[0].text

    # Hibrit arama (vektör ve leksikal adayların birleşimi)
    hybrid_results = chroma_mgr.hybrid_search("XenobladeAffinityChartSystem")
    assert len(hybrid_results) >= 1
    assert "XenobladeAffinityChartSystem" in hybrid_results[0].text


def test_chroma_deduplicate_chunks(test_settings, sample_raw_doc):
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    doc_proc = DocumentProcessor(test_settings)

    chunks = doc_proc.process_document(sample_raw_doc)
    chroma_mgr.add_chunks(chunks)
    count_before = chroma_mgr.count()

    # Aynı içerikte kopya bir parça oluşturup farklı ID ile ekle
    duplicate_chunk = chunks[0].model_copy(deep=True)
    duplicate_chunk.chunk_id = "duplicate_9999"
    chroma_mgr.add_chunks([duplicate_chunk])
    assert chroma_mgr.count() == count_before + 1

    # Mükerrer temizliği çalıştır
    removed = chroma_mgr.deduplicate_chunks()
    assert removed >= 1
    assert chroma_mgr.count() == count_before


def test_scheduler_maintenance_tasks(test_settings):
    scheduler = ScraperScheduler(test_settings)
    m_res = scheduler.run_maintenance()

    assert "removed_duplicates" in m_res
    assert "updated_stale_scores" in m_res
    assert "compacted" in m_res
    assert m_res["compacted"] is True


def test_market_mode_stale_date_warning(test_settings):
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    doc_proc = DocumentProcessor(test_settings)
    user_store = UserProfileStore(test_settings)

    # 2 yıl önceki pazar verisi (Tier 4 Postmortem raporu, 2 parçalı zengin doküman)
    stale_date = date.today() - timedelta(days=750)
    stale_doc = RawDocument(
        title="2024 Historical Mobile Market Report",
        content=(
            "# Hypercasual Market Share 2024\n\n"
            "Hypercasual game downloads and market share analysis in 2024 showed rapid saturation and declining retention.\n\n"
            "## Revenue and Trends\n"
            "Ad revenue metrics and hypercasual publishing trends indicated shifting player preferences toward hybrid-casual games."
        ),
        category=Category.MARKET_ANALYSIS,
        source_type=SourceType.POSTMORTEM,
        publication_date=stale_date,
        tags=["market", "mobile", "hypercasual"],
        is_verified=True,
    )
    chunks = doc_proc.process_document(stale_doc)
    chroma_mgr.add_chunks(chunks)

    rag = RagEngine(test_settings, chroma_mgr, user_store)
    response = rag.process_query(
        "Hypercasual pazar durumu ve indirme analizi",
        mode="market_analysis",
    )

    assert response.mode == "market_analysis"
    assert len(response.sources) >= 1
    assert response.sources[0].is_stale is True
    # Uyarı metni raporda veya kaynakta bulunmalı
    assert "Pazar Verisi Uyarısı" in response.text or "Güncel olmayabilir" in response.text


def test_get_mode_prompt_templates():
    # Templates klasöründen prompt şablonlarının okunması
    qa_prompt = get_mode_prompt("qa")
    assert "[MOD: Soru-Cevap (QA Mode)]" in qa_prompt

    gdd_prompt = get_mode_prompt("create_gdd")
    assert "Executive Summary" in gdd_prompt

    market_prompt = get_mode_prompt("market_analysis")
    assert "Pazar Analizi" in market_prompt


def test_all_8_modes_local_synthesis_output_structure(test_settings):
    embedding_mgr = EmbeddingManager(test_settings)
    chroma_mgr = ChromaManager(test_settings, embedding_mgr)
    doc_proc = DocumentProcessor(test_settings)
    user_store = UserProfileStore(test_settings)

    # Tier 5 Kitap & Tasarım Çerçevesi ekle
    doc = RawDocument(
        title="Celeste Movement and Game Feel Analysis",
        content=(
            "# Movement Design in Celeste\n\n"
            "## Jump Mechanics\n"
            "Celeste gives the player precise aerial control. It implements coyote time "
            "allowing players to jump a few frames after stepping off a ledge.\n\n"
            "## Dash Mechanics\n"
            "The dash mechanic freezes the game for 4 frames (hitstop) to provide immense game feel and impact.\n\n"
            "## Pacing\n"
            "Each screen represents a discrete micro-challenge, avoiding frustration."
        ),
        category=Category.CORE_MECHANICS,
        subcategory="game_feel",
        tags=["celeste", "platformer", "game_feel", "juice"],
        source_type=SourceType.BOOK,
        is_verified=True,
    )
    market_doc = RawDocument(
        title="Platformer Market Trends and Landscape",
        content=(
            "# Platformer Market Report\n\n"
            "Precision platformers maintain high engagement on Steam and consoles. "
            "Top indie games differentiate through responsive game feel and speedrunning features."
        ),
        category=Category.MARKET_ANALYSIS,
        source_type=SourceType.BOOK,
        tags=["platformer", "market", "indie"],
        is_verified=True,
    )
    gdd_doc = RawDocument(
        title="Platformer Game Design Document Template",
        content=(
            "# Platformer GDD Specification\n\n"
            "Core gameplay loop consists of level traversal, hazard evasion, and secret collection. "
            "Input buffering and coyote time ensure forgiving platforming controls."
        ),
        category=Category.GDD,
        source_type=SourceType.BOOK,
        tags=["gdd", "platformer", "specification"],
        is_verified=True,
    )

    chroma_mgr.add_chunks(doc_proc.process_document(doc))
    chroma_mgr.add_chunks(doc_proc.process_document(market_doc))
    chroma_mgr.add_chunks(doc_proc.process_document(gdd_doc))

    rag = RagEngine(test_settings, chroma_mgr, user_store)

    # 1. analyze_game -> MDA Framework
    resp_analysis = rag.process_query("Celeste mekanikleri ve jump analizi", mode="analyze_game")
    assert "MDA Framework" in resp_analysis.text
    assert "Mekanikler" in resp_analysis.text
    assert "Dinamikler" in resp_analysis.text
    assert "Estetik" in resp_analysis.text

    # 2. brainstorm -> Fikirler ve Pro/Con
    resp_brainstorm = rag.process_query("Celeste tarzı platformer için zıplama fikirleri", mode="brainstorm")
    assert "Beyin Fırtınası" in resp_brainstorm.text
    assert "Fikir 1" in resp_brainstorm.text

    # 3. compare -> Karşılaştırma tablosu
    resp_compare = rag.process_query("Jump vs Dash mekanikleri karşılaştırması", mode="compare")
    assert "Karşılaştırma" in resp_compare.text or "|" in resp_compare.text

    # 4. create_gdd -> Standart GDD bölümleri
    resp_gdd = rag.process_query("Platformer oyunu için GDD taslağı", mode="create_gdd")
    assert "Game Design Document" in resp_gdd.text
    assert "Core Gameplay Loop" in resp_gdd.text

    # 5. brief -> Yönetici özeti ve En İyi Pratikler
    resp_brief = rag.process_query("Celeste game feel brifingi", mode="brief")
    assert "Yönetici Özeti" in resp_brief.text or "Brifing" in resp_brief.text

    # 6. advise -> Durum analizi, tuzaklar, sonraki adımlar
    resp_advise = rag.process_query("Celeste benzeri karakter zıplama sistemi tasarlıyorum, tavsiye", mode="advise")
    assert "Danışmanlığı" in resp_advise.text
    assert "Tuzaklar" in resp_advise.text
    assert "Sonraki Adım" in resp_advise.text

    # 7. market_analysis -> Pazar durumu, trendler, gap analizi
    resp_market = rag.process_query("Platformer oyunlarının pazar durumu ve trendleri", mode="market_analysis")
    assert "Pazar Durumu" in resp_market.text
    assert "Gap Analysis" in resp_market.text or "Fırsat Boşluğu" in resp_market.text

    # 8. qa -> Tasarım yanıtı
    resp_qa = rag.process_query("Celeste oyununda coyote time nedir?", mode="qa")
    assert "Tasarım Yanıtı" in resp_qa.text or "Kaynaklar" in resp_qa.text

