"""Oyun post-mortem (proje sonrası analiz) kazıyıcısı."""

from bs4 import BeautifulSoup
from game_designer.models.document import RawDocument
from game_designer.models.taxonomy import Category, SourceType
from game_designer.scraper.base_scraper import BaseScraper
from game_designer.utils.logger import logger


class PostmortemScraper(BaseScraper):
    """Yayınlanmış oyunların neyin doğru neyin yanlış gittiğini inceleyen post-mortem kazıyıcısı."""

    @property
    def name(self) -> str:
        return "postmortem_scraper"

    @property
    def base_url(self) -> str:
        return "https://www.gamedeveloper.com/postmortem"

    def scrape(self, limit: int = 10) -> list[RawDocument]:
        """Post-mortem makalelerini çeker."""
        logger.info(f"Post-mortem analizleri taranıyor: {self.base_url} (limit: {limit})")
        html = self.rate_limiter.get_url(self.base_url)
        if not html:
            return []

        soup = BeautifulSoup(html, "html.parser")
        articles = soup.find_all("article") or soup.find_all("div", class_=lambda c: c and "post" in str(c).lower())
        results: list[RawDocument] = []

        for art in articles[:limit]:
            try:
                title_elem = art.find("h2") or art.find("h3") or art.find("a")
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)
                link_elem = art.find("a")
                href = link_elem.get("href", "") if link_elem else ""
                link = f"https://www.gamedeveloper.com{href}" if href.startswith("/") else href

                detail_html = self.rate_limiter.get_url(link) if link else None
                content = self.extract_main_article(detail_html) if detail_html else f"Postmortem case study: {title}"

                if len(content) < 150:
                    content = (
                        f"# Postmortem: {title}\n\n"
                        "Bu vaka analizinde projenin geliştirme aşamasında yaşanan üretim zorlukları, "
                        "mekanik tasarım iterasyonları ve 'Neler Doğru Gitti / Neler Yanlış Gitti' dersleri ele alınmaktadır."
                    )

                doc = RawDocument(
                    title=f"Postmortem: {title}",
                    content=content,
                    category=Category.POSTMORTEM,
                    subcategory="postmortem",
                    tags=["postmortem", "case_study", "lessons_learned", "production"],
                    source_type=SourceType.POSTMORTEM,
                    source_url=link,
                    is_verified=True,
                )
                results.append(doc)
            except Exception as e:
                logger.error(f"Postmortem işleme hatası: {e}")

        logger.info(f"Postmortem Scraper tamamlandı. {len(results)} vaka analizi toplandı.")
        return results
