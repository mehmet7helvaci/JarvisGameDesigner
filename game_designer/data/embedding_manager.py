"""Offline embedding yönetimi (Sentence-Transformers ve yerel yedek vektörleyici)."""

import hashlib
import math
import re
from typing import Sequence
import numpy as np

from game_designer.config import Settings, get_settings
from game_designer.utils.language_utils import get_english_terms_for_query
from game_designer.utils.logger import logger


class EmbeddingManager:
    """Metin embedding'lerini yerel ve çevrimdışı olarak üreten yönetici sınıfı."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._model = None
        self._dimension = 384  # all-MiniLM-L6-v2 boyutu
        self._cache: dict[str, list[float]] = {}
        self._is_transformer_model = False

    @property
    def dimension(self) -> int:
        """Embedding vektör boyutu."""
        return self._dimension

    def _load_model_if_needed(self) -> None:
        """Lazy loading: Model ilk kullanım anında yüklenir."""
        if self._model is not None:
            return

        model_name = self.settings.embedding.model
        device = self.settings.embedding.device

        try:
            from sentence_transformers import SentenceTransformer

            logger.info(f"SentenceTransformer modeli yükleniyor: {model_name} (cihaz: {device})")
            self._model = SentenceTransformer(model_name, device=device)
            self._dimension = self._model.get_sentence_embedding_dimension()
            self._is_transformer_model = True
            logger.info(f"SentenceTransformer başarıyla yüklendi. Boyut: {self._dimension}")
        except ImportError:
            logger.warning(
                "sentence-transformers kütüphanesi bulunamadı! "
                "Yerel deterministik simülasyon embedding motoru aktif ediliyor."
            )
            self._model = "fallback_hasher"
            self._is_transformer_model = False
        except Exception as e:
            logger.error(f"Embedding modeli yüklenirken hata oluştu: {e}. Yerel yedek vektörleyici kullanılacak.")
            self._model = "fallback_hasher"
            self._is_transformer_model = False

    def pre_warm(self) -> None:
        """Embedding modelini ve önbelleği önceden ısıtarak ilk sorgudaki gecikmeyi sıfırlar."""
        try:
            self._load_model_if_needed()
            self.embed_text("game design mechanics and 3d animation pipeline")
            logger.info("Embedding modeli başarıyla önceden ısıtıldı (pre-warmed).")
        except Exception as e:
            logger.warning(f"Embedding ön ısıtma uyarısı: {e}")

    def _fallback_embed(self, text: str) -> list[float]:
        """Sentence-transformers yüklenemediğinde veya offline çalışırken deterministik vektör üretir."""
        vec = np.zeros(self._dimension, dtype=np.float32)
        tokens = re.findall(r"\b[a-zA-ZçğıöşüÇĞİÖŞÜ0-9_\-]{2,}\b", text.lower())
        # Türkçe sorgular için İngilizce terim karşılıklarını da vektöre dahil et
        for en_t in get_english_terms_for_query(text):
            for sub_t in re.findall(r"\b[a-zA-Z0-9_\-]{2,}\b", en_t.lower()):
                tokens.append(sub_t)

        if not tokens:
            return vec.tolist()

        for token in tokens:
            # Token bazlı kararlı hash üret
            h = int(hashlib.md5(token.encode("utf-8")).hexdigest(), 16)
            idx = h % self._dimension
            weight = 1.0 + (h % 5) * 0.2
            vec[idx] += weight

        # L2 Normalizasyonu
        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec.tolist()

    def embed_text(self, text: str) -> list[float]:
        """Tek bir metnin embedding vektörünü döndürür.

        Args:
            text: Vektörleştirilecek metin.

        Returns:
            Normalleştirilmiş float vektör listesi.
        """
        text_clean = text.strip()
        if not text_clean:
            return [0.0] * self._dimension

        # Önbellek kontrolü
        cache_key = hashlib.sha256(text_clean.encode("utf-8")).hexdigest()
        if cache_key in self._cache:
            return self._cache[cache_key]

        self._load_model_if_needed()

        if self._is_transformer_model and hasattr(self._model, "encode"):
            try:
                embedding = self._model.encode(
                    text_clean,
                    normalize_embeddings=self.settings.embedding.normalize_embeddings,
                    show_progress_bar=False,
                )
                if hasattr(embedding, "tolist"):
                    res = embedding.tolist()
                else:
                    res = list(embedding)
            except Exception as e:
                logger.error(f"Transformer encode hatası: {e}. Fallback vektörleme uygulanıyor.")
                res = self._fallback_embed(text_clean)
        else:
            res = self._fallback_embed(text_clean)

        # Basit LRU koruma (maksimum 5000 embedding önbelleği)
        if len(self._cache) > 5000:
            self._cache.clear()

        self._cache[cache_key] = res
        return res

    def embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        """Birden çok metni toplu (batch) olarak embed eder.

        Args:
            texts: Metin listesi.

        Returns:
            Embedding vektörleri listesi.
        """
        if not texts:
            return []

        results: list[list[float]] = []
        texts_to_compute_indices: list[int] = []
        texts_to_compute: list[str] = []

        # Önbellekten bak
        for i, t in enumerate(texts):
            clean_t = t.strip()
            key = hashlib.sha256(clean_t.encode("utf-8")).hexdigest()
            if key in self._cache:
                results.append(self._cache[key])
            else:
                results.append([])
                texts_to_compute_indices.append(i)
                texts_to_compute.append(clean_t)

        if not texts_to_compute:
            return results

        self._load_model_if_needed()

        batch_size = self.settings.embedding.batch_size
        computed_embeddings: list[list[float]] = []

        if self._is_transformer_model and hasattr(self._model, "encode"):
            try:
                for b_start in range(0, len(texts_to_compute), batch_size):
                    batch = texts_to_compute[b_start : b_start + batch_size]
                    batch_res = self._model.encode(
                        batch,
                        batch_size=batch_size,
                        normalize_embeddings=self.settings.embedding.normalize_embeddings,
                        show_progress_bar=False,
                    )
                    for emb in batch_res:
                        computed_embeddings.append(emb.tolist() if hasattr(emb, "tolist") else list(emb))
            except Exception as e:
                logger.error(f"Batch embedding hatası: {e}. Fallback üretiliyor.")
                computed_embeddings = [self._fallback_embed(t) for t in texts_to_compute]
        else:
            computed_embeddings = [self._fallback_embed(t) for t in texts_to_compute]

        # Sonuçları eşle ve önbelleğe al
        for orig_idx, emb in zip(texts_to_compute_indices, computed_embeddings):
            results[orig_idx] = emb
            key = hashlib.sha256(texts[orig_idx].strip().encode("utf-8")).hexdigest()
            self._cache[key] = emb

        return results
