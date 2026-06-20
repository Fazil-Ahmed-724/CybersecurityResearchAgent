import requests
from bs4 import BeautifulSoup


class ArticleScraperService:
    """
    Scrapes full article content from supported sources.
    Currently supports:
    - The Hacker News
    - BleepingComputer
    """

    def __init__(self):
        self.timeout = 20
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/137.0.0.0 Safari/537.36"
            )
        }

    def scrape(self, url: str, source: str) -> str:
        """
        Scrape article content from the given URL based on source.
        Returns extracted text or empty string if extraction fails.
        """

        try:
            response = requests.get(
                url,
                headers=self.headers,
                timeout=self.timeout,
            )
            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            if source == "The Hacker News":
                return self._scrape_hackernews(soup)

            if source == "BleepingComputer":
                return self._scrape_bleepingcomputer(soup)

            return ""

        except Exception as e:
            print(
                f"[Scraper] Error scraping {url}: {e}"
            )
            return ""

    def _scrape_hackernews(self, soup: BeautifulSoup) -> str:
        """
        Extract article content from The Hacker News.
        """

        selectors = [
            "div.articlebody",
            "div[itemprop='articleBody']",
            "div.post-body.entry-content",
        ]

        for selector in selectors:
            container = soup.select_one(selector)
            if container:
                return self._clean_text(container)

        return ""

    def _scrape_bleepingcomputer(self, soup: BeautifulSoup) -> str:
        """
        Extract article content from BleepingComputer.
        """

        selectors = [
            "div.articleBody",
            "div#articleBody",
            "section.articleBody",
        ]

        for selector in selectors:
            container = soup.select_one(selector)
            if container:
                return self._clean_text(container)

        return ""

    def _clean_text(self, container: BeautifulSoup) -> str:
        """
        Remove junk tags and return cleaned article text.
        """

        for tag in container.select(
            "script, style, noscript, iframe, form, "
            ".related-article, .ads, .advertisement"
        ):
            tag.decompose()

        text = container.get_text(
            separator="\n",
            strip=True
        )

        lines = [
            line.strip()
            for line in text.splitlines()
            if line.strip()
        ]

        return "\n".join(lines)