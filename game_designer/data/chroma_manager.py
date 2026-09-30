"""ChromaDB vektör veritabanı CRUD ve hibrit arama yöneticisi."""

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path
from typing import Any
import numpy as np

from game_designer.config import Settings, get_settings
from game_designer.data.embedding_manager import EmbeddingManager
from game_designer.models.document import DocumentChunk, DocumentMetadata
from game_designer.models.query import RetrievedChunk
from game_designer.models.taxonomy import Category
from game_designer.utils.logger import logger
from game_designer.utils.text_utils import extract_keywords, lexical_similarity


class ChromaManager:
    """ChromaDB ve yerel vektör depolama yöneticisi."""

    COLLECTION_NAME = "game_design_knowledge"

    def __init__(
        self,
        settings: Settings | None = None,
        embedding_manager: EmbeddingManager | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.embedding_manager = embedding_manager or EmbeddingManager(self.settings)
        self.db_dir = self.settings.chroma_db_dir
        self.db_dir.mkdir(parents=True, exist_ok=True)

        self._client: Any = None
        self._collection: Any = None
        self._use_chroma = False

        # Yerel yedek depolama (chromadb kütüphanesi hazır değilse veya hata verirse)
        self._fallback_store_file = self.db_dir / "local_vector_store.json"
        self._fallback_docs: dict[str, dict[str, Any]] = {}

        self._initialize_db()

    def _initialize_db(self) -> None:
        """Veritabanını başlatır. ChromaDB mevcutsa onu, değilse yerel depoyu açar."""
        try:
            import chromadb
            from chromadb.config import Settings as ChromaSettings

            logger.info(f"ChromaDB PersistentClient başlatılıyor: {self.db_dir}")
            self._client = chromadb.PersistentClient(
                path=str(self.db_dir),
                settings=ChromaSettings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=self.COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            self._use_chroma = True
            logger.info("ChromaDB koleksiyonu hazır.")
        except ImportError:
            logger.warning("chromadb paketi bulunamadı. Yerel gömülü vektör depolama kullanılıyor.")
            self._init_fallback_store()
        except Exception as e:
            logger.error(f"ChromaDB başlatılırken hata: {e}. Yerel gömülü depolamaya geçiliyor.")
            self._init_fallback_store()

    def _init_fallback_store(self) -> None:
        """ChromaDB olmadığında JSON tabanlı yerel vektör deposunu başlatır."""
        self._use_chroma = False
        if self._fallback_store_file.exists():
            try:
                with open(self._fallback_store_file, "r", encoding="utf-8") as f:
                    self._fallback_docs = json.load(f)
            except Exception as e:
                logger.error(f"Yerel depo okunamadı: {e}")
                self._fallback_docs = {}
        else:
            self._fallback_docs = {}

    def _save_fallback_store(self) -> None:
        """Yerel depoyu diske yazar."""
        try:
            with open(self._fallback_store_file, "w", encoding="utf-8") as f:
                json.dump(self._fallback_docs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Yerel depo kaydedilirken hata: {e}")

    def pre_warm(self) -> None:
        """Embedding modelini ve vektör deposunu önceden ısıtır."""
        try:
            self.embedding_manager.pre_warm()
        except Exception as e:
            logger.warning(f"ChromaManager ön ısıtma uyarısı: {e}")

    def add_chunks(self, chunks: list[DocumentChunk]) -> int:
        """Doküman parçalarını vektör veritabanına ekler veya günceller.

        Args:
            chunks: Eklenecek DocumentChunk listesi.

        Returns:
            Eklenen parça sayısı.
        """
        if not chunks:
            return 0

        # Embedding'i eksik olan parçalar için embedding üret
        missing_texts = [c.text for c in chunks if c.embedding is None]
        if missing_texts:
            computed_embeddings = self.embedding_manager.embed_batch(missing_texts)
            comp_idx = 0
            for c in chunks:
                if c.embedding is None:
                    c.embedding = computed_embeddings[comp_idx]
                    comp_idx += 1

        ids = [c.chunk_id for c in chunks]
        texts = [c.text for c in chunks]
        metadatas = [c.metadata.to_chroma_metadata() for c in chunks]
        embeddings = [c.embedding for c in chunks]

        if self._use_chroma and self._collection is not None:
            try:
                self._collection.upsert(
                    ids=ids,
                    documents=texts,
                    metadatas=metadatas,
                    embeddings=embeddings,
                )
                logger.info(f"{len(chunks)} parça ChromaDB'ye kaydedildi.")
                return len(chunks)
            except Exception as e:
                logger.error(f"ChromaDB upsert hatası: {e}. Fallback depoya yazılıyor.")

        # Fallback yazma
        for c in chunks:
            self._fallback_docs[c.chunk_id] = {
                "text": c.text,
                "metadata": c.metadata.to_chroma_metadata(),
                "embedding": c.embedding,
            }
        self._save_fallback_store()
        logger.info(f"{len(chunks)} parça yerel depoya kaydedildi.")
        return len(chunks)

    def get_chunk(self, chunk_id: str) -> DocumentChunk | None:
        """ID ile tek bir parçayı getirir."""
        if self._use_chroma and self._collection is not None:
            try:
                res = self._collection.get(ids=[chunk_id], include=["documents", "metadatas", "embeddings"])
                if res and res.get("ids") and len(res["ids"]) > 0:
                    text = res["documents"][0]
                    meta_dict = res["metadatas"][0]
                    emb = res["embeddings"][0] if res.get("embeddings") is not None and len(res["embeddings"]) > 0 else None
                    metadata = DocumentMetadata.from_chroma_metadata(meta_dict)
                    return DocumentChunk(chunk_id=chunk_id, text=text, metadata=metadata, embedding=emb)
            except Exception as e:
                logger.error(f"ChromaDB get hatası: {e}")

        if chunk_id in self._fallback_docs:
            d = self._fallback_docs[chunk_id]
            meta = DocumentMetadata.from_chroma_metadata(d["metadata"])
            return DocumentChunk(chunk_id=chunk_id, text=d["text"], metadata=meta, embedding=d.get("embedding"))

        return None

    def delete_chunk(self, chunk_id: str) -> bool:
        """ID'ye göre bir parçayı siler."""
        success = False
        if self._use_chroma and self._collection is not None:
            try:
                self._collection.delete(ids=[chunk_id])
                success = True
            except Exception as e:
                logger.error(f"ChromaDB delete hatası: {e}")

        if chunk_id in self._fallback_docs:
            del self._fallback_docs[chunk_id]
            self._save_fallback_store()
            success = True

        return success

    def count(self) -> int:
        """Veritabanındaki toplam parça sayısını döndürür."""
        if self._use_chroma and self._collection is not None:
            try:
                return self._collection.count()
            except Exception as e:
                logger.error(f"ChromaDB count hatası: {e}")

        return len(self._fallback_docs)

    def search(
        self,
        query_embedding: list[float],
        top_k: int = 10,
        category: Category | None = None,
        engine: str | None = None,
        genre: str | None = None,
    ) -> list[RetrievedChunk]:
        """Vektör benzerliğine göre arama yapar."""
        where_filter: dict[str, Any] = {}
        if category:
            cat_str = category.value if isinstance(category, Category) else str(category)
            where_filter["category"] = cat_str

        # ChromaDB araması
        if self._use_chroma and self._collection is not None:
            try:
                count = self._collection.count()
                if count == 0:
                    return []
                fetch_k = min(top_k, count)

                kwargs: dict[str, Any] = {
                    "query_embeddings": [query_embedding],
                    "n_results": fetch_k,
                    "include": ["documents", "metadatas", "distances"],
                }
                if where_filter:
                    kwargs["where"] = where_filter

                results = self._collection.query(**kwargs)

                retrieved: list[RetrievedChunk] = []
                if results and results.get("ids") and results["ids"][0]:
                    ids = results["ids"][0]
                    docs = results["documents"][0]
                    metas = results["metadatas"][0]
                    dists = results["distances"][0]

                    for cid, text, meta, dist in zip(ids, docs, metas, dists):
                        # Cosine distance: sim = 1.0 - dist
                        similarity = max(0.0, min(1.0, 1.0 - float(dist)))
                        doc_meta = DocumentMetadata.from_chroma_metadata(meta)

                        # Opsiyonel filtreler
                        if engine and doc_meta.game_engines and engine.lower() not in [e.lower() for e in doc_meta.game_engines] and engine.lower() not in [t.lower() for t in doc_meta.tags]:
                            continue
                        if genre and doc_meta.game_genres and genre.lower() not in [g.lower() for g in doc_meta.game_genres] and genre.lower() not in [t.lower() for t in doc_meta.tags] and genre.lower() not in doc_meta.source_title.lower():
                            continue

                        retrieved.append(
                            RetrievedChunk(
                                chunk_id=cid,
                                text=text,
                                score=round(similarity, 4),
                                metadata=doc_meta,
                            )
                        )
                return retrieved
            except Exception as e:
                logger.error(f"ChromaDB search hatası: {e}. Fallback arama yapılıyor.")

        # Fallback vektör araması
        return self._fallback_search(query_embedding, top_k, category, engine, genre)

    def _fallback_search(
        self,
        query_embedding: list[float],
        top_k: int,
        category: Category | None,
        engine: str | None,
        genre: str | None,
    ) -> list[RetrievedChunk]:
        """Yerel depoda Cosine benzerliği ile arama yapar."""
        if not self._fallback_docs:
            return []

        q_vec = np.array(query_embedding, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm == 0:
            return []

        candidates: list[tuple[float, str, dict[str, Any]]] = []

        for cid, data in self._fallback_docs.items():
            meta = data["metadata"]
            if category:
                cat_str = category.value if isinstance(category, Category) else str(category)
                if meta.get("category") != cat_str:
                    continue

            emb = data.get("embedding")
            if not emb:
                continue

            d_vec = np.array(emb, dtype=np.float32)
            d_norm = np.linalg.norm(d_vec)
            if d_norm == 0:
                sim = 0.0
            else:
                sim = float(np.dot(q_vec, d_vec) / (q_norm * d_norm))

            candidates.append((sim, cid, data))

        candidates.sort(key=lambda x: x[0], reverse=True)
        retrieved: list[RetrievedChunk] = []

        for sim, cid, data in candidates[:top_k]:
            doc_meta = DocumentMetadata.from_chroma_metadata(data["metadata"])
            if engine and doc_meta.game_engines and engine.lower() not in [e.lower() for e in doc_meta.game_engines] and engine.lower() not in [t.lower() for t in doc_meta.tags]:
                continue
            if genre and doc_meta.game_genres and genre.lower() not in [g.lower() for g in doc_meta.game_genres] and genre.lower() not in [t.lower() for t in doc_meta.tags] and genre.lower() not in doc_meta.source_title.lower():
                continue

            retrieved.append(
                RetrievedChunk(
                    chunk_id=cid,
                    text=data["text"],
                    score=round(max(0.0, min(1.0, sim)), 4),
                    metadata=doc_meta,
                )
            )

        return retrieved

    def keyword_search(
        self,
        query_text: str,
        top_k: int = 10,
        category: Category | None = None,
        engine: str | None = None,
        genre: str | None = None,
    ) -> list[RetrievedChunk]:
        """Kelime benzerliği (lexical / BM25 mantığı) ile aday dokümanları arar."""
        candidates: list[tuple[float, str, str, DocumentMetadata, list[float] | None]] = []

        if self._use_chroma and self._collection is not None:
            try:
                where_filter: dict[str, Any] = {}
                if category:
                    cat_str = category.value if isinstance(category, Category) else str(category)
                    where_filter["category"] = cat_str

                kwargs: dict[str, Any] = {
                    "include": ["documents", "metadatas", "embeddings"],
                }
                if where_filter:
                    kwargs["where"] = where_filter

                res = self._collection.get(**kwargs)
                if res and res.get("ids"):
                    ids = res["ids"]
                    docs = res["documents"]
                    metas = res["metadatas"]
                    embs = res.get("embeddings")

                    for idx, (cid, text, meta) in enumerate(zip(ids, docs, metas)):
                        doc_meta = DocumentMetadata.from_chroma_metadata(meta)
                        if engine and doc_meta.game_engines and engine.lower() not in [e.lower() for e in doc_meta.game_engines] and engine.lower() not in [t.lower() for t in doc_meta.tags]:
                            continue
                        if genre and doc_meta.game_genres and genre.lower() not in [g.lower() for g in doc_meta.game_genres] and genre.lower() not in [t.lower() for t in doc_meta.tags] and genre.lower() not in doc_meta.source_title.lower():
                            continue

                        lex = lexical_similarity(query_text, text)
                        if lex > 0.05:
                            emb = embs[idx] if embs is not None and idx < len(embs) else None
                            candidates.append((lex, cid, text, doc_meta, emb))
            except Exception as e:
                logger.error(f"ChromaDB keyword_search hatası: {e}")

        # Fallback deponun kontrolü
        for cid, data in self._fallback_docs.items():
            meta = data["metadata"]
            if category:
                cat_str = category.value if isinstance(category, Category) else str(category)
                if meta.get("category") != cat_str:
                    continue

            doc_meta = DocumentMetadata.from_chroma_metadata(meta)
            if engine and doc_meta.game_engines and engine.lower() not in [e.lower() for e in doc_meta.game_engines] and engine.lower() not in [t.lower() for t in doc_meta.tags]:
                continue
            if genre and doc_meta.game_genres and genre.lower() not in [g.lower() for g in doc_meta.game_genres] and genre.lower() not in [t.lower() for t in doc_meta.tags] and genre.lower() not in doc_meta.source_title.lower():
                continue

            lex = lexical_similarity(query_text, data["text"])
            if lex > 0.05:
                # Varsa tekrar ekleme
                if not any(c[1] == cid for c in candidates):
                    candidates.append((lex, cid, data["text"], doc_meta, data.get("embedding")))

        candidates.sort(key=lambda x: x[0], reverse=True)
        retrieved: list[RetrievedChunk] = []
        for lex, cid, text, meta, _ in candidates[:top_k]:
            retrieved.append(
                RetrievedChunk(
                    chunk_id=cid,
                    text=text,
                    score=round(lex, 4),
                    metadata=meta,
                )
            )
        return retrieved

    def hybrid_search(
        self,
        query_text: str,
        query_embedding: list[float] | None = None,
        top_k: int = 10,
        category: Category | None = None,
        engine: str | None = None,
        genre: str | None = None,
    ) -> list[RetrievedChunk]:
        """Semantik ve kelime bazlı (lexical) gerçek hibrit arama gerçekleştirir.

        Vektör arama ve kelime arama adayları birleştirilir (union),
        Score = alpha * semantic_score + (1 - alpha) * lexical_score
        """
        cfg = self.settings.retrieval
        alpha = cfg.hybrid_alpha
        threshold = cfg.similarity_threshold

        if query_embedding is None:
            query_embedding = self.embedding_manager.embed_text(query_text)

        pool_k = max(top_k * 2, 10)

        # 1. Vektör tabanlı semantik adaylar
        vector_results = self.search(
            query_embedding=query_embedding,
            top_k=pool_k,
            category=category,
            engine=engine,
            genre=genre,
        )

        # 2. Anahtar kelime / leksikal adaylar
        keyword_results = self.keyword_search(
            query_text=query_text,
            top_k=pool_k,
            category=category,
            engine=engine,
            genre=genre,
        )

        # 3. Aday havuzunu birleştir (Union)
        candidates_map: dict[str, tuple[RetrievedChunk, float, float]] = {}  # chunk_id -> (chunk, sem_score, lex_score)

        for chunk in vector_results:
            lex_score = lexical_similarity(query_text, chunk.text)
            candidates_map[chunk.chunk_id] = (chunk, chunk.score, lex_score)

        for chunk in keyword_results:
            if chunk.chunk_id in candidates_map:
                # Halihazırda var, leksikal skoru güncelle
                orig_chunk, sem_score, _ = candidates_map[chunk.chunk_id]
                candidates_map[chunk.chunk_id] = (orig_chunk, sem_score, chunk.score)
            else:
                # Vektör aramasında çıkmamış ama anahtar kelimede yakalanmış aday
                # Semantik benzerliği hesapla
                sem_score = 0.0
                stored = self.get_chunk(chunk.chunk_id)
                if stored and stored.embedding and query_embedding:
                    q_vec = np.array(query_embedding, dtype=np.float32)
                    d_vec = np.array(stored.embedding, dtype=np.float32)
                    q_norm = np.linalg.norm(q_vec)
                    d_norm = np.linalg.norm(d_vec)
                    if q_norm > 0 and d_norm > 0:
                        sem_score = max(0.0, min(1.0, float(np.dot(q_vec, d_vec) / (q_norm * d_norm))))
                candidates_map[chunk.chunk_id] = (chunk, sem_score, chunk.score)

        # 4. Hibrit skorları hesapla
        hybrid_results: list[RetrievedChunk] = []
        for chunk_id, (chunk, sem_score, lex_score) in candidates_map.items():
            standard_hybrid = (alpha * sem_score) + ((1.0 - alpha) * lex_score)
            keyword_boosted = (0.4 * sem_score) + (0.6 * lex_score)
            combined_score = round(max(standard_hybrid, keyword_boosted), 4)

            # Eşik kontrolü
            if combined_score >= threshold or sem_score >= threshold or lex_score >= threshold:
                chunk.score = round(max(combined_score, lex_score, sem_score), 4)
                hybrid_results.append(chunk)

        hybrid_results.sort(key=lambda c: c.score, reverse=True)
        return hybrid_results[:top_k]

    def deduplicate_chunks(self) -> int:
        """Veritabanındaki mükerrer (duplicate) doküman parçalarını temizler."""
        logger.info("ChromaManager: Mükerrer kayıt temizliği başlatılıyor...")
        removed_count = 0
        seen_hashes: dict[str, str] = {}  # sha256_hash -> chunk_id

        # Fallback deponun taranması
        to_delete: list[str] = []
        for cid, data in self._fallback_docs.items():
            text = data["text"].strip().lower()
            text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
            if text_hash in seen_hashes:
                to_delete.append(cid)
            else:
                seen_hashes[text_hash] = cid

        for cid in to_delete:
            self.delete_chunk(cid)
            removed_count += 1

        if self._use_chroma and self._collection is not None:
            try:
                res = self._collection.get(include=["documents"])
                if res and res.get("ids"):
                    ids = res["ids"]
                    docs = res["documents"]
                    chroma_to_delete = []
                    c_seen = {}
                    for cid, doc_text in zip(ids, docs):
                        h = hashlib.sha256(doc_text.strip().lower().encode("utf-8")).hexdigest()
                        if h in c_seen:
                            chroma_to_delete.append(cid)
                        else:
                            c_seen[h] = cid
                    if chroma_to_delete:
                        self._collection.delete(ids=chroma_to_delete)
                        removed_count += len(chroma_to_delete)
            except Exception as e:
                logger.error(f"ChromaDB tekilleştirme hatası: {e}")

        logger.info(f"Tekilleştirme tamamlandı. Kaldırılan mükerrer parça sayısı: {removed_count}")
        return removed_count

    def update_stale_scores(self) -> int:
        """Eski veya doğrulanmamış kaynakların meta verilerini gözden geçirir (1 yıldan eski veriler)."""
        logger.info("ChromaManager: Eski kaynak skorları güncelleniyor...")
        updated_count = 0
        one_year_ago = date.today() - timedelta(days=365)

        # 1. Fallback JSON depodaki dokümanları güncelle
        for cid, data in self._fallback_docs.items():
            meta = data.get("metadata", {})
            pub_date_raw = meta.get("publication_date")
            if pub_date_raw:
                try:
                    pub_date = date.fromisoformat(str(pub_date_raw)[:10])
                    if pub_date < one_year_ago and not meta.get("is_stale"):
                        meta["is_stale"] = True
                        updated_count += 1
                except ValueError:
                    pass

        # 2. ChromaDB koleksiyonundaki dokümanları güncelle (aktifse)
        if self._use_chroma and self._collection is not None:
            try:
                res = self._collection.get(include=["metadatas"])
                if res and res.get("ids"):
                    ids = res["ids"]
                    metas = res["metadatas"]
                    chroma_ids_to_update = []
                    chroma_metas_to_update = []
                    for cid, meta in zip(ids, metas):
                        pub_date_raw = meta.get("publication_date")
                        if pub_date_raw:
                            try:
                                pub_date = date.fromisoformat(str(pub_date_raw)[:10])
                                if pub_date < one_year_ago and not meta.get("is_stale"):
                                    meta["is_stale"] = True
                                    chroma_ids_to_update.append(cid)
                                    chroma_metas_to_update.append(meta)
                                    updated_count += 1
                            except ValueError:
                                pass
                    if chroma_ids_to_update:
                        self._collection.update(
                            ids=chroma_ids_to_update,
                            metadatas=chroma_metas_to_update,
                        )
            except Exception as e:
                logger.error(f"ChromaDB stale skorları güncellenirken hata: {e}")

        if updated_count > 0:
            self._save_fallback_store()

        logger.info(f"ChromaManager: {updated_count} eski kaynak güncellendi.")
        return updated_count

    def compact_database(self) -> None:
        """Veritabanı disk dosyalarını optimize eder ve kaydeder."""
        logger.info("ChromaManager: Veritabanı sıkıştırma ve optimizasyonu başlatıldı...")
        self._save_fallback_store()
        logger.info("ChromaManager: Veritabanı optimizasyonu tamamlandı.")

    def reset(self) -> None:
        """Tüm veritabanı koleksiyonunu sıfırlar."""
        if self._use_chroma and self._client is not None:
            try:
                self._client.delete_collection(self.COLLECTION_NAME)
                self._collection = self._client.create_collection(
                    name=self.COLLECTION_NAME,
                    metadata={"hnsw:space": "cosine"},
                )
            except Exception as e:
                logger.error(f"ChromaDB reset hatası: {e}")

        self._fallback_docs.clear()
        if self._fallback_store_file.exists():
            self._fallback_store_file.unlink()
        logger.info("Vektör veritabanı sıfırlandı.")

