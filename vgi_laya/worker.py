# Copyright 2024 Lorenzo Mangani - https://github.com/lmangani/vgi-laya

"""VGI worker exposing Laya System 1 decisions to DuckDB/SQL.

    ATTACH 'laya' (TYPE vgi, LOCATION 'uv run laya_worker.py');

    -- Filter by subjective criteria
    SELECT * FROM articles
    WHERE laya.main.is_interesting(title, 'About databases') > 0.5;

    -- Classify into categories
    SELECT t.body, c.choice, c.confidence
    FROM tickets t,
         LATERAL laya.main.choice(t.body,
             instructions => 'Which department?',
             criteria => MAP {'sales': '...', 'support': '...'}) c;

Laya runs locally using ModernBERT-large (~421M params). No API keys, no cloud
calls, no per-query costs. First load downloads the model (~1.6GB); subsequent
sessions use the cached model.
"""

from __future__ import annotations

import json
import sys

from vgi import Worker
from vgi.catalog import Catalog, ReadOnlyCatalogInterface, Schema
from vgi.catalog.catalog_interface import CatalogInfo

from vgi_laya import __version__
from vgi_laya.choice import ChoiceFunction
from vgi_laya.is_interesting import IsInterestingFunction
from vgi_laya.meta import examples, keywords
from vgi_laya.noul import NoulFunction
from vgi_laya.score import ScoreFunction

IMPLEMENTATION_VERSION = __version__
DATA_VERSION_SPEC = f"=={__version__}"
SOURCE_URL = "https://github.com/lmangani/vgi-laya"

_KEYWORDS = keywords(
    "laya",
    "local",
    "inference",
    "classification",
    "modernbert",
    "noul",
    "choice",
    "score",
    "filter",
    "taste",
    "relevance",
    "duckdb",
)

_CATEGORIES = json.dumps([
    {
        "name": "classification",
        "title": "Classification & Filtering",
        "description": (
            "Make typed decisions about rows: yes/no probabilities, pick one option, "
            "or place on an ordered scale. All inference runs locally."
        ),
        "keywords": ["classify", "filter", "score", "route", "rank"],
    },
])

_CATALOG_TAGS = {
    "provider": "laya",
    "domain": "local-ai",
    "vgi.title": "Laya Local Inference",
    "vgi.source_url": SOURCE_URL,
    "vgi.author": "Lorenzo Mangani <lorenzo@mangani.dev>",
    "vgi.license": "MIT",
    "vgi.support_contact": "https://github.com/lmangani/vgi-laya/issues",
    "vgi.keywords": _KEYWORDS,
    "vgi.doc_llm": (
        "Local AI inference for DuckDB using Laya (ModernBERT-large). Make typed decisions "
        "about rows: filter by subjective criteria, classify into categories, or rate on scales. "
        "No API keys, no cloud calls, no costs. Runs entirely on your machine."
    ),
    "vgi.doc_md": (
        "Laya brings local AI inference to SQL through three question types.\n\n"
        "### Question Types\n\n"
        "**noul** (yes/no/unsure/likely): Answer a yes/no question as a probability between "
        "0 and 1. Use for filtering, flagging, or any binary decision.\n\n"
        "**choice**: Pick one option from a set you define. Returns the choice, confidence, "
        "and probability distribution. Use for classification, routing, or categorization.\n\n"
        "**score**: Place content on an ordered scale. Returns a weighted position (0-1). "
        "Use for severity ratings, quality scores, or priority ranking.\n\n"
        "### The Model\n\n"
        "Laya uses ModernBERT-large (~421M parameters), a modern encoder model optimized for "
        "classification tasks. First load downloads ~1.6GB; subsequent runs use the cache. "
        "Inference is ~30-50ms per evaluation on CPU.\n\n"
        "### When to Use\n\n"
        "- **Content filtering**: Keep articles matching your interests\n"
        "- **Ticket routing**: Classify support requests to the right team\n"
        "- **Severity triage**: Prioritize issues by urgency\n"
        "- **Dataset curation**: Filter training data by quality or relevance\n"
        "- **Log analysis**: Flag anomalous or important log entries\n"
    ),
}

_SCHEMA_TAGS = {
    "provider": "laya",
    "domain": "local-ai",
    "vgi.title": "Laya Functions",
    "vgi.keywords": _KEYWORDS,
    "vgi.categories": _CATEGORIES,
    "vgi.example_queries": examples(
        (
            "Filter articles by topic",
            "SELECT * FROM articles WHERE laya.main.is_interesting(title, 'About databases') > 0.5",
        ),
        (
            "Classify support tickets",
            "SELECT t.body, c.choice FROM tickets t, "
            "LATERAL laya.main.choice(t.body, instructions => 'Which team?', "
            "criteria => MAP {'shipping': 'Delivery', 'billing': 'Payments'}) c",
        ),
        (
            "Rate issue severity",
            "SELECT t.issue, s.score FROM tickets t, "
            "LATERAL laya.main.score(t.issue, instructions => 'How severe?', "
            "criteria => ['minor', 'moderate', 'critical']) s WHERE s.score > 0.5",
        ),
    ),
    "vgi.doc_llm": (
        "Make typed decisions about rows using local AI. `is_interesting()` is a scalar for "
        "WHERE/CASE/ORDER BY. `noul()`, `choice()`, and `score()` are table functions for LATERAL. "
        "No API keys required."
    ),
    "vgi.doc_md": (
        "Four functions, each suited to different SQL patterns.\n\n"
        "### Scalars vs Table Functions\n\n"
        "`is_interesting()` is a scalar — use it in WHERE, CASE, or ORDER BY. The others are "
        "table functions — use them with LATERAL for richer output.\n\n"
        "### Choosing the Right Function\n\n"
        "| Need | Function |\n"
        "| --- | --- |\n"
        "| Filter rows by criteria | `is_interesting()` in WHERE |\n"
        "| Yes/no with LATERAL | `noul()` |\n"
        "| Pick one of N options | `choice()` |\n"
        "| Rate on a scale | `score()` |\n"
    ),
}

_LAYA_CATALOG = Catalog(
    name="laya",
    default_schema="main",
    comment="Local AI inference using Laya (ModernBERT-large) — no API keys required",
    tags=_CATALOG_TAGS,
    source_url=SOURCE_URL,
    schemas=[
        Schema(
            path=["main"],
            comment="Laya classification functions for filtering, routing, and scoring",
            tags=_SCHEMA_TAGS,
            functions=[
                IsInterestingFunction,
                NoulFunction,
                ChoiceFunction,
                ScoreFunction,
            ],
        ),
    ],
)


class LayaCatalog(ReadOnlyCatalogInterface):
    """Advertises the worker's versions."""

    catalog = _LAYA_CATALOG
    catalog_name = _LAYA_CATALOG.name
    secret_types = []  # No secrets needed — local inference

    def catalogs(self) -> list[CatalogInfo]:
        """Advertise the Laya catalog."""
        return [
            CatalogInfo(
                name=self._effective_catalog_name,
                implementation_version=IMPLEMENTATION_VERSION,
                data_version_spec=DATA_VERSION_SPEC,
                source_url=SOURCE_URL,
            )
        ]


class LayaWorker(Worker):
    """Worker process hosting the Laya catalog."""

    catalog = _LAYA_CATALOG
    catalog_interface = LayaCatalog


def main() -> None:
    """Run the worker (stdio by default; pass ``--http`` for HTTP server)."""
    LayaWorker.main()


def main_http() -> None:
    """Run the worker over HTTP."""
    argv = sys.argv[1:]
    if "--http" not in argv:
        argv = ["--http", *argv]
    sys.argv = [sys.argv[0], *argv]
    LayaWorker.main()


if __name__ == "__main__":
    main()
