-- vgi-laya Demo: Filter Content by Taste
-- =======================================
-- This demo shows how to use local AI inference to filter content
-- using natural language criteria — a "WHERE clause for taste".

-- Setup: Install and load VGI extension
FORCE INSTALL vgi FROM community;
LOAD vgi;

-- Attach the Hacker News worker (fetches stories from public HN API)
ATTACH 'hackernews' (TYPE vgi,
  LOCATION 'uvx --from git+https://github.com/Query-farm/vgi-hackernews vgi-hackernews');

-- Attach the Laya worker (local ModernBERT inference — no API key needed)
ATTACH 'laya' (TYPE vgi,
  LOCATION 'uvx --from git+https://github.com/lmangani/vgi-laya vgi-laya');

-- Step 4: Fetch top stories and filter by taste!
-- This is the magic: SQL WHERE clause powered by local AI inference
WITH scored_stories AS (
    SELECT
        title,
        url,
        score AS hn_score,
        laya.main.is_interesting(
            title,
            'Interesting to someone who likes databases, DuckDB, distributed systems, Python, Apache Arrow'
        ) AS interest_score
    FROM hackernews.top_stories
    LIMIT 100  -- Score top 100 stories
)
SELECT * FROM scored_stories
WHERE interest_score > 0.5
ORDER BY interest_score DESC
LIMIT 20;

-- Alternative: Using LATERAL join for more detailed output
-- SELECT
--     hn.title,
--     hn.url,
--     hn.score AS hn_score,
--     n.noul AS interest_score
-- FROM hackernews.top_stories hn,
--      LATERAL laya.main.noul(hn.title,
--          instructions => 'Is this story interesting to someone who likes databases, DuckDB, distributed systems, Python, and Apache Arrow?') n
-- WHERE n.noul > 0.5
-- ORDER BY n.noul DESC
-- LIMIT 20;
