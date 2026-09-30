"""Bağımsız ve stüdyo geliştirici blogları kazıyıcısı."""

from game_designer.models.document import RawDocument
from game_designer.models.taxonomy import Category, SourceType
from game_designer.scraper.base_scraper import BaseScraper
from game_designer.utils.logger import logger


class BlogScraper(BaseScraper):
    """Tanınmış oyun stüdyolarının ve tasarımcıların dev blog'larını tarayan kazıyıcı."""

    @property
    def name(self) -> str:
        return "blog_scraper"

    @property
    def base_url(self) -> str:
        return "https://www.gamedeveloper.com/blogs"

    def scrape(self, limit: int = 10) -> list[RawDocument]:
        """Tasarımcı blog yazılarını tarar."""
        logger.info(f"Geliştirici blogları taranıyor: {self.base_url} (limit: {limit})")
        html = self.rate_limiter.get_url(self.base_url)
        if not html:
            return []

        main_text = self.extract_main_article(html)
        results: list[RawDocument] = []

        doc = RawDocument(
            title="Industry Dev Blog Design Insights",
            content=main_text if len(main_text) > 200 else "Geliştirici bloglarından derlenen tasarım dersleri ve mekanik notları.",
            category=Category.GAME_BALANCE,
            subcategory="dev_blog",
            tags=["dev_blog", "indie", "studio_insights"],
            source_type=SourceType.DEV_BLOG,
            source_url=self.base_url,
            is_verified=False,
        )
        results.append(doc)
        return results
