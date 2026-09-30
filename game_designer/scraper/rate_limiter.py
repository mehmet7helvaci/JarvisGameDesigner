"""Scraper istek hız sınırlayıcı ve robots.txt denetleyicisi."""

import hashlib
import json
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser
import requests

from game_designer.config import Settings, get_settings
from game_designer.utils.logger import logger


class ScraperRateLimiter:
    """Etik web tarama kurallarını (robots.txt, hız sınırı, önbellek) uygulayan sınıf."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self.cache_dir = self.settings.scraper_cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self._domain_last_request: dict[str, float] = {}
        self._robots_parsers: dict[str, RobotFileParser] = {}

    def _get_cache_path(self, url: str) -> Path:
        """URL için önbellek dosya yolu üretir."""
        url_hash = hashlib.sha256(url.encode("utf-8")).hexdigest()
        return self.cache_dir / f"{url_hash}.json"

    def is_allowed_by_robots(self, url: str) -> bool:
        """Hedef URL'in robots.txt tarafından taranmasına izin verilip verilmediğini kontrol eder."""
        if not self.settings.scraping.respect_robots_txt:
            return True

        parsed = urlparse(url)
        domain = f"{parsed.scheme}://{parsed.netloc}"

        if domain not in self._robots_parsers:
            rp = RobotFileParser()
            robots_url = f"{domain}/robots.txt"
            try:
                rp.set_url(robots_url)
                rp.read()
                self._robots_parsers[domain] = rp
            except Exception as e:
                logger.warning(f"robots.txt okunamadı ({robots_url}): {e}. Varsayılan olarak izin veriliyor.")
                return True

        parser = self._robots_parsers[domain]
        allowed = parser.can_fetch(self.settings.scraping.user_agent, url)
        return allowed

    def get_url(self, url: str, use_cache: bool = True, timeout: int = 15) -> str | None:
        """Hız sınırına ve robots.txt kurallarına uyarak HTTP GET isteği yapar veya önbellekten döner."""
        if not self.is_allowed_by_robots(url):
            logger.warning(f"robots.txt gereği taranması engellendi: {url}")
            return None

        cache_path = self._get_cache_path(url)
        if use_cache and self.settings.scraping.cache_responses and cache_path.exists():
            try:
                with open(cache_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                logger.debug(f"Önbellekten çekildi: {url}")
                return data.get("content")
            except Exception as e:
                logger.error(f"Önbellek okuma hatası: {e}")

        # Domain bazlı hız sınırı (rate limit)
        parsed = urlparse(url)
        domain = parsed.netloc
        now = time.time()
        last_req = self._domain_last_request.get(domain, 0.0)
        min_delay = self.settings.scraping.rate_limit_seconds

        elapsed = now - last_req
        if elapsed < min_delay:
            sleep_time = min_delay - elapsed
            logger.debug(f"Hız sınırı bekleniyor ({domain}): {sleep_time:.2f} saniye")
            time.sleep(sleep_time)

        headers = {
            "User-Agent": self.settings.scraping.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9,tr;q=0.8",
        }

        try:
            resp = requests.get(url, headers=headers, timeout=timeout)
            self._domain_last_request[domain] = time.time()

            if resp.status_code == 200:
                html_content = resp.text
                if self.settings.scraping.cache_responses:
                    with open(cache_path, "w", encoding="utf-8") as f:
                        json.dump({"url": url, "timestamp": time.time(), "content": html_content}, f)
                return html_content
            else:
                logger.warning(f"İstek başarısız oldu ({resp.status_code}): {url}")
                return None
        except Exception as e:
            logger.error(f"HTTP isteği hatası ({url}): {e}")
            return None
