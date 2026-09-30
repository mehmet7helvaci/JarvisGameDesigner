import sys

# Windows konsolunda UTF-8 / emoji desteği (cp1254/cp1252 charmap çökmesini önler)
if sys.platform == "win32":
    try:
        if hasattr(sys.stdout, "reconfigure") and sys.stdout and not sys.stdout.closed:
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure") and sys.stderr and not sys.stderr.closed:
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from game_designer.models.document import DocumentChunk, DocumentMetadata, RawDocument
from game_designer.models.query import QueryInput, RetrievedChunk, RewrittenQuery
from game_designer.models.response import ConfidenceBreakdown, GameDesignerResponse, SourceCitation
from game_designer.models.taxonomy import Category, SourceType
from game_designer.models.user_profile import ActiveProject, UserProfile
from game_designer.models.project import BlendFileRef, GameProject
from game_designer.plugin import GameDesignerPlugin, JarvisPlugin

__all__ = [
    "GameDesignerPlugin",
    "JarvisPlugin",
    "Category",
    "SourceType",
    "DocumentChunk",
    "DocumentMetadata",
    "RawDocument",
    "QueryInput",
    "RewrittenQuery",
    "RetrievedChunk",
    "SourceCitation",
    "ConfidenceBreakdown",
    "GameDesignerResponse",
    "ActiveProject",
    "UserProfile",
    "BlendFileRef",
    "GameProject",
]

__version__ = "0.1.0"
