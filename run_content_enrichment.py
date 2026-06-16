from app.services.content_enrichment import (
    ContentEnrichmentService
)

ContentEnrichmentService().enrich_articles()

print("Content Extraction Completed")