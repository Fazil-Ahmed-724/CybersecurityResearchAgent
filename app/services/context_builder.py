class ContextBuilder:

    MAX_CONTEXT = 6000

    def build(self, articles):

        filtered_articles = [
            article
            for article in articles
            if article["distance"] < 0.35
        ]

        if not filtered_articles:
            return "No relevant articles found."

        sections = []

        current_length = 0

        for index, article in enumerate(
            filtered_articles,
            start=1
        ):

            summary = article["summary"] or ""

            section = f"""
ARTICLE {index}

TITLE:
{article['title']}

SOURCE:
{article['source']}

SUMMARY:
{summary}
"""

            if current_length + len(section) > self.MAX_CONTEXT:
                break

            sections.append(section)

            current_length += len(section)

        return "\n\n".join(sections)