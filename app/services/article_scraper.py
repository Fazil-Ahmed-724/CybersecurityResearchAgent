import requests
from bs4 import BeautifulSoup


class ArticleScraper:

    def scrape(self, url: str):

        try:
            response = requests.get(
                url,
                timeout=20,
                headers={
                    "User-Agent": "Mozilla/5.0"
                }
            )

            response.raise_for_status()

            soup = BeautifulSoup(
                response.text,
                "lxml"
            )

            paragraphs = soup.find_all("p")

            content = "\n".join(
                p.get_text(strip=True)
                for p in paragraphs
            )

            return content

        except Exception as e:
            print(f"Scraping Error: {e}")
            return None