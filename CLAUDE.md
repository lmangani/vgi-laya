# CLAUDE.md — vgi-laya

Guidance for AI agents (and humans) working in this repository. The README is the
product doc: what the functions are and how to call them. This is the build doc:
how it fits together, and where it bites.

## What this is

A [VGI](https://query.farm/vgi/) worker exposing [Laya](https://github.com/convaiinnovations/laya)
local AI inference to DuckDB. Laya answers *typed* questions about content using
ModernBERT-large (~421M parameters), running entirely on your machine — no API keys,
no cloud calls, no per-query costs.

Three question types:
- **noul** (yes/no/unsure/likely): probability between 0 and 1
- **choice**: pick one option from a set, with confidence
- **score**: place content on an ordered scale

## Layout

One module per function, plus shared infrastructure.

```
laya_worker.py          stdio entry point (the ATTACH LOCATION), PEP-723 self-resolving
serve.py                HTTP entry point (uv run serve.py --port 8000)
vgi_laya/
  __init__.py           version
  worker.py             the catalog: which functions exist, catalog/schema docs
  laya_engine.py        the ONLY module that loads the model
  is_interesting.py     scalar function for WHERE/CASE/ORDER BY
  noul.py               table function for yes/no via LATERAL
  choice.py             table function for classification via LATERAL
  score.py              table function for ordered scales via LATERAL
  meta.py               catalog-tag helpers
tests/
  test_laya_engine.py   model inference tests
  test_functions.py     VGI function tests
  test_end_to_end.py    real SQL via haybarn
```

## Core conventions

- **One inference path.** Every function calls `laya_engine`, which is the only
  module that imports `laya.Agent`. The model loads lazily on first use.
- **Errors throw; only a NULL input is NULL.** An inference failure must propagate.
  A NULL answer is indistinguishable from a NULL input.
- **Validate at bind.** Missing `instructions` or `criteria` should fail when the
  query is planned, before inference runs.
- Python ≥ 3.13, `from __future__ import annotations`, Google docstrings.
- Copyright header: `# Copyright 2024 Lorenzo Mangani - https://github.com/lmangani/vgi-laya`.

## The model

Laya uses ModernBERT-large, a modern encoder model (~421M parameters) trained for
classification tasks. Key characteristics:

- **First load**: Downloads ~1.6GB from HuggingFace Hub
- **Memory**: ~2GB RAM for inference
- **Speed**: ~30-50ms per evaluation on CPU, faster on GPU
- **Caching**: Model is cached after first download

The model is loaded as a singleton in `laya_engine.get_agent()`. All functions
share the same instance.

## Sharp edges

1. **First-call latency.** The first query downloads and loads the model (~20-30s).
   Subsequent queries in the same session are fast.

2. **Memory pressure.** The model needs ~2GB RAM. On memory-constrained systems,
   inference may be slow due to swapping.

3. **No batching optimization yet.** Current implementation processes rows one at a
   time. Future versions could batch for GPU efficiency.

4. **PEP-723 headers must match pyproject.toml.** The headers in `laya_worker.py`
   and `serve.py` are what `uv run` resolves. Keep them in sync with
   `[project.dependencies]`.

## Testing

```sh
uv run pytest -v                 # all tests
uv run pytest tests/test_laya_engine.py  # just model tests
```

The end-to-end tests require `haybarn` (DuckDB with VGI extension). They skip
automatically if haybarn is not found.

## Running

### Stdio (default)

```sql
ATTACH 'laya' (TYPE vgi, LOCATION 'uv run laya_worker.py');
```

### HTTP server

```bash
uv run serve.py --port 9876
```

```sql
ATTACH 'laya' (TYPE vgi, LOCATION 'http://localhost:9876');
```

### From installed package

```bash
pip install vgi-laya
vgi-laya        # stdio
vgi-laya-http   # http
```

## Use cases

This worker is designed for:

- **Content filtering**: Keep articles/posts matching your interests
- **Ticket routing**: Classify support requests to the right team
- **Severity triage**: Prioritize issues by urgency
- **Dataset curation**: Filter training data by quality or relevance
- **Log analysis**: Flag anomalous or important entries
- **Research filtering**: Find papers/articles on specific topics
- **Content moderation**: Flag potentially problematic content
- **Sentiment detection**: Classify positive/negative/neutral

All inference runs locally, so it's suitable for:
- Sensitive data that can't leave your machine
- Offline environments
- Cost-sensitive batch processing
- Development and prototyping
