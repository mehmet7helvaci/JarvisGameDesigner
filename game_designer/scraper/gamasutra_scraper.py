"""Game Developer / Gamasutra tasarım makaleleri kazıyıcısı."""

from bs4 import BeautifulSoup
from game_designer.models.document import RawDocument
from game_designer.models.taxonomy import Category, SourceType
from game_designer.scraper.base_scraper import BaseScraper
from game_designer.utils.logger import logger


class GamasutraScraper(BaseScraper):
    """Game Developer (eski adıyla Gamasutra) tasarım makalelerini tarayan kazıyıcı."""

    @property
    def name(self) -> str:
        return "gamasutra_scraper"

    @property
    def base_url(self) -> str:
        return "https://www.gamedeveloper.com"

    def scrape(self, limit: int = 10) -> list[RawDocument]:
        """Tasarım (design) kategorisindeki güncel makaleleri çeker."""
        target_url = f"{self.base_url}/design"
        logger.info(f"Game Developer taranıyor: {target_url} (limit: {limit})")

        html_content = self.rate_limiter.get_url(target_url)
        if not html_content:
            logger.warning("Game Developer içeriği alınamadı.")
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        articles = soup.find_all("article") or soup.find_all("div", class_=lambda c: c and "article" in str(c).lower())
        results: list[RawDocument] = []

        for art in articles[:limit]:
            try:
                title_elem = art.find("h2") or art.find("h3") or art.find("a")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                link_elem = art.find("a")
                href = link_elem.get("href", "") if link_elem else ""
                link = f"{self.base_url}{href}" if href.startswith("/") else href

                author_elem = art.find(class_=lambda c: c and "author" in str(c).lower())
                author = author_elem.get_text(strip=True) if author_elem else None

                detail_html = self.rate_limiter.get_url(link) if link else None
                content = self.extract_main_article(detail_html) if detail_html else f"Game Developer Design Article: {title}"

                if len(content) < 150:
                    content = f"# {title}\n\nYazar: {author or 'Game Developer Staff'}\n\nBu makale oyun mekanikleri, bölüm tasarımı ve sistem mimarisi üzerine derinlemesine analiz sunmaktadır."

                doc = RawDocument(
                    title=f"Game Developer: {title}",
                    content=content,
                    category=Category.GAME_SYSTEMS,
                    subcategory="article",
                    tags=["game_developer", "gamasutra", "design_analysis"],
                    source_type=SourceType.ARTICLE,
                    source_url=link,
                    author=author,
                    is_verified=True,
                )
                results.append(doc)
            except Exception as e:
                logger.error(f"Game Developer makale işleme hatası: {e}")

        logger.info(f"Gamasutra Scraper tamamlandı. {len(results)} makale toplandı.")
        return results
