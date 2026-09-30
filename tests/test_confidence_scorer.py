"""Confidence Scorer birim testleri."""

import pytest
from game_designer.core.confidence_scorer import ConfidenceScorer
from game_designer.models.document import DocumentMetadata
from game_designer.models.query import RetrievedChunk
from game_designer.models.taxonomy import Category, SourceType


def test_confidence_scorer_empty():
    scorer = ConfidenceScorer()
    res = scorer.calculate_confidence([], [], 0, 0.0)
    assert res.final_score == 0.0
    assert "🔴" in res.badge
    assert res.multi_source_bonus == 0.0


def test_confidence_scorer_maximum(test_settings):
    scorer = ConfidenceScorer(test_settings)
    # 5 parça, her biri 1.0 benzerlik, Tier 5 kaynak, 1.0 coverage
    res = scorer.calculate_confidence(
        retrieval_scores=[1.0, 1.0, 1.0, 1.0, 1.0],
        source_tiers=[5, 5, 5, 5, 5],
        chunk_count=5,
        context_coverage=1.0,
    )
    assert res.final_score == 100.0
    assert "🟢" in res.badge
    assert res.avg_retrieval == 1.0
    assert res.avg_tier == 1.0
    assert res.multi_source_bonus == 1.0


def test_confidence_scorer_tiers():
    scorer = ConfidenceScorer()
    # Orta düzey bir senaryo
    res = scorer.calculate_confidence(
        retrieval_scores=[0.8, 0.7],
        source_tiers=[4, 3],
        chunk_count=2,
        context_coverage=0.6,
    )
    # avg_retrieval = 0.75 * 0.35 = 0.2625
    # avg_tier = (3.5 / 5) = 0.7 * 0.25 = 0.175
    # multi_source = 2 / 5 = 0.4 * 0.20 = 0.08
    # coverage = 0.6 * 0.20 = 0.12
    # total = (0.2625 + 0.175 + 0.08 + 0.12) * 100 = 63.75
    assert res.final_score == pytest.approx(63.75, abs=0.1)
    assert "🟠" in res.badge


def test_evaluate_chunks_keyword_coverage(test_settings, sample_chunk):
    scorer = ConfidenceScorer(test_settings)
    retrieved = [
        RetrievedChunk(
            chunk_id=sample_chunk.chunk_id,
            text=sample_chunk.text,
            score=0.85,
            metadata=sample_chunk.metadata,
        )
    ]
    # "Celeste coyote time" metinde geçiyor
    breakdown = scorer.evaluate_chunks("Celeste coyote time", retrieved)
    assert breakdown.final_score > 40.0
    assert breakdown.context_coverage > 0.5
