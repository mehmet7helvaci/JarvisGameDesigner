# 📖 Jarvis Game Designer — API Referansı

## Genel Bakış
`GameDesignerPlugin`, Jarvis AI asistanı ve bağımsız Python projeleri için geliştirilmiş uzman bir oyun tasarımı bilgi motorudur.

---

## 1. Başlatma ve Kapatma

```python
from game_designer import GameDesignerPlugin

# Örnek oluşturma
plugin = GameDesignerPlugin()

# Eklentiyi başlatma (Veritabanı, modeller, dizinler)
plugin.initialize()

# Kapatma
plugin.shutdown()
```

---

## 2. Temel Yetenek Metotları

### `query(query: str, context: dict = None, category=None, engine=None, genre=None, user_id='default_user') -> GameDesignerResponse`
Genel soru-cevap veya akıllı mod yönlendirmeli sorgu işleme metodu.

### `analyze_game(game_or_mechanic: str, context: dict = None) -> GameDesignerResponse`
MDA (Mechanics, Dynamics, Aesthetics) Framework çerçevesinde oyun veya mekanik analizi yapar.

### `brainstorm(topic: str, context: dict = None) -> GameDesignerResponse`
Yaratıcı beyin fırtınası modu (Temperature: 0.7). 3-5 alternatif tasarım fikri ve pro/con tablosu üretir.

### `compare(item_a: str, item_b: str = None, context: dict = None) -> GameDesignerResponse`
İki sistem veya yaklaşımı karşılaştıran Markdown tablosu ve analiz sunar.

### `create_gdd(concept: str, context: dict = None) -> GameDesignerResponse`
Endüstri standardında yapılandırılmış Oyun Tasarım Dökümanı (GDD) üretir.

### `brief(topic: str, context: dict = None) -> GameDesignerResponse`
Kısa/kapsamlı yönetici özeti ve en iyi tasarım pratiklerini sunar.

### `advise(current_situation: str, context: dict = None) -> GameDesignerResponse`
Kullanıcının aktif projesine ve motoruna göre anlık durum danışmanlığı verir.

### `market_analysis(genre_or_platform: str, context: dict = None) -> GameDesignerResponse`
Pazar trendleri ve hedef kitle analizi yapar.

---

## 3. Veri Ekleme ve Hafıza Yönetimi

```python
# Doğrudan metin dökümanı ekleme
plugin.ingest_text(
    title="Celeste Platforming Mechanics",
    content="Celeste utilizes coyote time and jump buffering...",
    category=Category.CORE_MECHANICS,
    tags=["platformer", "game_feel"]
)

# Aktif proje ayarlama
plugin.set_user_active_project(
    user_id="developer_1",
    project_name="Shadow Dungeons",
    game_engine="Godot",
    genre="Roguelike"
)
```
