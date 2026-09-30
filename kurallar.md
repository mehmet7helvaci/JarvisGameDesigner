# 🎮 Jarvis Game Designer — Geliştirme Kuralları ve Mimari Rehber

> **Bu doküman nedir?**
> Jarvis AI asistanının "Game Design" modülünü geliştirmek için oluşturulmuş kapsamlı bir kural ve mimari şablondur.
> Hem insan geliştiriciler hem de yapay zeka asistanları (Claude, Gemini, GPT vb.) bu dokümanı okuyarak
> projenin vizyonunu, teknik kararlarını ve kodlama standartlarını anlayabilir.

---

## 📋 İçindekiler

1. [Proje Tanımı ve Vizyon](#1-proje-tanımı-ve-vizyon)
2. [Teknik Altyapı Kararları](#2-teknik-altyapı-kararları)
3. [Mimari Yapı](#3-mimari-yapı)
4. [Dizin Yapısı](#4-dizin-yapısı)
5. [Bilgi Tabanı Taksonomisi](#5-bilgi-tabanı-taksonomisi)
6. [RAG Pipeline Kuralları](#6-rag-pipeline-kuralları)
7. [Anti-Halüsinasyon Kuralları](#7-anti-halüsinasyon-kuralları)
8. [Etkileşim Modları](#8-etkileşim-modları)
9. [Veri Toplama Kuralları](#9-veri-toplama-kuralları)
10. [Kullanıcı Profili ve Hafıza Sistemi](#10-kullanıcı-profili-ve-hafıza-sistemi)
11. [Plugin Mimarisi](#11-plugin-mimarisi)
12. [Kodlama Standartları](#12-kodlama-standartları)
13. [Güvenlik ve Etik Kurallar](#13-güvenlik-ve-etik-kurallar)
14. [Test Stratejisi](#14-test-stratejisi)
15. [Performans ve Ölçeklendirme](#15-performans-ve-ölçeklendirme)
16. [Yapay Zeka Asistanları İçin Özel Talimatlar](#16-yapay-zeka-asistanları-için-özel-talimatlar)

---

## 1. Proje Tanımı ve Vizyon

### 1.1 Ne Yapıyoruz?
**Jarvis Game Designer**, Jarvis adlı Python tabanlı yapay zeka asistanının bir **plugin modülü** olarak çalışan,
oyun tasarımı (game design) konusunda uzmanlaşmış bir bilgi yardımcısıdır.

### 1.2 Temel Hedefler
| Hedef | Açıklama |
|-------|----------|
| **Halüsinasyonsuz Cevaplar** | Tüm cevaplar doğrulanmış kaynaklara dayanmalı, uydurma bilgi verilmemeli |
| **Sürekli Güncellenen Bilgi Tabanı** | İnternetten otomatik + manuel veri toplama ile canlı bir kütüphane |
| **Profesyonel Oyun Tasarımı Rehberliği** | GDC kalitesinde, endüstri standardında tavsiyeler |
| **Aktif Geliştirme Danışmanlığı** | Kullanıcı oyun geliştirirken anlık, bağlama duyarlı tavsiye |
| **Çoklu Motor Desteği** | Unity, Unreal, Godot ve diğer motorlara uyumlu tavsiyeler |
| **Türkçe + İngilizce** | Kaynaklar İngilizce, cevaplar Türkçe (İngilizce terimler korunarak) |

### 1.3 Ne Yapmıyoruz (Kapsam Dışı)
- ❌ Kod yazmıyoruz (bu bir tasarım danışmanı, kodlama asistanı değil)
- ❌ Görsel/ses üretmiyoruz (asset generation yok)
- ❌ Gerçek zamanlı oyun çalıştırmıyoruz
- ❌ Telif hakları korunan içerikleri birebir kopyalamıyoruz

---

## 2. Teknik Altyapı Kararları

### 2.1 Teknoloji Yığını (Tech Stack)

```
┌─────────────────────────────────────────────────────┐
│                   Jarvis (Ana Uygulama)              │
│                     Python 3.10+                     │
├─────────────────────────────────────────────────────┤
│              Jarvis Game Designer Plugin              │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────┐ │
│  │  Gemini   │  │ ChromaDB  │  │ Sentence-        │ │
│  │  API      │  │ (Vektör   │  │ Transformers     │ │
│  │ (LLM)     │  │  DB)      │  │ (Offline Embed)  │ │
│  └───────────┘  └───────────┘  └──────────────────┘ │
│  ┌───────────┐  ┌───────────┐  ┌──────────────────┐ │
│  │ Scrapy/   │  │ APSchedul-│  │ Pydantic         │ │
│  │ BS4       │  │ er        │  │ (Doğrulama)      │ │
│  │ (Scraper) │  │ (Zamanlama│  │                  │ │
│  └───────────┘  └───────────┘  └──────────────────┘ │
└─────────────────────────────────────────────────────┘
```

### 2.2 Bağımlılıklar ve Versiyon Kısıtları

| Paket | Minimum Versiyon | Amaç | Notlar |
|-------|-----------------|------|--------|
| `python` | 3.10+ | Dil | Pattern matching, union types |
| `google-genai` | latest | LLM API | Gemini API v2 SDK |
| `chromadb` | 0.5+ | Vektör DB | Local, ücretsiz, internetsiz |
| `sentence-transformers` | 3.0+ | Embedding | Offline embedding modeli |
| `pydantic` | 2.0+ | Veri doğrulama | Strict mode kullanılacak |
| `scrapy` | 2.11+ | Web scraping | Büyük ölçekli tarama |
| `beautifulsoup4` | 4.12+ | HTML parsing | Tekil sayfa parsing |
| `apscheduler` | 3.10+ | Zamanlanmış görevler | Otomatik tarama schedule |
| `requests` | 2.31+ | HTTP istekleri | BS4 ile birlikte |
| `loguru` | 0.7+ | Loglama | Yapılandırılmış loglar |

### 2.3 Neden Bu Seçimler?

**ChromaDB (Vektör DB):**
- ✅ Tamamen local çalışır — internet gerekmez
- ✅ Ücretsiz ve açık kaynak
- ✅ Python-native — ek sunucu/Docker gerekmez
- ✅ `PersistentClient` ile veri disk üzerinde kalıcı saklanır
- ✅ Metadata filtreleme desteği (kategori, etiket bazlı arama)

**Sentence-Transformers (Offline Embedding):**
- ✅ Model bir kez indirilir, sonra tamamen offline çalışır
- ✅ `all-MiniLM-L6-v2` modeli hızlı ve yeterli kalitede
- ✅ GPU varsa CUDA desteği, yoksa CPU'da çalışır
- ✅ Hiçbir veri dışarıya gönderilmez

**Google Gemini API (LLM):**
- ✅ Cevap üretme (generation) için kullanılır
- ✅ Geniş context window
- ✅ Türkçe dil desteği
- ⚠️ İnternet bağlantısı gerektirir (sadece cevap üretme aşamasında)
- ⚠️ Embedding için kullanılMAYACAK (embedding offline olacak)

> **ÖNEMLİ KARAR:** Embedding işlemi `sentence-transformers` ile offline yapılacak.
> Gemini API sadece cevap üretme (generation) aşamasında kullanılacak.
> Bu sayede bilgi tabanı oluşturma ve arama tamamen internetsiz çalışır.

---

## 3. Mimari Yapı

### 3.1 Katmanlı Mimari (Layered Architecture)

```
┌─────────────────────────────────────────────────────────┐
│                    SUNUM KATMANI                         │
│            (Jarvis Plugin Interface)                     │
│  ┌─────────────────────────────────────────────────────┐ │
│  │  GameDesignerPlugin (ana giriş noktası)             │ │
│  │  - query()         → Soru-Cevap                    │ │
│  │  - analyze_game()  → Oyun Analizi                  │ │
│  │  - brainstorm()    → Beyin Fırtınası               │ │
│  │  - compare()       → Karşılaştırma                 │ │
│  │  - create_gdd()    → GDD Oluşturma                 │ │
│  │  - brief()         → Brifing/Özet                  │ │
│  │  - advise()        → Aktif Geliştirme Danışmanlığı │ │
│  │  - market_analysis() → Pazar Analizi               │ │
│  └─────────────────────────────────────────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                    MANTIK KATMANI                         │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │  RAG Engine   │ │ Mode Router  │ │ Confidence       │ │
│  │  (Retrieve +  │ │ (Mod seçici) │ │ Scorer           │ │
│  │   Generate)   │ │              │ │ (Güvenilirlik)   │ │
│  └──────────────┘ └──────────────┘ └──────────────────┘ │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │  Query        │ │ Context      │ │ Response         │ │
│  │  Rewriter     │ │ Builder      │ │ Formatter        │ │
│  │  (Sorgu       │ │ (Bağlam      │ │ (Cevap           │ │
│  │   iyileştirme)│ │  oluşturucu) │ │  biçimlendirici) │ │
│  └──────────────┘ └──────────────┘ └──────────────────┘ │
├─────────────────────────────────────────────────────────┤
│                    VERİ KATMANI                           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────────┐ │
│  │  ChromaDB     │ │ Scraper      │ │ User Profile     │ │
│  │  Manager      │ │ Engine       │ │ Store            │ │
│  │  (Vektör DB)  │ │ (Veri toplama│ │ (Kullanıcı       │ │
│  │              │ │  motoru)     │ │  hafızası)       │ │
│  └──────────────┘ └──────────────┘ └──────────────────┘ │
│  ┌──────────────┐ ┌──────────────┐                      │
│  │  Document     │ │ Scheduler    │                      │
│  │  Processor    │ │ (Zamanlanmış │                      │
│  │  (Döküman     │ │  görevler)   │                      │
│  │   işleme)     │ │              │                      │
│  └──────────────┘ └──────────────┘                      │
└─────────────────────────────────────────────────────────┘
```

### 3.2 Veri Akış Diyagramı

```
Kullanıcı Sorusu
       │
       ▼
┌──────────────┐
│ Mode Router  │ ← Hangi etkileşim modu? (QA, Analiz, Beyin Fırtınası...)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Query        │ ← Sorguyu optimize et (İngilizce'ye çevir, genişlet)
│ Rewriter     │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ ChromaDB     │ ← Hibrit arama: Semantic + Metadata filtreleme
│ Retrieval    │ ← Top-K sonuç getir (varsayılan K=10)
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Re-ranker    │ ← Sonuçları ilgililik skoruna göre yeniden sırala
│              │ ← En iyi 3-5 chunk'ı seç
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Context      │ ← Seçilen chunk'ları + kullanıcı profilini birleştir
│ Builder      │ ← System prompt + context + user query oluştur
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Gemini API   │ ← Grounded cevap üret
│ Generation   │
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Confidence   │ ← Cevabın güvenilirlik skorunu hesapla
│ Scorer       │ ← Kaynak sayısı, benzerlik skoru, context coverage
└──────┬───────┘
       │
       ▼
┌──────────────┐
│ Response     │ ← Türkçe formatlama, kaynak ekleme, skor ekleme
│ Formatter    │
└──────┬───────┘
       │
       ▼
  Kullanıcıya Cevap
  [%87 Güvenilirlik]
  [Kaynaklar: ...]
```

---

## 4. Dizin Yapısı

```
JarvisGameDesigner/
├── kurallar.md                      # ← BU DOSYA (ana rehber)
├── requirements.txt                 # Bağımlılık listesi
├── pyproject.toml                   # Proje metadata ve build ayarları
├── setup.py                         # Kurulum scripti
├── .env.example                     # Ortam değişkenleri şablonu
├── .gitignore
│
├── game_designer/                   # ← ANA PAKET (import edilecek modül)
│   ├── __init__.py                  # Public API: from game_designer import GameDesignerPlugin
│   ├── plugin.py                    # GameDesignerPlugin sınıfı (ana giriş noktası)
│   ├── config.py                    # Konfigürasyon yönetimi (Pydantic Settings)
│   │
│   ├── core/                        # Mantık katmanı
│   │   ├── __init__.py
│   │   ├── rag_engine.py            # RAG pipeline orkestrasyonu
│   │   ├── query_rewriter.py        # Sorgu iyileştirme ve çeviri
│   │   ├── context_builder.py       # Bağlam oluşturucu
│   │   ├── confidence_scorer.py     # Güvenilirlik puanlama
│   │   ├── response_formatter.py    # Cevap biçimlendirici
│   │   └── mode_router.py           # Etkileşim modu yönlendirici
│   │
│   ├── modes/                       # Etkileşim modları
│   │   ├── __init__.py
│   │   ├── base_mode.py             # Tüm modların ABC'si
│   │   ├── qa_mode.py               # Soru-Cevap modu
│   │   ├── analysis_mode.py         # Oyun analiz modu
│   │   ├── brainstorm_mode.py       # Beyin fırtınası modu
│   │   ├── compare_mode.py          # Karşılaştırma modu
│   │   ├── gdd_mode.py              # GDD oluşturucu modu
│   │   ├── briefing_mode.py         # Brifing/özet modu
│   │   ├── advisor_mode.py          # Aktif geliştirme danışmanlığı
│   │   └── market_mode.py           # Pazar analizi modu
│   │
│   ├── data/                        # Veri katmanı
│   │   ├── __init__.py
│   │   ├── chroma_manager.py        # ChromaDB CRUD operasyonları
│   │   ├── document_processor.py    # Doküman chunking ve işleme
│   │   ├── embedding_manager.py     # Embedding üretme (offline)
│   │   └── user_profile.py          # Kullanıcı profili CRUD
│   │
│   ├── scraper/                     # Veri toplama motoru
│   │   ├── __init__.py
│   │   ├── base_scraper.py          # Tüm scraper'ların ABC'si
│   │   ├── gdc_scraper.py           # GDC makaleleri scraper
│   │   ├── gamasutra_scraper.py     # Gamasutra/Game Developer scraper
│   │   ├── blog_scraper.py          # Genel blog scraper
│   │   ├── postmortem_scraper.py    # Post-mortem analiz scraper
│   │   ├── scheduler.py             # APScheduler zamanlanmış görevler
│   │   └── rate_limiter.py          # İstek hız sınırlayıcı
│   │
│   ├── prompts/                     # System prompt şablonları
│   │   ├── __init__.py
│   │   ├── system_prompts.py        # Ana system prompt tanımları
│   │   ├── mode_prompts.py          # Mod-spesifik prompt'lar
│   │   └── templates/               # Jinja2 veya f-string şablonları
│   │       ├── qa_template.txt
│   │       ├── analysis_template.txt
│   │       ├── gdd_template.txt
│   │       └── ...
│   │
│   ├── models/                      # Pydantic veri modelleri
│   │   ├── __init__.py
│   │   ├── document.py              # Doküman modeli
│   │   ├── query.py                 # Sorgu modeli
│   │   ├── response.py              # Cevap modeli (confidence score dahil)
│   │   ├── user_profile.py          # Kullanıcı profil modeli
│   │   └── taxonomy.py              # Taksonomi/kategori modeli
│   │
│   └── utils/                       # Yardımcı fonksiyonlar
│       ├── __init__.py
│       ├── text_utils.py            # Metin işleme yardımcıları
│       ├── language_utils.py        # Dil algılama ve çeviri
│       └── logger.py                # Loguru yapılandırması
│
├── data/                            # Kalıcı veri dizini
│   ├── chroma_db/                   # ChromaDB kalıcı depolama
│   ├── user_profiles/               # Kullanıcı profil dosyaları (JSON)
│   ├── scraper_cache/               # Scraper önbelleği
│   └── logs/                        # Uygulama logları
│
├── seeds/                           # Başlangıç verileri (ilk yükleme)
│   ├── books/                       # Kitap özetleri (elle hazırlanmış)
│   │   ├── art_of_game_design.json
│   │   ├── rules_of_play.json
│   │   ├── theory_of_fun.json
│   │   └── ...
│   ├── frameworks/                  # Tasarım çerçeveleri
│   │   ├── mda_framework.json
│   │   ├── machinations.json
│   │   └── ...
│   └── glossary/                    # Oyun tasarımı terimler sözlüğü
│       └── game_design_glossary.json
│
├── tests/                           # Test dizini
│   ├── __init__.py
│   ├── conftest.py                  # Pytest fixtures
│   ├── test_rag_engine.py
│   ├── test_confidence_scorer.py
│   ├── test_document_processor.py
│   ├── test_modes/
│   │   ├── test_qa_mode.py
│   │   └── ...
│   └── test_scraper/
│       └── ...
│
└── docs/                            # Ek dokümantasyon
    ├── API.md                       # Plugin API referansı
    ├── TAXONOMY.md                  # Detaylı taksonomi açıklamaları
    ├── SCRAPING_SOURCES.md          # Taranacak kaynak listesi
    └── CHANGELOG.md                 # Değişiklik günlüğü
```

---

## 5. Bilgi Tabanı Taksonomisi

### 5.1 Ana Kategoriler ve Alt Kategoriler

Her bilgi parçası (chunk) aşağıdaki metadata ile etiketlenir:

```python
class DocumentMetadata(BaseModel):
    """Her bilgi parçasının zorunlu metadata'sı."""

    # Birincil sınıflandırma
    category: Category           # Ana kategori (enum)
    subcategory: str             # Alt kategori
    tags: list[str]              # Serbest etiketler (max 10)

    # Kaynak bilgisi
    source_type: SourceType      # Kaynak türü (enum)
    source_url: str | None       # Orijinal URL
    source_title: str            # Kaynak başlığı
    author: str | None           # Yazar
    publication_date: date | None # Yayın tarihi

    # Kalite ve güvenilirlik
    reliability_tier: int        # 1-5 arası (5 = en güvenilir)
    is_verified: bool            # Manuel doğrulama yapıldı mı?

    # Teknik bağlam
    game_engines: list[str]      # İlgili oyun motorları (boş olabilir)
    game_genres: list[str]       # İlgili oyun türleri (boş olabilir)

    # Sistem
    chunk_id: str                # Benzersiz ID
    ingested_at: datetime        # Sisteme eklenme tarihi
    last_verified_at: datetime | None  # Son doğrulama tarihi
```

### 5.2 Kategori Enumerasyonu

```python
class Category(str, Enum):
    """Ana bilgi kategorileri — MDA Framework + Schell's Elements bazlı."""

    # === MEKANIK (Mechanics) ===
    CORE_MECHANICS = "core_mechanics"           # Temel mekanikler, core loops
    GAME_SYSTEMS = "game_systems"               # Ekonomi, crafting, progression
    GAME_BALANCE = "game_balance"               # Denge, tuning, meta-game
    CONTROLS_INPUT = "controls_input"           # Kontrol şemaları, input handling

    # === DİNAMİK (Dynamics) ===
    LEVEL_DESIGN = "level_design"               # Seviye tasarımı, pacing, flow
    AI_DESIGN = "ai_design"                     # Oyun yapay zekası tasarımı
    MULTIPLAYER = "multiplayer"                 # Çok oyunculu tasarım

    # === ESTETİK (Aesthetics) ===
    NARRATIVE = "narrative"                     # Hikaye, dialog, world building
    UX_UI = "ux_ui"                             # Kullanıcı deneyimi/arayüzü
    AUDIO_DESIGN = "audio_design"               # Ses tasarımı
    VISUAL_DESIGN = "visual_design"             # Görsel yön, art direction

    # === OYUNCU (Player) ===
    PLAYER_PSYCHOLOGY = "player_psychology"      # Oyuncu motivasyonu, engagement
    PLAYER_TYPES = "player_types"               # Bartle, oyuncu profilleri
    ACCESSIBILITY = "accessibility"             # Erişilebilirlik

    # === İŞ (Business) ===
    MONETIZATION = "monetization"               # F2P, premium, battle pass
    MARKET_ANALYSIS = "market_analysis"         # Pazar trendleri, rekabet
    ANALYTICS = "analytics"                     # Oyuncu verileri, KPI'lar

    # === SÜREÇ (Process) ===
    GDD = "gdd"                                 # Game Design Document
    PROTOTYPING = "prototyping"                 # Prototipleme, playtesting
    POSTMORTEM = "postmortem"                   # Proje sonrası analizler

    # === TÜR-SPESİFİK (Genre-Specific) ===
    GENRE_RPG = "genre_rpg"
    GENRE_FPS = "genre_fps"
    GENRE_STRATEGY = "genre_strategy"
    GENRE_MOBILE = "genre_mobile"
    GENRE_PUZZLE = "genre_puzzle"
    GENRE_PLATFORMER = "genre_platformer"
    GENRE_SIMULATION = "genre_simulation"
    GENRE_OTHER = "genre_other"


class SourceType(str, Enum):
    """Kaynak türleri — güvenilirlik sıralamasına göre."""

    ACADEMIC_PAPER = "academic_paper"           # Tier 5 — En güvenilir
    BOOK = "book"                               # Tier 5
    GDC_TALK = "gdc_talk"                       # Tier 4
    POSTMORTEM = "postmortem"                   # Tier 4
    DEV_BLOG = "dev_blog"                       # Tier 3
    ARTICLE = "article"                         # Tier 3
    TUTORIAL = "tutorial"                       # Tier 2
    FORUM_DISCUSSION = "forum_discussion"       # Tier 1
    USER_SUBMITTED = "user_submitted"           # Tier 1 (doğrulanana kadar)
```

### 5.3 Etiketleme Kuralları

1. **Tek Kategori Kuralı:** Her chunk yalnızca BİR ana kategoriye atanır. Çapraz referans için `tags` kullanılır.
2. **Minimum Etiket:** Her chunk en az 2, en fazla 10 etiket alır.
3. **İngilizce Etiketler:** Etiketler her zaman İngilizce olmalı (arama tutarlılığı için).
4. **Motor Bağımsızlık:** `game_engines` alanı boş bırakılabilir. Sadece motor-spesifik bilgiler için doldurulur.
5. **Güvenilirlik Katmanı:** Kaynak türüne göre otomatik atanır, manuel doğrulama ile yükseltilebilir.

---

## 6. RAG Pipeline Kuralları

### 6.1 Chunking (Parçalama) Stratejisi

```python
# KURAL: Sabit boyutlu chunking KULLANILMAYACAK.
# Semantic chunking tercih edilecek.

CHUNKING_CONFIG = {
    "strategy": "semantic",              # "fixed" değil!
    "min_chunk_size": 200,               # Minimum karakter
    "max_chunk_size": 1500,              # Maximum karakter
    "overlap": 100,                      # Chunk'lar arası örtüşme (karakter)
    "preserve_paragraphs": True,         # Paragraf bütünlüğünü koru
    "preserve_headings": True,           # Başlıkları chunk'un başına ekle
    "metadata_inheritance": True,        # Parent dokümanın metadata'sını miras al
}
```

**Neden Semantic Chunking?**
- Oyun tasarımı metinleri genellikle kavramsal bütünlük taşır
- Bir mekanik açıklamasını ortasından bölmek anlam kaybına yol açar
- Semantic chunking, anlam sınırlarında bölerek context kalitesini artırır

### 6.2 Embedding Kuralları

```python
EMBEDDING_CONFIG = {
    "model": "all-MiniLM-L6-v2",         # Offline model
    "device": "cpu",                      # GPU varsa "cuda" yapılabilir
    "normalize_embeddings": True,         # L2 normalizasyonu
    "batch_size": 64,                     # Toplu embedding batch boyutu
}
```

**Kurallar:**
1. **Embedding modeli DEĞİŞTİRİLMEMELİ** — Model değiştirilirse tüm veritabanının yeniden embed edilmesi gerekir.
2. **Embedding önbelleğe alınmalı** — Aynı metin için tekrar embedding hesaplanmamalı.
3. **Sorgu embedding'i de aynı modelle yapılmalı** — Farklı model = uyumsuz vektör uzayı.

### 6.3 Retrieval (Arama) Kuralları

```python
RETRIEVAL_CONFIG = {
    "top_k": 10,                          # İlk arama sonucu sayısı
    "rerank_top_n": 5,                    # Re-rank sonrası seçilecek sayı
    "similarity_threshold": 0.3,          # Minimum benzerlik skoru (altı filtrelenir)
    "use_metadata_filter": True,          # Metadata filtreleme aktif
    "hybrid_search": True,                # Semantic + keyword arama
    "hybrid_alpha": 0.7,                  # Semantic ağırlığı (0.7) vs Keyword (0.3)
}
```

**Kurallar:**
1. **Hibrit Arama Zorunlu:** Sadece semantic arama yeterli değil. Oyun tasarımında spesifik terimler (ör. "roguelike", "gacha", "battle pass") keyword aramayla daha iyi bulunur.
2. **Re-ranking Zorunlu:** Top-K sonuçları Gemini ile re-rank edilerek en ilgili chunk'lar seçilir.
3. **Metadata Pre-filter:** Kullanıcı belirli bir konu belirtmişse (ör. "RPG mekanikleri"), önce kategori filtrelemesi yapılır.
4. **Boş Sonuç Yönetimi:** Arama sonucu boşsa veya threshold altındaysa, model "Bu konuda yeterli bilgim yok" demeli.

### 6.4 Generation (Üretim) Kuralları

```python
GENERATION_CONFIG = {
    "model": "gemini-2.5-flash",          # Maliyet/performans dengesi
    "temperature": 0.3,                   # Düşük — yaratıcılık değil doğruluk önemli
    "max_output_tokens": 4096,            # Uzun, detaylı cevaplar
    "top_p": 0.85,                        # Nucleus sampling
    "top_k_tokens": 40,
    "stop_sequences": [],
}
```

**Kurallar:**
1. **Temperature 0.3** — Beyin fırtınası modu hariç tüm modlarda düşük temperature kullanılır. Beyin fırtınasında 0.7'ye çıkılabilir.
2. **Context Window Yönetimi** — Context'e sadece re-rank sonrası en iyi chunk'lar verilir. Tüm veritabanı verilmez.
3. **System Prompt Zorunlu** — Her istekte mod-spesifik system prompt kullanılır.
4. **Grounding Talimatı** — System prompt'ta her zaman şu kural bulunur:

```
SADECE sana verilen context içindeki bilgilere dayanarak cevap ver.
Context'te bulunmayan bilgileri UYDURMA.
Eğer context yetersizse, açıkça "Bu konuda bilgi tabanımda yeterli veri yok" de.
Cevabının hangi kaynaklardan geldiğini belirt.
```

---

## 7. Anti-Halüsinasyon Kuralları

### 7.1 Güvenilirlik Puanlama Sistemi

Her cevabın başında bir güvenilirlik skoru gösterilir:

```
🟢 %90-100 — Yüksek Güvenilirlik: Birden fazla güvenilir kaynakla doğrulanmış
🟡 %70-89  — Orta Güvenilirlik: Tek kaynak veya kısmen desteklenmiş
🟠 %50-69  — Düşük Güvenilirlik: Sınırlı kaynak, dikkatli değerlendir
🔴 %0-49   — Çok Düşük / Yetersiz: Bilgi tabanında yeterli veri yok
```

### 7.2 Güvenilirlik Skoru Hesaplama Formülü

```python
def calculate_confidence(
    retrieval_scores: list[float],      # ChromaDB benzerlik skorları
    source_tiers: list[int],            # Kaynak güvenilirlik katmanları (1-5)
    chunk_count: int,                   # Eşleşen chunk sayısı
    context_coverage: float,            # Sorunun ne kadarı context'te var (0-1)
) -> float:
    """
    Güvenilirlik skoru hesapla.

    Ağırlıklar:
    - Retrieval kalitesi: %35
    - Kaynak güvenilirliği: %25
    - Çoklu kaynak desteği: %20
    - Context coverage: %20
    """
    avg_retrieval = sum(retrieval_scores) / len(retrieval_scores)
    avg_tier = sum(source_tiers) / len(source_tiers) / 5  # 0-1 arası normalize

    multi_source_bonus = min(chunk_count / 5, 1.0)  # 5+ kaynak = tam puan

    score = (
        avg_retrieval * 0.35 +
        avg_tier * 0.25 +
        multi_source_bonus * 0.20 +
        context_coverage * 0.20
    )

    return round(score * 100, 1)
```

### 7.3 Halüsinasyon Önleme Katmanları

| Katman | Mekanizma | Açıklama |
|--------|-----------|----------|
| **1. Retrieval** | Threshold filtreleme | Benzerlik skoru < 0.3 olan sonuçlar atılır |
| **2. Grounding** | System prompt talimatı | "Sadece context'e dayan" kuralı |
| **3. Verification** | Claim-level check | Cevaptaki her iddia context'te var mı? |
| **4. Scoring** | Confidence score | Her cevaba güvenilirlik puanı |
| **5. Fallback** | Bilinmeyen cevap | Yetersiz veri = "Bilmiyorum" cevabı |
| **6. Citation** | Kaynak gösterme | Her cevap kaynak URL/başlık içerir |

### 7.4 "Bilmiyorum" Politikası

```
KURAL: Modül, bilmediğini bilmelidir.

Aşağıdaki durumlarda modül "Bu konuda yeterli bilgim yok" demelidir:
1. Hiçbir chunk retrieval threshold'u geçemezse
2. Güvenilirlik skoru %50'nin altındaysa
3. Kullanıcının sorusu oyun tasarımı dışındaysa
4. Context'te sorunun cevabı bulunmuyorsa

"Bilmiyorum" cevabı verildiğinde:
- Neden bilmediğini kısaca açıkla
- Varsa ilgili ama eksik kaynakları göster
- Kullanıcıya manuel kaynak eklemeyi öner
- İnternette araştırma yapmasını teklif et
```

---

## 8. Etkileşim Modları

### 8.1 Mod Tanımları ve Davranış Kuralları

#### 🔹 Soru-Cevap Modu (QA Mode)
```yaml
tetikleyiciler: Doğrudan soru formatı ("... nasıl yapılır?", "... nedir?")
temperature: 0.3
max_tokens: 4096
davranış:
  - Kısa ve öz giriş
  - Adım adım veya madde madde açıklama
  - Varsa görsel/diyagram önerisi
  - Somut oyun örnekleri ile destekle
  - Kaynak göster
çıktı_formatı: "[Güvenilirlik %X] + Cevap + Kaynaklar"
```

#### 🔹 Oyun Analiz Modu (Analysis Mode)
```yaml
tetikleyiciler: "... oyununu analiz et", "... mekaniklerini incele"
temperature: 0.3
max_tokens: 8192
davranış:
  - Oyunun temel mekaniklerini listele
  - MDA framework ile analiz yap (Mechanics → Dynamics → Aesthetics)
  - Güçlü ve zayıf yönleri belirle
  - Benzer oyunlarla karşılaştır
  - İyileştirme önerileri sun
çıktı_formatı: "Yapılandırılmış rapor (başlıklar + tablolar)"
```

#### 🔹 Beyin Fırtınası Modu (Brainstorm Mode)
```yaml
tetikleyiciler: "... için fikir ver", "... nasıl geliştirilebilir?"
temperature: 0.7  # ← Diğer modlardan yüksek!
max_tokens: 4096
davranış:
  - En az 3-5 alternatif fikir üret
  - Her fikrin artılarını ve eksilerini belirt
  - Referans oyun örnekleri ver
  - Risk/ödül analizini dahil et
  - Kullanıcının mevcut projesine uygunluğu değerlendir
çıktı_formatı: "Numaralı fikir listesi + Pro/Con tablosu"
```

#### 🔹 Karşılaştırma Modu (Compare Mode)
```yaml
tetikleyiciler: "... ile ... arasındaki fark", "... vs ..."
temperature: 0.3
max_tokens: 4096
davranış:
  - Karşılaştırma tablosu oluştur
  - Her öğenin güçlü/zayıf yönlerini listele
  - Hangi durumda hangisinin tercih edileceğini açıkla
  - Somut oyun örnekleri ile destekle
çıktı_formatı: "Karşılaştırma tablosu + Özet yorum"
```

#### 🔹 GDD Oluşturucu Modu (GDD Creator Mode)
```yaml
tetikleyiciler: "GDD oluştur", "oyun dökümanı hazırla"
temperature: 0.4
max_tokens: 16384
davranış:
  - Adım adım sorular sorarak bilgi topla
  - Standart GDD şablonunu kullan
  - Her bölümü kullanıcı onayı ile doldur
  - Eksik bölümler için öneri sun
  - Son çıktıyı yapılandırılmış Markdown olarak ver
çıktı_formatı: "Interaktif wizard → Markdown GDD"
```

#### 🔹 Brifing/Özet Modu (Briefing Mode)
```yaml
tetikleyiciler: "... hakkında brifing ver", "... konusunu özetle"
temperature: 0.3
max_tokens: 2048 (kısa) / 8192 (detaylı)
davranış:
  - İstenen konuyu özlü ama kapsamlı özetle
  - Temel kavramları ve terminolojiyi açıkla
  - "Daha fazla bilgi" bağlantıları öner
  - Kısa/detaylı mod seçeneği sun
çıktı_formatı: "[Kısa: 1-2 paragraf] veya [Detaylı: bölümlenmiş rapor]"
```

#### 🔹 Aktif Geliştirme Danışmanı Modu (Advisor Mode)
```yaml
tetikleyiciler: "Şu an ... yapıyorum", "... üzerinde çalışıyorum"
temperature: 0.4
max_tokens: 4096
davranış:
  - Kullanıcının anlattığı durumu analiz et
  - Mevcut yaklaşımın güçlü/zayıf yönlerini değerlendir
  - Alternatif yöntemler öner
  - Potansiyel sorunları erken uyar
  - Motor-spesifik tavsiyeler ver (kullanıcı motorunu belirtmişse)
  - "Dikkat edilmesi gerekenler" listesi ver
çıktı_formatı: "Durum analizi + Öneriler + Uyarılar"
özel_kural: |
  Bu mod kullanıcı profilinden aktif proje bilgisini okur.
  Kullanıcı hangi oyun motorunu kullandığını belirtmişse,
  tavsiyeler o motora özgü olmalıdır.
```

#### 🔹 Pazar Analizi Modu (Market Analysis Mode)
```yaml
tetikleyiciler: "... türünün pazar durumu", "... oyun pazarı analizi"
temperature: 0.3
max_tokens: 8192
davranış:
  - Belirtilen türün güncel pazar durumunu özetle
  - Trend analizi yap (yükselen/düşen trendler)
  - Başarılı ve başarısız örnekleri incele
  - Boşluk analizi (gap analysis) yap
  - Giriş stratejisi önerileri sun
çıktı_formatı: "Yapılandırılmış pazar raporu + trend tablosu"
özel_kural: |
  Bu modun verisi en hızlı eskiyendir.
  Kaynakların tarihine dikkat et.
  1 yıldan eski pazar verilerini "güncel olmayabilir" uyarısıyla işaretle.
```

---

## 9. Veri Toplama Kuralları

### 9.1 Scraping Etik Kuralları

```python
SCRAPING_ETHICS = {
    # ✅ YAPILACAKLAR
    "respect_robots_txt": True,           # robots.txt'e mutlaka uy
    "rate_limit_seconds": 3,              # İstekler arası minimum 3 saniye
    "identify_bot": True,                 # User-Agent'ta bot kimliğini belirt
    "cache_responses": True,              # Aynı sayfa tekrar indirilmez
    "check_terms_of_service": True,       # ToS kontrolü yap

    # ❌ YAPILMAYACAKLAR
    "scrape_behind_login": False,         # Login gerektiren içerik taranmaz
    "scrape_personal_data": False,        # Kişisel veri toplanmaz
    "bypass_captcha": False,              # CAPTCHA atlatılmaz
    "overwhelm_servers": False,           # Sunucu aşırı yüklenmez
}
```

### 9.2 Kaynak Önceliklendirme

| Öncelik | Kaynak | Tarama Sıklığı | Neden |
|---------|--------|-----------------|-------|
| 1 | GDC Vault (ücretsiz kısım) | Haftalık | Endüstri standardı |
| 2 | Game Developer Magazine/Gamasutra | Haftalık | Derin teknik makaleler |
| 3 | Oyun şirketi dev blog'ları | 2 haftada bir | Birincil kaynak |
| 4 | Post-mortem analizleri | Aylık | Derin analitik değer |
| 5 | Akademik makaleler | Aylık | En yüksek güvenilirlik |
| 6 | Kitap özetleri/notları | Manuel | Temel bilgi tabanı |

### 9.3 Doküman İşleme Pipeline'ı

```
Ham İçerik (HTML/PDF/Text)
       │
       ▼
┌──────────────────┐
│ 1. Temizleme      │ ← HTML tag'leri, reklam, navigasyon kaldır
│    (Cleaning)      │ ← Yalnızca ana içerik (article body) al
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 2. Normalizasyon  │ ← Unicode normalize, boşluk düzenleme
│    (Normalize)     │ ← Başlıkları, listeleri koru
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 3. Metadata       │ ← Kategori, etiket, kaynak türü ata
│    Çıkarma         │ ← LLM veya rule-based sınıflandırma
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 4. Chunking       │ ← Semantic chunking uygula
│    (Parçalama)     │ ← Overlap ile bağlam koru
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 5. Embedding      │ ← sentence-transformers ile embed et
│    (Vektörleme)    │ ← Offline, local
└──────┬───────────┘
       │
       ▼
┌──────────────────┐
│ 6. Depolama       │ ← ChromaDB'ye kaydet
│    (Storage)       │ ← Metadata ile birlikte
└──────────────────┘
```

### 9.4 Zamanlanmış Görevler (Schedule)

```python
SCHEDULE_CONFIG = {
    "auto_scrape": {
        "enabled": True,
        "cron": "0 3 * * 1",            # Her Pazartesi saat 03:00
        "sources": ["gdc", "gamasutra", "dev_blogs"],
        "max_articles_per_run": 50,       # Çalışma başına maksimum makale
    },
    "database_maintenance": {
        "enabled": True,
        "cron": "0 4 * * 0",            # Her Pazar saat 04:00
        "tasks": [
            "remove_duplicates",          # Tekrar eden chunk'ları kaldır
            "update_stale_scores",        # Eski skorları güncelle
            "compact_database",           # DB optimizasyonu
        ],
    },
}
```

---

## 10. Kullanıcı Profili ve Hafıza Sistemi

### 10.1 Kullanıcı Profil Modeli

```python
class UserProfile(BaseModel):
    """Kullanıcı profil verisi — cevapları kişiselleştirmek için."""

    # Kimlik
    user_id: str                         # Benzersiz kullanıcı ID
    display_name: str                    # Görünen isim

    # Tercihler
    preferred_language: str = "tr"       # Cevap dili
    preferred_game_engines: list[str] = []  # Kullanılan motorlar
    preferred_genres: list[str] = []     # İlgilendiği oyun türleri
    experience_level: str = "intermediate"  # beginner/intermediate/advanced

    # Aktif Proje
    active_project: ActiveProject | None = None

    # Geçmiş
    interaction_history: list[InteractionSummary] = []  # Son N etkileşimin özeti
    favorite_topics: list[str] = []      # Sık sorulan konular (otomatik)

    # Sistem
    created_at: datetime
    updated_at: datetime


class ActiveProject(BaseModel):
    """Kullanıcının aktif olarak geliştirdiği proje bilgisi."""

    project_name: str
    game_engine: str | None = None       # Unity, Unreal, Godot vb.
    genre: str | None = None             # RPG, FPS, puzzle vb.
    development_phase: str | None = None # concept, prototype, production, polish
    key_features: list[str] = []         # Projenin temel özellikleri
    known_challenges: list[str] = []     # Bilinen sorunlar/zorluklar
    notes: str = ""                      # Serbest notlar
```

### 10.2 Hafıza Kuralları

1. **Profil Kalıcı:** Kullanıcı profili JSON olarak diske kaydedilir, oturumlar arası korunur.
2. **Otomatik Güncelleme:** Kullanıcı motor veya tür belirttiğinde profil otomatik güncellenir.
3. **Geçmiş Özeti:** Son 50 etkileşimin kısa özeti saklanır (tam mesajlar değil, sadece konu + mod).
4. **Favori Konular:** En sık sorulan 10 konu otomatik izlenir.
5. **Aktif Proje Bağlamı:** `advisor_mode` ve diğer modlar aktif proje bilgisini okur.
6. **Gizlilik:** Profil verileri sadece local'de saklanır, hiçbir yere gönderilmez.

---

## 11. Plugin Mimarisi

### 11.1 Jarvis Plugin Interface

Bu modül, Jarvis'in ilk plugin'i olacak. Plugin altyapısı basit ve genişletilebilir olmalı:

```python
# === game_designer/__init__.py ===

from game_designer.plugin import GameDesignerPlugin

__all__ = ["GameDesignerPlugin"]
__version__ = "0.1.0"
```

```python
# === game_designer/plugin.py ===

from abc import ABC, abstractmethod


class JarvisPlugin(ABC):
    """
    Tüm Jarvis plugin'lerinin uyması gereken temel arayüz.
    Bu, ileride başka plugin'ler (müzik, grafik vb.) eklendiğinde
    tutarlılık sağlar.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Plugin'in benzersiz adı."""
        ...

    @property
    @abstractmethod
    def version(self) -> str:
        """Plugin versiyonu (SemVer)."""
        ...

    @property
    @abstractmethod
    def description(self) -> str:
        """Plugin'in kısa açıklaması."""
        ...

    @abstractmethod
    def initialize(self) -> None:
        """Plugin'i başlat (DB bağlantısı, model yükleme vb.)."""
        ...

    @abstractmethod
    def shutdown(self) -> None:
        """Plugin'i temiz bir şekilde kapat."""
        ...

    @abstractmethod
    def handle_query(self, query: str, context: dict | None = None) -> dict:
        """Ana sorgu işleme metodu."""
        ...

    @abstractmethod
    def get_capabilities(self) -> list[str]:
        """Plugin'in desteklediği yeteneklerin listesi."""
        ...


class GameDesignerPlugin(JarvisPlugin):
    """Jarvis Game Designer Plugin — Oyun tasarımı uzman modülü."""

    @property
    def name(self) -> str:
        return "game_designer"

    @property
    def version(self) -> str:
        return "0.1.0"

    @property
    def description(self) -> str:
        return "Oyun tasarımı konusunda uzmanlaşmış RAG tabanlı bilgi yardımcısı"

    def get_capabilities(self) -> list[str]:
        return [
            "query",              # Soru-Cevap
            "analyze_game",       # Oyun Analizi
            "brainstorm",         # Beyin Fırtınası
            "compare",            # Karşılaştırma
            "create_gdd",         # GDD Oluşturma
            "brief",              # Brifing/Özet
            "advise",             # Aktif Danışmanlık
            "market_analysis",    # Pazar Analizi
        ]
```

### 11.2 Jarvis Entegrasyon Kullanımı

```python
# Jarvis ana uygulamasından kullanım örneği:

from game_designer import GameDesignerPlugin

# Plugin'i başlat
gd = GameDesignerPlugin(config_path="./config.yaml")
gd.initialize()

# Soru-Cevap
response = gd.query("Core loop nasıl tasarlanır?")
print(response.text)
print(f"Güvenilirlik: %{response.confidence}")
print(f"Kaynaklar: {response.sources}")

# Oyun Analizi
analysis = gd.analyze_game("Hades")

# Beyin Fırtınası
ideas = gd.brainstorm(
    "Roguelike bir oyunda kalıcı progression sistemi",
    context={"engine": "Unity", "genre": "roguelike"}
)

# Aktif Geliştirme Danışmanlığı
advice = gd.advise(
    "Karakterin yürüme animasyonlarını yapıyorum, inverse kinematics kullanıyorum"
)

# Plugin'i kapat
gd.shutdown()
```

---

## 12. Kodlama Standartları

### 12.1 Genel Python Kuralları

```python
# ✅ YAPILACAKLAR

# 1. Type hints ZORUNLU — her fonksiyon, parametre ve dönüş tipi belirtilmeli
def process_query(query: str, top_k: int = 10) -> QueryResult:
    ...

# 2. Docstring ZORUNLU — Google style
def calculate_confidence(scores: list[float]) -> float:
    """Güvenilirlik skorunu hesapla.

    Args:
        scores: ChromaDB benzerlik skorları listesi.

    Returns:
        0-100 arası güvenilirlik skoru.

    Raises:
        ValueError: scores listesi boşsa.
    """
    ...

# 3. Pydantic modelleri ZORUNLU — dict değil, model kullan
class QueryResult(BaseModel):
    text: str
    confidence: float
    sources: list[Source]
    mode: str

# 4. Hata yönetimi ZORUNLU — bare except yasak
try:
    result = chroma_collection.query(...)
except chromadb.errors.InvalidCollectionException as e:
    logger.error(f"Collection bulunamadı: {e}")
    raise
except Exception as e:
    logger.error(f"Beklenmeyen hata: {e}")
    raise GameDesignerError(f"Sorgu işlenirken hata: {e}") from e

# 5. Loglama ZORUNLU — print() yasak, loguru kullan
from loguru import logger
logger.info("Sorgu işleniyor", query=query, mode=mode)
```

```python
# ❌ YAPILMAYACAKLAR

# 1. Global state YASAK
GLOBAL_DB = None  # ❌ Bunu yapma

# 2. Hardcoded değerler YASAK
similarity_threshold = 0.3  # ❌ Config'den oku

# 3. Star import YASAK
from game_designer.core import *  # ❌

# 4. print() YASAK (loglama hariç)
print("Debug:", result)  # ❌ logger.debug() kullan

# 5. Bare except YASAK
except:  # ❌ Her zaman spesifik exception yakala
    pass
```

### 12.2 Dosya ve Sınıf İsimlendirme

| Tip | Format | Örnek |
|-----|--------|-------|
| Dosya adı | `snake_case.py` | `rag_engine.py`, `chroma_manager.py` |
| Sınıf adı | `PascalCase` | `RagEngine`, `ChromaManager` |
| Fonksiyon | `snake_case` | `process_query`, `calculate_confidence` |
| Sabitler | `UPPER_SNAKE_CASE` | `MAX_CHUNK_SIZE`, `DEFAULT_MODEL` |
| Private | `_leading_underscore` | `_internal_search`, `_build_context` |

### 12.3 Import Sırası

```python
# 1. Standart kütüphane
import json
from datetime import datetime
from pathlib import Path

# 2. Üçüncü parti paketler
import chromadb
from google import genai
from pydantic import BaseModel
from loguru import logger

# 3. Proje içi importlar
from game_designer.core.rag_engine import RagEngine
from game_designer.models.document import DocumentMetadata
```

---

## 13. Güvenlik ve Etik Kurallar

### 13.1 API Anahtarı Güvenliği

```python
# ✅ DOĞRU: .env dosyasından oku
import os
from dotenv import load_dotenv

load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# ❌ YANLIŞ: Koda gömmek
GEMINI_API_KEY = "AIzaSy..."  # ASLA YAPMA
```

**Kurallar:**
1. API anahtarları **ASLA** kaynak koduna yazılmaz.
2. `.env` dosyası `.gitignore`'a eklenir.
3. `.env.example` dosyasında sadece anahtar isimleri (değerleri değil) bulunur.

### 13.2 Veri Gizliliği

1. Kullanıcı profil verileri sadece local diskte saklanır.
2. ChromaDB verileri sadece local diskte saklanır.
3. Gemini API'ye gönderilen sorgularda kişisel bilgi bulunmaz.
4. Scraping sırasında kişisel veri (isim, email vb.) toplanmaz.

### 13.3 Telif Hakkı Uyumu

1. Kitapların **tam metni** saklanmaz — yalnızca özetler ve notlar.
2. Makalelerin **tam kopyası** saklanmaz — chunked özetler saklanır.
3. Her kaynağın orijinal URL'si korunur ve atıf yapılır.
4. `robots.txt` kurallarına uyulur.
5. Paywall arkasındaki içerikler taranmaz.

---

## 14. Test Stratejisi

### 14.1 Test Piramidi

```
         ╱╲
        ╱  ╲
       ╱ E2E╲          ← 2-3 entegrasyon testi (tam pipeline)
      ╱──────╲
     ╱Integra-╲        ← 10-15 entegrasyon testi (modül arası)
    ╱──tion────╲
   ╱────────────╲
  ╱  Unit Tests  ╲     ← 50+ birim testi (her fonksiyon için)
 ╱────────────────╲
```

### 14.2 Test Edilmesi Gereken Kritik Alanlar

| Alan | Test Türü | Açıklama |
|------|-----------|----------|
| Confidence Scorer | Unit | Çeşitli skor kombinasyonları ile doğruluk |
| Chunking | Unit | Farklı metin yapılarında doğru parçalama |
| Metadata Atama | Unit | Doğru kategori/etiket atanması |
| Query Rewriter | Unit | Sorgu iyileştirme kalitesi |
| RAG Pipeline | Integration | Uçtan uca sorgu → cevap akışı |
| Scraper | Integration | Gerçek URL'lerden veri çekme |
| Fallback | Integration | Bilgi yokken "bilmiyorum" cevabı |
| Mode Router | Unit | Doğru mod seçimi |

### 14.3 Test Çalıştırma

```bash
# Tüm testler
pytest tests/ -v

# Sadece birim testleri
pytest tests/ -v -m "not integration"

# Coverage raporu
pytest tests/ --cov=game_designer --cov-report=html
```

---

## 15. Performans ve Ölçeklendirme

### 15.1 Performans Hedefleri

| Metrik | Hedef | Açıklama |
|--------|-------|----------|
| Sorgu yanıt süresi | < 5 saniye | Embedding + retrieval + generation |
| İlk yükleme süresi | < 10 saniye | Model ve DB yükleme |
| Embedding hızı | > 50 chunk/sn | CPU üzerinde |
| Veritabanı boyutu | < 2 GB | İlk 10.000 chunk için |
| RAM kullanımı | < 1 GB | Çalışma zamanında |

### 15.2 Optimizasyon Kuralları

1. **Lazy Loading:** Embedding modeli ilk sorguya kadar yüklenmez.
2. **Batch Processing:** Scraping sonrası embedding toplu yapılır (64'lük batch).
3. **Caching:** Sık sorulan sorguların sonuçları önbelleğe alınır (LRU, max 100).
4. **Async I/O:** Scraping ve API çağrıları mümkün olduğunca asenkron yapılır.
5. **DB Compact:** Haftalık veritabanı bakımı ile performans korunur.

---

## 16. Yapay Zeka Asistanları İçin Özel Talimatlar

> **Bu bölüm, bu projeyi geliştirmek için kullanılan AI asistanlarına yöneliktir.**
> Claude, Gemini, GPT veya başka bir AI asistanı bu dokümanı okuduğunda
> aşağıdaki kurallara uymalıdır.

### 16.1 Genel Talimatlar

```
1. BU DOKÜMANI ÖNCE TAMAMEN OKU, sonra kod yaz.
2. Dizin yapısına uy — dosyaları doğru konumlara oluştur.
3. Type hints ve docstring'leri ATLA yapma.
4. Her sınıf için Pydantic model kullan (dict değil).
5. Hata yönetimini ATLA yapma — her harici çağrı try/except içinde olmalı.
6. print() kullanma, loguru logger kullan.
7. Hardcoded değer kullanma, config'den oku.
8. Testleri ATLA yapma — her yeni fonksiyon için en az bir test yaz.
```

### 16.2 Kod Üretme Sırası

```
Aşağıdaki sırayla kod üret:

1. models/          ← Önce veri modellerini oluştur (Pydantic)
2. config.py        ← Konfigürasyon yönetimini kur
3. utils/           ← Yardımcı fonksiyonları yaz
4. data/            ← ChromaDB manager, embedding manager yaz
5. core/            ← RAG engine, confidence scorer yaz
6. modes/           ← Etkileşim modlarını yaz
7. scraper/         ← Scraper'ları yaz
8. prompts/         ← System prompt'ları hazırla
9. plugin.py        ← Ana plugin sınıfını yaz
10. __init__.py     ← Public API'yi expose et
11. tests/          ← Testleri yaz
12. seeds/          ← Başlangıç verilerini hazırla
```

### 16.3 Kalite Kontrol Listesi

Her PR/commit öncesi kontrol et:

- [ ] Tüm fonksiyonlarda type hints var mı?
- [ ] Tüm public fonksiyonlarda docstring var mı?
- [ ] Tüm harici çağrılar try/except içinde mi?
- [ ] Hardcoded değer yok, config'den mi okunuyor?
- [ ] print() yerine logger mi kullanılıyor?
- [ ] Yeni fonksiyonlar için test yazıldı mı?
- [ ] Import sırası doğru mu? (stdlib → 3rd party → project)
- [ ] Pydantic modeller doğru tanımlanmış mı?
- [ ] `.env` dosyasına hassas veri yazılmamış mı?
- [ ] Confidence score hesaplaması doğru çalışıyor mu?

### 16.4 Sık Yapılan Hatalar (Kaçınılacaklar)

| Hata | Neden Yanlış | Doğru Yaklaşım |
|------|-------------|----------------|
| Tüm veritabanını context'e vermek | Token limiti aşar, maliyet artar | Top-5 re-ranked chunk ver |
| Temperature 1.0 kullanmak | QA modunda halüsinasyon artar | QA: 0.3, Brainstorm: 0.7 |
| Embedding modelini değiştirmek | Tüm DB'yi yeniden embed etmek gerekir | Projeye başlarken bir seç, değiştirme |
| Synchronous scraping | Programı kilitler | Async veya ayrı thread kullan |
| Kaynak göstermemek | Doğrulama yapılamaz | Her cevapta kaynak URL/başlık göster |
| Kullanıcı profilini güncellememek | Cevaplar kişisel olmaz | Her etkileşimde profili kontrol et |

---

## Ek A: Terimler Sözlüğü

| Terim | Açıklama |
|-------|----------|
| **RAG** | Retrieval-Augmented Generation — Bilgi getirme destekli üretim |
| **Chunk** | Dokümanın anlamlı bir alt parçası |
| **Embedding** | Metnin sayısal vektör temsili |
| **ChromaDB** | Açık kaynak vektör veritabanı |
| **Hallucination** | LLM'in kaynak olmadan uydurduğu bilgi |
| **Grounding** | Cevabı kanıtlanmış kaynaklara dayandırma |
| **Re-ranking** | Arama sonuçlarını ilgililik skoruna göre yeniden sıralama |
| **System Prompt** | LLM'e verilen rol ve davranış talimatı |
| **GDD** | Game Design Document — Oyun tasarım belgesi |
| **MDA Framework** | Mechanics-Dynamics-Aesthetics analiz çerçevesi |
| **Core Loop** | Oyunun temel tekrar eden döngüsü |
| **Playtesting** | Oyunun oyuncularla test edilmesi |
| **Post-mortem** | Proje sonrası analiz raporu |

---

## Ek B: Hızlı Başlangıç Kontrol Listesi

```
Projeyi sıfırdan kurmak için:

1. [ ] Python 3.10+ kurulu olduğunu doğrula
2. [ ] Virtual environment oluştur: python -m venv .venv
3. [ ] Bağımlılıkları kur: pip install -r requirements.txt
4. [ ] .env dosyasını oluştur ve GEMINI_API_KEY ekle
5. [ ] Embedding modelini indir (ilk çalıştırmada otomatik)
6. [ ] Seed verileri yükle: python -m game_designer.seeds.loader
7. [ ] Test et: pytest tests/ -v
8. [ ] Plugin'i başlat ve test sorgusu gönder
```

---

> **Son Güncelleme:** 2026-09-22
> **Versiyon:** 1.0.0
> **Yazar:** AI-assisted (Mehmet + Antigravity)
