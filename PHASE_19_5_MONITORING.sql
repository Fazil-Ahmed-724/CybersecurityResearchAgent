-- =========================================
-- 1) Overall article processing health
-- =========================================
SELECT
    COUNT(*) AS total_articles,
    COUNT(*) FILTER (WHERE content IS NOT NULL AND content <> '') AS with_content,
    COUNT(*) FILTER (WHERE is_processed = true) AS processed,
    COUNT(*) FILTER (WHERE summary_generated = true) AS summaries_done,
    COUNT(*) FILTER (WHERE embedding_generated = true) AS embeddings_done
FROM articles;


-- =========================================
-- 2) Incomplete article count
-- =========================================
SELECT COUNT(*) AS incomplete_articles
FROM articles
WHERE content IS NULL
   OR content = ''
   OR is_processed = false
   OR summary_generated = false
   OR embedding_generated = false;


-- =========================================
-- 3) Failed task count by stage
-- =========================================
SELECT
    stage,
    COUNT(*) AS failures
FROM failed_tasks
WHERE is_resolved = false
GROUP BY stage
ORDER BY stage;


-- =========================================
-- 4) Latest unresolved failures
-- =========================================
SELECT
    id,
    task_name,
    article_id,
    stage,
    error_message,
    retry_count,
    created_at
FROM failed_tasks
WHERE is_resolved = false
ORDER BY created_at DESC
LIMIT 50;


-- =========================================
-- 5) Resolved vs unresolved failure summary
-- =========================================
SELECT
    is_resolved,
    COUNT(*) AS count
FROM failed_tasks
GROUP BY is_resolved;


-- =========================================
-- 6) Article source counts
-- =========================================
SELECT source, COUNT(*)
FROM articles
GROUP BY source
ORDER BY source;


-- =========================================
-- 7) Articles missing summaries
-- =========================================
SELECT
    id,
    source,
    title,
    processed_at
FROM articles
WHERE content IS NOT NULL
  AND content <> ''
  AND summary_generated = false
ORDER BY id DESC;


-- =========================================
-- 8) Articles missing embeddings
-- =========================================
SELECT
    id,
    source,
    title,
    processed_at
FROM articles
WHERE content IS NOT NULL
  AND content <> ''
  AND embedding_generated = false
ORDER BY id DESC;
