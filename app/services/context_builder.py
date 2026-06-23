class ContextBuilder:

    def build(
        self,
        articles: list[dict]
    ) -> str:

        if not articles:
            return "No relevant articles found."

        blocks = []

        for index, article in enumerate(articles, start=1):
            title = article.get("title", "")
            source = article.get("source", "")
            url = article.get("url", "")
            summary = article.get("summary", "") or ""
            content = article.get("content", "") or ""

            block = f"""
Article {index}
Title: {title}
Source: {source}
URL: {url}

Summary:
{summary}

Content:
{content}
""".strip()

            blocks.append(block)

        return "\n\n" + ("\n\n" + ("-" * 80) + "\n\n").join(blocks)