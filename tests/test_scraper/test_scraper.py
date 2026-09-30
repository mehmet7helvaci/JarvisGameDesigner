"""Scraper ve veri toplama motoru testleri."""

import pytest
from game_designer.scraper.base_scraper import BaseScraper
from game_designer.scraper.rate_limiter import ScraperRateLimiter
from game_designer.scraper.scheduler import ScraperScheduler
from game_designer.models.document import RawDocument


class DummyScraper(BaseScraper):
    @property
    def name(self) -> str:
        return "dummy_scraper"

    @property
    def base_url(self) -> str:
        return "https://example.com"

    def scrape(self, limit: int = 10) -> list[RawDocument]:
        return []


def test_scraper_rate_limiter(test_settings):
    limiter = ScraperRateLimiter(test_settings)
    assert limiter.is_allowed_by_robots("https://example.com/test") is True


def test_base_scraper_html_extraction(test_settings):
    scraper = DummyScraper(test_settings)
    sample_html = """
    <html>
      <head><title>Test Game</title></head>
      <body>
        <nav><a href="#">Menu</a></nav>
        <article>
          <h1>Design Mechanics</h1>
          <p>The core loop of this roguelike is fast and challenging.</p>
        </article>
        <footer>Copyright 2026</footer>
      </body>
    </html>
    """
    extracted = scraper.extract_main_article(sample_html)
    assert "Design Mechanics" in extracted
    assert "fast and challenging" in extracted
    assert "Menu" not in extracted
    assert "Copyright" not in extracted


def test_scraper_scheduler_jobs(test_settings):
    scheduler = ScraperScheduler(test_settings)
    scheduler.setup_jobs()

    job_ids = [j.id for j in scheduler.scheduler.get_jobs()]
    assert "auto_scrape_job" in job_ids
    assert "db_maintenance_job" in job_ids
