"""Web kazıyıcılar için temel soyut sınıf (BaseScraper)."""

from abc import ABC, abstractmethod
from typing import Any
from bs4 import BeautifulSoup

from game_designer.config import Settings, get_settings
from game_designer.models.document import RawDocument
from game_designer.scraper.rate_limiter import ScraperRateLimiter
from game_designer.utils.logger import logger
from game_designer.utils.text_utils import clean_text


class BaseScraper(ABC):
    """Tüm oyun tasarımı web kazıyıcılarının türetileceği temel sınıf."""

    def __init__(
        self,
        settings: Settings | None = None,
        rate_limiter: ScraperRateLimiter | None = None,
    ) -> None:
        self.settings = settings or get_settings()
        self.rate_limiter = rate_limiter or ScraperRateLimiter(self.settings)

    @property
    @abstractmethod
    def name(self) -> str:
        """Kazıyıcının benzersiz adı."""
        ...

    @property
    @abstractmethod
    def base_url(self) -> str:
        """Hedef web sitesinin ana URL'si."""
        ...

    @abstractmethod
    def scrape(self, limit: int = 10) -> list[RawDocument]:
        """Belirtilen limit kadar güncel makaleyi/konuşmayı çeker."""
        ...

    def extract_main_article(self, html_content: str) -> str:
        """HTML içinden ana makale metnini çıkarır, gereksiz tag'leri eler."""
        soup = BeautifulSoup(html_content, "html.parser")

        # Gereksiz kısımları temizle
        for tag in soup(["script", "style", "nav", "footer", "header", "aside", "form"]):
            tag.extract()

        # Olası ana içerik kaplarını ara
        main_container = (
            soup.find("article")
            or soup.find("main")
            or soup.find(class_=lambda c: c and any(k in str(c).lower() for k in ["article-body", "post-content", "entry-content", "content-body"]))
            or soup.body
        )

        if main_container:
            return clean_text(main_container.get_text(separator="\n\n"))
        return clean_text(soup.get_text(separator="\n\n"))
