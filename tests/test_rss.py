from app.services.rss_service import RSSService

rss = RSSService()

feed = rss.fetch_hackernews()

for item in feed.entries[:5]:
    print(item.title)