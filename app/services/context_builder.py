class ContextBuilder:

    def build(self, articles):

        if not articles:
            return "No relevant articles found."

        sections = []

        for index, article in enumerate(articles, start=1):

            section = f"""
ARTICLE {index}

TITLE:
{article["title"]}

SOURCE:
{article["source"]}

SUMMARY:
{article["summary"]}

URL:
{article["url"]}
"""

            sections.append(section)

        return "\n\n".join(sections)