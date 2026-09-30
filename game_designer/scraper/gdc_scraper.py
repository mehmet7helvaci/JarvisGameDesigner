"""GDC (Game Developers Conference) konuşma ve makale kazıyıcısı."""

from bs4 import BeautifulSoup
from game_designer.models.document import RawDocument
from game_designer.models.taxonomy import Category, SourceType
from game_designer.scraper.base_scraper import BaseScraper
from game_designer.utils.logger import logger


class GDCScraper(BaseScraper):
    """GDC Vault ücretsiz yayınlarını ve özetlerini tarayan kazıyıcı."""

    @property
    def name(self) -> str:
        return "gdc_scraper"

    @property
    def base_url(self) -> str:
        return "https://www.gdcvault.com"

    def scrape(self, limit: int = 10) -> list[RawDocument]:
        """GDC Vault ücretsiz konuşma listesinden verileri çeker."""
        target_url = f"{self.base_url}/free"
        logger.info(f"GDC Vault taranıyor: {target_url} (limit: {limit})")

        html_content = self.rate_limiter.get_url(target_url)
        if not html_content:
            logger.warning("GDC Vault içeriği alınamadı.")
            return []

        soup = BeautifulSoup(html_content, "html.parser")
        items = soup.find_all("tr", class_=lambda c: c and "talk" in c) or soup.find_all("div", class_=lambda c: c and "session" in str(c).lower())
        results: list[RawDocument] = []

        for item in items[:limit]:
            try:
                title_elem = item.find("a")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                href = title_elem.get("href", "")
                link = f"{self.base_url}{href}" if href.startswith("/") else href

                speaker_elem = item.find(class_=lambda c: c and "speaker" in str(c).lower())
                speaker = speaker_elem.get_text(strip=True) if speaker_elem else None

                desc_elem = item.find(class_=lambda c: c and "desc" in str(c).lower())
                description = desc_elem.get_text(strip=True) if desc_elem else f"GDC Talk on game design principles: {title}"

                # Detay sayfasına istek
                detail_html = self.rate_limiter.get_url(link) if link else None
                content = self.extract_main_article(detail_html) if detail_html else description

                if len(content) < 100:
                    content = f"# {title}\n\n**Konuşmacı:** {speaker or 'GDC Speaker'}\n\n{description}"

                doc = RawDocument(
                    title=f"GDC: {title}",
                    content=content,
                    category=Category.CORE_MECHANICS,
                    subcategory="gdc_talk",
                    tags=["gdc", "industry_talk", "game_design"],
                    source_type=SourceType.GDC_TALK,
                    source_url=link,
                    author=speaker,
                    is_verified=True,
                )
                results.append(doc)
            except Exception as e:
                logger.error(f"GDC öğesi işlenirken hata: {e}")

        logger.info(f"GDC Scraper tamamlandı. {len(results)} doküman toplandı.")
        return results
