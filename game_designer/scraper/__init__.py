"""Web scraper and automated data collection engine."""

from game_designer.scraper.base_scraper import BaseScraper
from game_designer.scraper.blog_scraper import BlogScraper
from game_designer.scraper.gamasutra_scraper import GamasutraScraper
from game_designer.scraper.gdc_scraper import GDCScraper
from game_designer.scraper.postmortem_scraper import PostmortemScraper
from game_designer.scraper.rate_limiter import ScraperRateLimiter
from game_designer.scraper.scheduler import ScraperScheduler

__all__ = [
    "BaseScraper",
    "BlogScraper",
    "GamasutraScraper",
    "GDCScraper",
    "PostmortemScraper",
    "ScraperRateLimiter",
    "ScraperScheduler",
]
