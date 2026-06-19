import feedparser
from datetime import datetime
from email.utils import parsedate_to_datetime

from app.config.settings import settings


class RSSService:

    def __init__(self):
        self.feeds = [
            {
                "source": "The Hacker News",
                "url": settings.HACKERNEWS_RSS
            },
            {
                "source": "BleepingComputer",
                "url": settings.BLEEPINGCOMPUTER_RSS
            }
        ]

    def fetch_articles(self):
        """
        Fetch articles from all RSS feeds.
        Returns list of articles with title, link, summary, source, and published_at.
        """
        articles = []

        for feed in self.feeds:

            try:
                parsed = feedparser.parse(
                    feed["url"]
                )

                for entry in parsed.entries:

                    # Extract published date from feed entry
                    # Try multiple date fields in order of preference
                    published_at = None

                    # Try published_parsed (most common)
                    if hasattr(entry, "published_parsed") and entry.published_parsed:
                        try:
                            published_at = datetime(*entry.published_parsed[:6])
                        except Exception:
                            pass

                    # Try updated_parsed (for feeds without published)
                    if not published_at and hasattr(entry, "updated_parsed") and entry.updated_parsed:
                        try:
                            published_at = datetime(*entry.updated_parsed[:6])
                        except Exception:
                            pass

                    # Try published string
                    if not published_at and hasattr(entry, "published"):
                        try:
                            published_at = parsedate_to_datetime(
                                entry.published
                            )
                        except Exception:
                            pass

                    # Try updated string
                    if not published_at and hasattr(entry, "updated"):
                        try:
                            published_at = parsedate_to_datetime(
                                entry.updated
                            )
                        except Exception:
                            pass

                    # Fallback to current time if all parsing fails
                    if not published_at:
                        published_at = datetime.now()

                    articles.append(
                        {
                            "title": entry.title,
                            "link": entry.link,
                            "summary": getattr(
                                entry,
                                "summary",
                                ""
                            ),
                            "source": feed["source"],
                            "published_at": published_at
                        }
                    )

            except Exception as e:

                print(f"Error fetching {feed['source']}: {e}")

        return articles

    def fetch_hackernews(self):
        return feedparser.parse(
            settings.HACKERNEWS_RSS
        )

    def fetch_bleepingcomputer(self):
        return feedparser.parse(
            settings.BLEEPINGCOMPUTER_RSS
        )