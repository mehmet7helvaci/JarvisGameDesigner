"""Pytest test yapılandırması ve ortak fixture'lar."""

import shutil
import tempfile
import tkinter as tk
from pathlib import Path
import pytest

from game_designer.config import Settings
from game_designer.data.chroma_manager import ChromaManager
from game_designer.data.document_processor import DocumentProcessor
from game_designer.data.embedding_manager import EmbeddingManager
from game_designer.data.user_profile import UserProfileStore
from game_designer.models.document import DocumentChunk, DocumentMetadata, RawDocument
from game_designer.models.taxonomy import Category, SourceType

_shared_root = None


@pytest.fixture
def tk_root():
    """Tk root fixture that reuses an initialized hidden root and cleans up child widgets."""
    global _shared_root
    if _shared_root is None:
        _shared_root = tk.Tk()
        _shared_root.withdraw()
    else:
        try:
            if not _shared_root.winfo_exists():
                _shared_root = tk.Tk()
                _shared_root.withdraw()
        except Exception:
            _shared_root = tk.Tk()
            _shared_root.withdraw()

    yield _shared_root
    try:
        for child in _shared_root.winfo_children():
            child.destroy()
    except Exception:
        pass


@pytest.fixture
def temp_dir():
    """Geçici test dizini oluşturur ve test bitince temizler."""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp, ignore_errors=True)


@pytest.fixture
def test_settings(temp_dir):
    """Test ortamı için izole ayarlar nesnesi."""
    settings = Settings(
        app_name="Test Game Designer",
        project_root=temp_dir,
        data_dir=temp_dir / "data",
        chroma_db_dir=temp_dir / "data" / "chroma_db",
        user_profiles_dir=temp_dir / "data" / "user_profiles",
        projects_dir=temp_dir / "data" / "projects",
        scraper_cache_dir=temp_dir / "data" / "scraper_cache",
        logs_dir=temp_dir / "data" / "logs",
        seeds_dir=temp_dir / "seeds",
        gemini_api_key=None,  # Testlerde deterministik çalışsın
    )
    settings.ensure_directories()
    return settings


@pytest.fixture
def sample_raw_doc():
    """Örnek test dokümanı."""
    return RawDocument(
        title="Celeste Movement and Game Feel Analysis",
        content=(
            "# Movement Design in Celeste\n\n"
            "## Jump Mechanics\n"
            "Celeste gives the player precise aerial control. It implements 'coyote time' "
            "allowing players to jump a few frames after stepping off a ledge.\n\n"
            "## Dash Mechanics\n"
            "The dash mechanic freezes the game for 4 frames (hitstop) to provide immense game feel and impact.\n\n"
            "## Pacing\n"
            "Each screen represents a discrete micro-challenge, avoiding frustration."
        ),
        category=Category.CORE_MECHANICS,
        subcategory="game_feel",
        tags=["celeste", "platformer", "game_feel", "juice"],
        source_type=SourceType.ARTICLE,
        source_url="https://example.com/celeste-design",
        author="Maddy Thorson",
        game_engines=["Monogame"],
        game_genres=["Platformer"],
        is_verified=True,
    )


@pytest.fixture
def sample_chunk(sample_raw_doc):
    """Örnek döküman parçası."""
    meta = DocumentMetadata(
        category=sample_raw_doc.category,
        subcategory=sample_raw_doc.subcategory,
        tags=sample_raw_doc.tags,
        source_type=sample_raw_doc.source_type,
        source_url=sample_raw_doc.source_url,
        source_title=sample_raw_doc.title,
        author=sample_raw_doc.author,
        reliability_tier=4,
        is_verified=True,
        game_engines=sample_raw_doc.game_engines,
        game_genres=sample_raw_doc.game_genres,
        chunk_id="test_chunk_001",
    )
    return DocumentChunk(
        chunk_id="test_chunk_001",
        text="Celeste implements coyote time and 4 frames of hitstop for responsive game feel.",
        metadata=meta,
    )
