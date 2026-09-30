"""APScheduler tabanlı zamanlanmış veri toplama ve bakım motoru."""

from typing import TYPE_CHECKING, Any
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from game_designer.config import Settings, get_settings
from game_designer.data.chroma_manager import ChromaManager
from game_designer.data.document_processor import DocumentProcessor
from game_designer.scraper.blog_scraper import BlogScraper
from game_designer.scraper.gamasutra_scraper import GamasutraScraper
from game_designer.scraper.gdc_scraper import GDCScraper
from game_designer.scraper.postmortem_scraper import PostmortemScraper
from game_designer.utils.logger import logger

if TYPE_CHECKING:
    from game_designer.scraper.base_scraper import BaseScraper


class ScraperScheduler:
    """Zamanlanmış web kazıma ve veritabanı bakım işlemlerini yöneten sınıf."""

    def __init__(
        self,
        settings: Settings | None = None,
        chroma_manager: ChromaManager | None = None,
        doc_processor: DocumentProcessor | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.chroma_manager = chroma_manager or ChromaManager(self.settings)
        self.doc_processor = doc_processor or DocumentProcessor(self.settings)

        self.scheduler = BackgroundScheduler()
        self.scrapers: dict[str, BaseScraper] = {
            "gdc": GDCScraper(self.settings),
            "gamasutra": GamasutraScraper(self.settings),
            "dev_blogs": BlogScraper(self.settings),
            "postmortem": PostmortemScraper(self.settings),
        }
        self._is_running = False

    def setup_jobs(self) -> None:
        """Zamanlanmış görevleri APScheduler'a kaydeder."""
        cfg = self.settings.schedule

        # 1. Otomatik kazıma görevi
        if cfg.auto_scrape_enabled:
            cron_parts = cfg.auto_scrape_cron.split()
            if len(cron_parts) == 5:
                minute, hour, day, month, day_of_week = cron_parts
                trigger = CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                )
                self.scheduler.add_job(
                    self.run_auto_scrape,
                    trigger=trigger,
                    id="auto_scrape_job",
                    replace_existing=True,
                )
                logger.info(f"Otomatik tarama görevi kuruldu ({cfg.auto_scrape_cron})")

        # 2. Bakım görevi
        if cfg.maintenance_enabled:
            cron_parts = cfg.maintenance_cron.split()
            if len(cron_parts) == 5:
                minute, hour, day, month, day_of_week = cron_parts
                trigger = CronTrigger(
                    minute=minute,
                    hour=hour,
                    day=day,
                    month=month,
                    day_of_week=day_of_week,
                )
                self.scheduler.add_job(
                    self.run_maintenance,
                    trigger=trigger,
                    id="db_maintenance_job",
                    replace_existing=True,
                )
                logger.info(f"Veritabanı bakım görevi kuruldu ({cfg.maintenance_cron})")

    def start(self) -> None:
        """Scheduler'ı başlatır."""
        if not self._is_running:
            self.setup_jobs()
            self.scheduler.start()
            self._is_running = True
            logger.info("ScraperScheduler başlatıldı.")

    def stop(self) -> None:
        """Scheduler'ı durdurur."""
        if self._is_running:
            self.scheduler.shutdown(wait=False)
            self._is_running = False
            logger.info("ScraperScheduler durduruldu.")

    def run_auto_scrape(self, max_articles: int | None = None) -> int:
        """Kayıtlı scraper'ları çalıştırıp bulunan dokümanları veritabanına ekler."""
        logger.info("Zamanlanmış tarama görevi çalışıyor...")
        limit = max_articles or self.settings.scraping.max_articles_per_run
        total_chunks_added = 0

        for name, scraper in self.scrapers.items():
            try:
                raw_docs = scraper.scrape(limit=max(limit // len(self.scrapers), 2))
                for raw_doc in raw_docs:
                    chunks = self.doc_processor.process_document(raw_doc)
                    if chunks:
                        added = self.chroma_manager.add_chunks(chunks)
                        total_chunks_added += added
            except Exception as e:
                logger.error(f"Scraper '{name}' çalışırken hata: {e}")

        logger.info(f"Tarama görevi tamamlandı. Toplam eklenen chunk: {total_chunks_added}")
        return total_chunks_added

    def run_maintenance(self) -> dict[str, Any]:
        """Haftalık veritabanı bakımı (mükerrer silme, skor güncelleme, DB sıkıştırma)."""
        logger.info("Veritabanı ve önbellek bakımı başlatılıyor...")
        results: dict[str, Any] = {}

        # 1. Mükerrer kayıtları temizle (remove_duplicates)
        dedup_count = self.chroma_manager.deduplicate_chunks()
        results["removed_duplicates"] = dedup_count

        # 2. Eski skorları ve meta verileri güncelle (update_stale_scores)
        stale_updated = self.chroma_manager.update_stale_scores()
        results["updated_stale_scores"] = stale_updated

        # 3. Veritabanını sıkıştır ve optimize et (compact_database)
        self.chroma_manager.compact_database()
        results["compacted"] = True

        # 4. Önbellekteki eski dosyaları denetle
        cache_files = list(self.settings.scraper_cache_dir.glob("*.json"))
        results["cache_files_count"] = len(cache_files)

        logger.info(f"Bakım tamamlandı: {results}")
        return results

