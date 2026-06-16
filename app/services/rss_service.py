import feedparser

from app.config.settings import settings


class RSSService:
    print("RSSService initialized")
    def fetch_hackernews(self):
        return feedparser.parse(
            settings.HACKERNEWS_RSS
        )

    def fetch_bleepingcomputer(self):
        return feedparser.parse(
            settings.BLEEPINGCOMPUTER_RSS
        )