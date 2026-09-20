# Copyright 2024 Lorenzo Mangani - https://github.com/lmangani/vgi-laya

"""Catalog metadata helpers for VGI functions.

Shared utilities for building consistent function documentation and tags.
"""

from __future__ import annotations

import json
from typing import Any

import pyarrow as pa


def field(name: str, dtype: pa.DataType, doc: str) -> pa.Field:
    """Create a PyArrow field with documentation metadata.

    Args:
        name: Field name.
        dtype: Arrow data type.
        doc: Documentation string for the field.

    Returns:
        A PyArrow Field with doc metadata attached.
    """
    return pa.field(name, dtype, metadata={"doc": doc})


def docs(
    *,
    category: str,
    llm: str,
    md: str,
    result_schema: pa.Schema | None = None,
    example_queries: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a complete tags dict for a function or schema.

    Args:
        category: The category this function belongs to.
        llm: Short doc for LLM consumption.
        md: Full Markdown documentation.
        result_schema: Optional output schema to document.
        example_queries: Optional JSON-encoded example queries.
        extra: Additional tags to merge.

    Returns:
        Complete tags dict for VGI metadata.
    """
    tags: dict[str, Any] = {
        "vgi.category": category,
        "vgi.doc_llm": llm,
        "vgi.doc_md": md,
    }
    if result_schema is not None:
        tags["vgi.result_columns_schema"] = column_comments(result_schema)
    if example_queries is not None:
        tags["vgi.example_queries"] = example_queries
    if extra:
        tags.update(extra)
    return tags


def examples(*pairs: tuple[str, str]) -> str:
    """Encode example queries as JSON for vgi.example_queries tag.

    Args:
        pairs: Tuples of (description, sql).

    Returns:
        JSON-encoded list of example objects.
    """
    return json.dumps([{"description": desc, "sql": sql} for desc, sql in pairs])


def column_comments(schema: pa.Schema) -> str:
    """Extract column documentation from a schema's field metadata.

    Args:
        schema: PyArrow schema with doc metadata on fields.

    Returns:
        JSON-encoded dict of column_name -> doc string.
    """
    comments = {}
    for field in schema:
        if field.metadata and b"doc" in field.metadata:
            comments[field.name] = field.metadata[b"doc"].decode("utf-8")
    return json.dumps(comments)


def keywords(*words: str) -> str:
    """Build a comma-separated keywords string.

    Args:
        words: Individual keywords.

    Returns:
        Comma-separated keywords for vgi.keywords tag.
    """
    return ",".join(words)
