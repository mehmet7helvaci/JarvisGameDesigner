"""DocumentProcessor birim testleri."""

import pytest
from game_designer.data.document_processor import DocumentProcessor
from game_designer.models.document import RawDocument
from game_designer.models.taxonomy import Category, SourceType


def test_document_processor_empty(test_settings):
    processor = DocumentProcessor(test_settings)
    raw_doc = RawDocument(
        title="Empty Doc",
        content="",
        category=Category.CORE_MECHANICS,
    )
    chunks = processor.process_document(raw_doc)
    assert chunks == []


def test_document_processor_semantic_chunking(test_settings, sample_raw_doc):
    processor = DocumentProcessor(test_settings)
    chunks = processor.process_document(sample_raw_doc)

    assert len(chunks) >= 1
    for chunk in chunks:
        # Başlık korunmuş mu?
        assert "[" in chunk.text or "Celeste" in chunk.text
        # Metadata miras alınmış mı?
        assert chunk.metadata.category == Category.CORE_MECHANICS
        assert chunk.metadata.source_title == sample_raw_doc.title
        assert chunk.metadata.source_type == SourceType.ARTICLE
        assert "celeste" in chunk.metadata.tags
        assert chunk.chunk_id.startswith("3") or len(chunk.chunk_id) > 5


def test_document_processor_oversized_text(test_settings):
    processor = DocumentProcessor(test_settings)
    # 2000 karakterlik uzun metin
    long_text = "This is a detailed analysis of combat mechanics. " * 50
    raw_doc = RawDocument(
        title="Long Combat Document",
        content=f"# Long Section\n\n{long_text}",
        category=Category.CORE_MECHANICS,
    )
    chunks = processor.process_document(raw_doc)
    assert len(chunks) > 1
    for c in chunks:
        assert len(c.text) <= test_settings.chunking.max_chunk_size * 1.5
