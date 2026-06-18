class ContextBuilder:

    MAX_CONTEXT = 6000

    def build(self, articles):

        if not articles:
            return "No relevant articles found."

        sections = []

        current_length = 0

        for index, article in enumerate(
            articles,
            start=1
        ):

            summary = article.get("summary", "") or ""

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

        context = "\n\n".join(sections)

        print("\n" + "=" * 50)
        print("CONTEXT BUILT")
        print("=" * 50)
        print(context[:1000])

        return context