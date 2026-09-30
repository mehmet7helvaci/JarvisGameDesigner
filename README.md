# 🎮 Jarvis Game Designer

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests: 81 Passed](https://img.shields.io/badge/tests-81%20passed-brightgreen.svg)]()

> **Jarvis AI** ekosistemi için geliştirilmiş, profesyonel oyun tasarımı rehberi, RAG (Retrieval-Augmented Generation) tabanlı yapay zeka danışmanı ve Blender 3D / animasyon varlık stüdyosu.

---

## 🌟 Öne Çıkan Özellikler

- **🧠 RAG Tabanlı AI Oyun Tasarımı Danışmanı:**
  - 8 farklı etkileşim modu: Soru-Cevap (`qa`), MDA Oyun Analizi (`analyze_game`), Yaratıcı Beyin Fırtınası (`brainstorm`), Mekanik Karşılaştırma (`compare`), GDD Oluşturucu (`create_gdd`), Brifing (`brief`), Aktif Geliştirme Danışmanlığı (`advise`), Pazar Analizi (`market_analysis`).
  - %0–100 Güvenilirlik Puanlaması (`ConfidenceScorer`) ve otomatik kaynak doğrulama.
  - Canlı akışlı (streaming) ultra hızlı yanıtlar ve LRU bellek önbelleği.

- **🕹️ Etkileşimli 3D ve Canlı Animasyon Viewport'u:**
  - `.blend`, `.fbx`, `.gltf`, `.glb`, `.obj`, `.dae`, `.bvh` dosyaları için entegre 3D önizleme.
  - 18 kemikli ileri kinematik (FK) motoru ile yürüme, koşma, zıplama ve saldırı animasyonlarını 30 FPS canlı oynatma.
  - Blender `.blend` başlıklarından gömülü render küçük resimlerini (thumbnail) otomatik ayıklama.
  - 3 boyutta fare ile serbest döndürme (Orbit), yakınlaşma (Zoom) ve kaydırma (Pan).

- **⚡ Sürükle-Bırak & Tek Tıkla Anında Dosya Tanıma:**
  - Dosyaları veya tüm klasörleri sürükleyip bırakarak form doldurmadan anında projeye ekleme.
  - Dosya adından ve uzantısından akıllı kategori sezgisi (*Animasyon*, *Karakter*, *Çevre/Level*, *Prop*, *Araç*, *VFX*).

- **🔄 Jarvis ile Çift Yönlü Canlı Senkronizasyon (Two-Way Sync):**
  - Standalone masaüstü uygulamasında oluşturulan veya düzenlenen tüm projeler ve 3D varlıklar, Jarvis'e anında yansır.
  - Jarvis üzerinden sesli veya yazılı olarak proje listeleme, aktif proje seçme ve Blender dosyalarını sorgulama.

- **🖥️ Bağımsız Masaüstü GUI & Windows Entegrasyonu:**
  - Unreal / Blender koyu stüdyo temalı arayüz (`gui_launcher.pyw`).
  - Windows Görev Yöneticisi ve Görev Çubuğunda Python yerine özel logo ve uygulama kimliği (`AppUserModelID`).
  - Masaüstü kısayolu (`.lnk`) ile tek tıkla konsolsuz başlatma.

---

## 🚀 Hızlı Başlangıç

### 1. Kurulum

```bash
# Depoyu klonlayın
git clone https://github.com/mehmet7helvaci/JarvisGameDesigner.git
cd JarvisGameDesigner

# Sanal ortam oluşturun ve aktif edin
python -m venv .venv
# Windows:
.venv\Scripts\activate

# Bağımlılıkları yükleyin
pip install -r requirements.txt
```

### 2. Ortam Değişkenleri

```bash
cp .env.example .env
# .env dosyasını açıp isteğe bağlı GEMINI_API_KEY değerinizi ekleyin.
# (API anahtarı girilmediğinde sistem yerel deterministik RAG motoruyla çevrimdışı çalışır.)
```

### 3. Uygulamayı Başlatma

#### Bağımsız Masaüstü Stüdyosu:
```bash
python gui_launcher.pyw
```
*(Veya masaüstünüzdeki `Jarvis Game Designer.lnk` kısayoluna çift tıklayın.)*

#### Jarvis Plugin Olarak Kullanım:
```python
from game_designer import GameDesignerPlugin

# Eklentiyi başlat
gd = GameDesignerPlugin()
gd.initialize()

# Soru-Cevap
res = gd.query("Core loop nasıl tasarlanır?")
print(f"Güvenilirlik: %{res.confidence}")
print(res.text)

# Oyun Analizi
res = gd.analyze_game("Hades")
print(res.text)

# Aktif Danışmanlık
res = gd.advise("Karakterin yürüme animasyonlarını yapıyorum, inverse kinematics kullanıyorum")
print(res.text)

# Kapatma
gd.shutdown()
```

---

## 🧪 Testler

Uygulamanın tüm birim ve entegrasyon testlerini çalıştırmak için:

```bash
pytest -v
# 81 passed (100%)
```

---

## 📂 Dizin Yapısı

```
JarvisGameDesigner/
├── assets/                          # Uygulama ikonları (.ico, .png)
├── game_designer/                   # Çekirdek Python paketi
│   ├── core/                        # RAG motoru, güvenilirlik puanlayıcı, yönlendirici
│   ├── data/                        # Vektör DB yöneticisi, proje yöneticisi, kullanıcı hafızası
│   ├── models/                      # Pydantic veri modelleri (proje, doküman, sorgu, taksonomi)
│   ├── modes/                       # 8 farklı oyun tasarım modu
│   ├── prompts/                     # Sistem prompt'ları ve şablonlar
│   ├── scraper/                     # Otomatik veri toplama ve web tarayıcıları
│   ├── ui/                          # Tkinter tabanlı stüdyo arayüzü ve 3D viewport
│   └── utils/                       # Kısayol, metin, dil ve log yardımcıları
├── seeds/                           # Başlangıç bilgi kütüphanesi (MDA, Schell, Machinations, Sözlük)
├── tests/                           # Kapsamlı test paketi (81 test)
├── gui_launcher.pyw                 # Bağımsız konsolsuz GUI başlatıcı
├── plugin.py                        # Jarvis Core entegrasyon adaptörü
├── kurallar.md                      # Kapsamlı mimari kural ve standartlar dokümanı
├── requirements.txt                 # Python bağımlılıkları
└── pyproject.toml                   # Proje metadata ve build ayarları
```

---

## 📄 Lisans

Bu proje [MIT Lisansı](LICENSE) kapsamında lisanslanmıştır.
