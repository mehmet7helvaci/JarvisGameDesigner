"""Başlangıç (seed) verilerini ChromaDB vektör veritabanına yükleme scripti."""

import json
from pathlib import Path
import sys
from typing import Any

# Proje kökünü sys.path'e ekle
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from game_designer.config import Settings, get_settings
from game_designer.data.chroma_manager import ChromaManager
from game_designer.data.document_processor import DocumentProcessor
from game_designer.models.document import RawDocument
from game_designer.models.taxonomy import Category, SourceType
from game_designer.utils.logger import logger


def load_seed_file(file_path: Path) -> RawDocument | None:
    """Tek bir seed JSON dosyasını okuyup RawDocument modeline dönüştürür."""
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            data: dict[str, Any] = json.load(f)

        title = data.get("title", file_path.stem.replace("_", " ").title())
        content = data.get("content", "")
        if not content:
            logger.warning(f"Seed dosyasında içerik yok: {file_path}")
            return None

        cat_str = data.get("category", "core_mechanics")
        try:
            category = Category(cat_str)
        except ValueError:
            category = Category.CORE_MECHANICS

        st_str = data.get("source_type", "book")
        try:
            source_type = SourceType(st_str)
        except ValueError:
            source_type = SourceType.BOOK

        return RawDocument(
            title=title,
            content=content,
            category=category,
            subcategory=data.get("subcategory", "seed"),
            tags=data.get("tags", []),
            source_type=source_type,
            source_url=data.get("source_url"),
            author=data.get("author"),
            game_engines=data.get("game_engines", []),
            game_genres=data.get("game_genres", []),
            is_verified=True,
        )
    except Exception as e:
        logger.error(f"Seed dosyası okuma hatası ({file_path}): {e}")
        return None


def load_all_seeds(
    settings: Settings | None = None,
    chroma_manager: ChromaManager | None = None,
    doc_processor: DocumentProcessor | None = None,
) -> int:
    """Tüm seed dizinlerini tarar ve döküman parçalarını ChromaDB'ye ekler."""
    settings = settings or get_settings()
    chroma_manager = chroma_manager or ChromaManager(settings)
    doc_processor = doc_processor or DocumentProcessor(settings)

    seeds_dir = settings.seeds_dir
    if not seeds_dir.exists():
        logger.warning(f"Seed dizini bulunamadı: {seeds_dir}")
        return 0

    json_files = list(seeds_dir.rglob("*.json"))
    logger.info(f"Yüklenecek {len(json_files)} seed dosyası bulundu.")

    total_chunks = 0
    for jf in json_files:
        raw_doc = load_seed_file(jf)
        if raw_doc:
            chunks = doc_processor.process_document(raw_doc)
            if chunks:
                added = chroma_manager.add_chunks(chunks)
                total_chunks += added
                logger.info(f"Seed yüklendi: '{raw_doc.title}' ({added} chunk)")

    logger.info(f"Tüm seed yüklemeleri tamamlandı. Toplam chunk sayısı: {total_chunks}")
    return total_chunks


if __name__ == "__main__":
    count = load_all_seeds()
    logger.info(f"Başarıyla {count} chunk yüklendi.")

