"""Utility functions for Jarvis Game Designer."""

from game_designer.utils.logger import logger, configure_logger
from game_designer.utils.text_utils import clean_text, extract_keywords, lexical_similarity, truncate_text
from game_designer.utils.language_utils import detect_language, get_english_terms_for_query, GAME_DESIGN_TERM_MAP

__all__ = [
    "logger",
    "configure_logger",
    "clean_text",
    "extract_keywords",
    "lexical_similarity",
    "truncate_text",
    "detect_language",
    "get_english_terms_for_query",
    "GAME_DESIGN_TERM_MAP",
]
