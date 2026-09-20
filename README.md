<p align="center">
  <a href="https://query.farm/vgi/">
    <img src="https://raw.githubusercontent.com/Query-farm/vgi-hackernews/main/docs/vgi-logo.png" alt="Vector Gateway Interface logo" width="320">
  </a>
</p>

<h1 align="center">vgi-laya</h1>

<p align="center">
  Local AI inference for DuckDB — filter, classify, and score rows using natural language.<br>
  A <a href="https://query.farm/vgi/">VGI</a> worker powered by <a href="https://github.com/convaiinnovations/laya">Laya</a> (ModernBERT-large).
</p>

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License: MIT"></a>
  <img src="https://img.shields.io/badge/python-3.13%2B-blue.svg" alt="Python 3.13+">
  <a href="https://query.farm/vgi/"><img src="https://img.shields.io/badge/VGI-Vector%20Gateway%20Interface-2f7d32.svg" alt="VGI"></a>
</p>

---

> **No API keys. No cloud. No cost per query.** Laya runs entirely on your machine using
> ModernBERT-large (~421M parameters). Your data never leaves your computer.

```sql
ATTACH 'laya' (TYPE vgi,
  LOCATION 'uvx --from git+https://github.com/lmangani/vgi-laya vgi-laya');

-- Filter articles by your interests
SELECT * FROM articles
WHERE laya.main.is_interesting(title, 'About databases and distributed systems') > 0.5;

-- Classify support tickets
SELECT body, c.choice AS team, c.confidence
FROM tickets,
     LATERAL laya.main.choice(body,
         instructions => 'Which team should handle this?',
         criteria => MAP {'shipping': 'Delivery issues',
                          'billing': 'Payment problems',
                          'support': 'General questions'}) c;
```

## What is Laya?

[Laya](https://github.com/convaiinnovations/laya) is an open-source "System 1" decision engine. It answers **typed questions** about content:

| Question Type | What it does | Returns |
|--------------|--------------|---------|
| **noul** | Yes/no as probability | `0.0` (no) to `1.0` (yes) |
| **choice** | Pick one option | Selected option + confidence |
| **score** | Rate on ordered scale | Position `0.0` to `1.0` |

Unlike generative AI, Laya doesn't produce text — it makes **decisions**. Fast, typed, and calibrated.

## Quick Start

Nothing to clone or install. [uv](https://docs.astral.sh/uv/) fetches and runs the worker:

```sql
-- Install VGI extension (one time)
FORCE INSTALL vgi FROM community;
LOAD vgi;

-- Attach the Laya worker
ATTACH 'laya' (TYPE vgi,
  LOCATION 'uvx --from git+https://github.com/lmangani/vgi-laya vgi-laya');

-- Start making decisions!
SELECT laya.main.is_interesting('DuckDB releases new optimizer', 'About databases');
-- Returns: 0.87
```

**First run downloads the model** (~1.6GB). Subsequent runs use the cached model and start instantly.

## Functions

### `is_interesting(text, criteria)` — Scalar

A yes/no probability you can use anywhere: WHERE, CASE, ORDER BY.

```sql
-- Filter by relevance
SELECT * FROM news
WHERE laya.main.is_interesting(headline, 'Technology and startups') > 0.6;

-- Rank by interest
SELECT headline, laya.main.is_interesting(headline, 'AI and machine learning') AS relevance
FROM news
ORDER BY relevance DESC;

-- Conditional logic
SELECT headline,
       CASE WHEN laya.main.is_interesting(headline, 'Breaking news') > 0.8
            THEN 'urgent' ELSE 'normal' END AS priority
FROM news;
```

### `noul(text, instructions)` — Table Function

Same as `is_interesting`, but as a LATERAL-joinable table function.

```sql
SELECT t.title, n.noul AS is_technical
FROM posts t,
     LATERAL laya.main.noul(t.title,
         instructions => 'Is this a technical post about programming?') n
WHERE n.noul > 0.5;
```

### `choice(text, instructions, criteria)` — Table Function

Classify content into one of several categories you define.

```sql
-- Route support tickets
SELECT t.id, t.message, c.choice AS department, c.confidence
FROM tickets t,
     LATERAL laya.main.choice(t.message,
         instructions => 'Which department should handle this ticket?',
         criteria => MAP {
             'engineering': 'Bug reports, technical issues, API problems',
             'billing': 'Payment issues, refunds, subscription changes',
             'sales': 'Pricing questions, enterprise inquiries, demos'
         }) c;

-- Only auto-route high-confidence classifications
SELECT * FROM (
    SELECT t.*, c.choice, c.confidence
    FROM tickets t,
         LATERAL laya.main.choice(t.message, ...) c
) WHERE confidence > 0.8;
```

### `score(text, instructions, criteria)` — Table Function

Rate content on an ordered scale.

```sql
-- Prioritize issues by severity
SELECT t.issue, s.score AS severity, s.confidence
FROM incidents t,
     LATERAL laya.main.score(t.issue,
         instructions => 'How severe is this incident?',
         criteria => ['minor inconvenience',
                      'degraded service',
                      'major outage',
                      'critical emergency']) s
ORDER BY s.score DESC;

-- Score ranges from 0.0 (first level) to 1.0 (last level)
```

## Use Cases

### Content Curation & Filtering

```sql
-- Build a personalized news feed
SELECT * FROM rss_items
WHERE laya.main.is_interesting(title || ' ' || description,
    'Interesting to a backend engineer who likes Rust, databases, and distributed systems') > 0.5
ORDER BY published_at DESC;
```

### Dataset Curation for ML

```sql
-- Filter training data by quality
SELECT text, label FROM raw_training_data
WHERE laya.main.is_interesting(text, 'High-quality, well-written text suitable for training') > 0.7;

-- Balance datasets by topic
SELECT text, c.choice AS topic
FROM documents,
     LATERAL laya.main.choice(text,
         instructions => 'What is the main topic?',
         criteria => MAP {'science': '...', 'politics': '...', 'sports': '...'}) c;
```

### Log Analysis & Alerting

```sql
-- Flag anomalous log entries
SELECT timestamp, message, laya.main.is_interesting(message,
    'Error, exception, failure, or unusual system behavior') AS anomaly_score
FROM logs
WHERE anomaly_score > 0.6
ORDER BY anomaly_score DESC;
```

### Research & Literature Review

```sql
-- Filter papers by relevance
SELECT title, abstract FROM arxiv_papers
WHERE laya.main.is_interesting(abstract,
    'Research on transformer architectures, attention mechanisms, or language models') > 0.6;
```

### Content Moderation

```sql
-- Flag potentially problematic content
SELECT post_id, content, s.score AS risk_level
FROM user_posts,
     LATERAL laya.main.score(content,
         instructions => 'How likely is this content to violate community guidelines?',
         criteria => ['clearly fine', 'borderline', 'likely violation', 'severe violation']) s
WHERE s.score > 0.5;
```

### Sentiment Analysis

```sql
-- Analyze customer feedback
SELECT feedback, c.choice AS sentiment, c.confidence
FROM reviews,
     LATERAL laya.main.choice(feedback,
         instructions => 'What is the sentiment of this review?',
         criteria => MAP {
             'positive': 'Happy, satisfied, recommending',
             'neutral': 'Mixed feelings, factual, no strong opinion',
             'negative': 'Unhappy, frustrated, complaining'
         }) c;
```

## Running as HTTP Server

For multiple clients or remote access:

```bash
uvx --from git+https://github.com/lmangani/vgi-laya vgi-laya-http --port 9876
```

```sql
ATTACH 'laya' (TYPE vgi, LOCATION 'http://localhost:9876');
```

## Installation

### From GitHub (recommended)

```bash
uvx --from git+https://github.com/lmangani/vgi-laya vgi-laya
```

### From source

```bash
git clone https://github.com/lmangani/vgi-laya
cd vgi-laya
uv sync
uv run laya_worker.py
```

### As a package

```bash
pip install vgi-laya
vgi-laya  # stdio mode
```

## Requirements

- Python 3.13+
- ~2GB RAM for model inference
- ~1.6GB disk for model cache (downloaded on first run)
- Works on CPU; faster with GPU (CUDA/MPS)

## How It Works

```
┌─────────────┐     VGI Protocol     ┌──────────────┐
│   DuckDB    │ ◄──────────────────► │  vgi-laya    │
│   (SQL)     │    (Arrow IPC)       │  (Python)    │
└─────────────┘                      └──────────────┘
       │                                    │
       │ ATTACH ... (TYPE vgi)              │ laya.Agent()
       │                                    │ .predict(state, questions)
       ▼                                    ▼
  SELECT * FROM data               ModernBERT-large
  WHERE is_interesting(...) > 0.5    (421M params, local)
```

1. DuckDB sends rows to the VGI worker via Arrow IPC
2. The worker evaluates each row using Laya (ModernBERT-large)
3. Results flow back as Arrow arrays
4. All inference happens locally — your data never leaves your machine

## Performance

| Metric | Value |
|--------|-------|
| Model size | ~1.6GB download, ~2GB RAM |
| First query | ~20-30s (model loading) |
| Subsequent queries | ~30-50ms per row (CPU) |
| Batch processing | Faster with GPU |

## License

MIT — see [LICENSE](LICENSE).

---

Built with [DuckDB](https://duckdb.org), [VGI](https://query.farm/vgi/), and [Laya](https://github.com/convaiinnovations/laya).
