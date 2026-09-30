"""Dokümanları anlamsal (semantic) parçalara (chunks) bölen işlemci."""

import hashlib
import re
from datetime import datetime, timezone
from game_designer.config import Settings, get_settings
from game_designer.models.document import DocumentChunk, DocumentMetadata, RawDocument
from game_designer.models.taxonomy import Category, get_default_tier_for_source
from game_designer.utils.logger import logger
from game_designer.utils.text_utils import clean_text


class DocumentProcessor:
    """Doküman temizleme ve anlamsal chunking sınıfı."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def process_document(self, raw_doc: RawDocument) -> list[DocumentChunk]:
        """Ham dokümanı işler, temizler ve semantik parçalara ayırır.

        Args:
            raw_doc: İşlenecek ham döküman.

        Returns:
            Oluşturulan DocumentChunk listesi.
        """
        cleaned_content = clean_text(raw_doc.content)
        if not cleaned_content:
            logger.warning(f"Doküman içeriği boş: {raw_doc.title}")
            return []

        # Doküman bazlı hash tabanı oluştur
        doc_base_id = hashlib.sha256(
            f"{raw_doc.title}:{raw_doc.source_url or ''}".encode("utf-8")
        ).hexdigest()[:12]

        chunks_text = self._semantic_split(cleaned_content)
        processed_chunks: list[DocumentChunk] = []

        reliability_tier = get_default_tier_for_source(raw_doc.source_type)
        normalized_tags = self._normalize_tags(raw_doc.tags, raw_doc.category, raw_doc.subcategory)

        assigned_genres = list(raw_doc.game_genres)
        if not assigned_genres:
            known_genres = ["platformer", "rpg", "fps", "roguelike", "roguelite", "puzzle", "strategy", "moba", "survival", "horror", "simulation", "metroidvania", "deckbuilder"]
            for g in known_genres:
                if any(g == t.lower() for t in raw_doc.tags) or g in raw_doc.title.lower():
                    if g not in assigned_genres:
                        assigned_genres.append(g)

        assigned_engines = list(raw_doc.game_engines)
        if not assigned_engines:
            known_engines = ["unity", "unreal", "godot", "gamemaker", "defold", "bevy", "roblox"]
            for e in known_engines:
                if any(e == t.lower() for t in raw_doc.tags) or e in raw_doc.title.lower():
                    if e not in assigned_engines:
                        assigned_engines.append(e)

        for idx, text in enumerate(chunks_text):
            chunk_id = f"{doc_base_id}_{idx:03d}"
            meta = DocumentMetadata(
                category=raw_doc.category,
                subcategory=raw_doc.subcategory,
                tags=normalized_tags,
                source_type=raw_doc.source_type,
                source_url=raw_doc.source_url,
                source_title=raw_doc.title,
                author=raw_doc.author,
                publication_date=raw_doc.publication_date,
                reliability_tier=reliability_tier,
                is_verified=raw_doc.is_verified,
                game_engines=assigned_engines,
                game_genres=assigned_genres,
                chunk_id=chunk_id,
                ingested_at=datetime.now(timezone.utc),
            )

            processed_chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    text=text,
                    metadata=meta,
                )
            )

        logger.info(
            f"Doküman işlendi: '{raw_doc.title}' -> {len(processed_chunks)} chunk oluşturuldu."
        )
        return processed_chunks

    def _semantic_split(self, text: str) -> list[str]:
        """Metni anlamsal bloklar, başlıklar ve paragraflar bazında parçalar."""
        cfg = self.settings.chunking
        min_size = cfg.min_chunk_size
        max_size = cfg.max_chunk_size
        overlap = cfg.overlap

        # Markdown başlıklarını tanı: #, ##, ###
        lines = text.splitlines()
        sections: list[tuple[str, str]] = []  # (heading, section_text)
        current_heading = "Giriş"
        current_lines: list[str] = []

        for line in lines:
            line_str = line.strip()
            heading_match = re.match(r"^(#{1,4})\s+(.+)$", line_str)
            if heading_match:
                if current_lines:
                    sections.append((current_heading, "\n".join(current_lines)))
                    current_lines = []
                current_heading = heading_match.group(2).strip()
            else:
                current_lines.append(line)

        if current_lines:
            sections.append((current_heading, "\n".join(current_lines)))

        chunks: list[str] = []

        for heading, section_text in sections:
            paragraphs = [p.strip() for p in section_text.split("\n\n") if p.strip()]
            if not paragraphs:
                continue

            current_chunk_parts: list[str] = []
            current_length = 0

            for para in paragraphs:
                para_len = len(para)

                # Çok uzun paragrafları cümlelere böl
                if para_len > max_size:
                    sentences = re.split(r"(?<=[.!?])\s+", para)
                    for sent in sentences:
                        sent = sent.strip()
                        if not sent:
                            continue
                        if current_length + len(sent) > max_size and current_chunk_parts:
                            chunk_str = "\n\n".join(current_chunk_parts)
                            if cfg.preserve_headings and heading:
                                chunk_str = f"[{heading}]\n{chunk_str}"
                            chunks.append(chunk_str)
                            # Overlap için son parçayı koru
                            last_part = current_chunk_parts[-1]
                            overlap_str = last_part[-overlap:] if len(last_part) > overlap else last_part
                            current_chunk_parts = [overlap_str, sent]
                            current_length = len(overlap_str) + len(sent)
                        else:
                            current_chunk_parts.append(sent)
                            current_length += len(sent)
                else:
                    if current_length + para_len > max_size and current_chunk_parts:
                        chunk_str = "\n\n".join(current_chunk_parts)
                        if cfg.preserve_headings and heading:
                            chunk_str = f"[{heading}]\n{chunk_str}"
                        chunks.append(chunk_str)
                        last_part = current_chunk_parts[-1]
                        overlap_str = last_part[-overlap:] if len(last_part) > overlap else last_part
                        current_chunk_parts = [overlap_str, para]
                        current_length = len(overlap_str) + para_len
                    else:
                        current_chunk_parts.append(para)
                        current_length += para_len

            if current_chunk_parts:
                chunk_str = "\n\n".join(current_chunk_parts)
                # min_size kontrolü: eğer chunk çok küçükse ve önceki chunk varsa birleştirmeyi dene
                if len(chunk_str) < min_size and chunks:
                    prev = chunks.pop()
                    combined = f"{prev}\n\n{chunk_str}"
                    if len(combined) <= max_size * 1.2:
                        chunks.append(combined)
                    else:
                        chunks.append(prev)
                        if cfg.preserve_headings and heading:
                            chunk_str = f"[{heading}]\n{chunk_str}"
                        chunks.append(chunk_str)
                else:
                    if cfg.preserve_headings and heading:
                        chunk_str = f"[{heading}]\n{chunk_str}"
                    chunks.append(chunk_str)

        return chunks if chunks else [text]

    def _normalize_tags(self, tags: list[str], category: Category, subcategory: str) -> list[str]:
        """Etiketleri kurallar.md gereğince en az 2, en fazla 10 etiket olacak şekilde normalize eder."""
        cleaned_tags: list[str] = []
        for t in tags:
            clean = re.sub(r"[^\w\-]", "_", t.strip().lower())
            if clean and clean not in cleaned_tags:
                cleaned_tags.append(clean)

        # En az 2 etiket sağla
        if len(cleaned_tags) < 2:
            cat_tag = category.value if isinstance(category, Category) else str(category)
            if cat_tag not in cleaned_tags:
                cleaned_tags.append(cat_tag)
        if len(cleaned_tags) < 2:
            sub_tag = re.sub(r"[^\w\-]", "_", subcategory.strip().lower())
            if sub_tag and sub_tag not in cleaned_tags:
                cleaned_tags.append(sub_tag)
        if len(cleaned_tags) < 2:
            cleaned_tags.append("game_design")

        # En fazla 10 etiket sınırla
        return cleaned_tags[:10]
