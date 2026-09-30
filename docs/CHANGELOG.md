# 📝 Değişiklik Günlüğü (Changelog)

## [0.1.0] - 2026-09-27
### Eklendi
- İlk sürüm mimarisi kuruldu.
- Pydantic v2 tabanlı veri modelleri (`taxonomy`, `document`, `query`, `response`, `user_profile`).
- Pydantic Settings ile konfigürasyon yönetimi (`config.py`).
- Merkezi loglama ve metin işleme araçları (`utils/`).
- Offline embedding yöneticisi ve semantik chunking döküman işlemcisi (`data/`).
- ChromaDB ve dayanıklı yerel vektör depolama yöneticisi (`ChromaManager`).
- 8 etkileşim modu: Soru-Cevap, Analiz, Beyin Fırtınası, Karşılaştırma, GDD, Brifing, Danışman, Pazar Analizi (`modes/`).
- Anti-halüsinasyon kuralları ve Güvenilirlik Puanlama Sistemi (`ConfidenceScorer`).
- RAG orkestrasyon motoru (`RagEngine`).
- Etik web kazıma ve APScheduler zamanlayıcı (`scraper/`).
- Başlangıç veri kütüphanesi (Schell, Salen & Zimmerman, Koster, MDA, Machinations, Glossary) ve seed loader (`seeds/`).
- Jarvis Core plugin arayüzü ve test suite (`tests/`).
