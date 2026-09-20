# Copyright 2024 Lorenzo Mangani - https://github.com/lmangani/vgi-laya

"""``is_interesting()`` — a noul question as a scalar expression.

A scalar function that drops straight into WHERE, CASE, ORDER BY — anywhere SQL
expects an expression. Returns the probability that content matches the given
criteria, using local Laya inference.

Example::

    SELECT * FROM articles
    WHERE laya.main.is_interesting(title, 'About distributed systems') > 0.5;

    SELECT title,
           CASE WHEN laya.main.is_interesting(body, 'Technical content') > 0.7
                THEN 'tech' ELSE 'other' END AS category
    FROM posts;
"""

from __future__ import annotations

from typing import Annotated

import pyarrow as pa
from vgi.arguments import ConstParam, Param, Returns
from vgi.metadata import FunctionExample
from vgi.scalar_function import BindParameters, BindResult, ScalarFunction

from vgi_laya import laya_engine
from vgi_laya.meta import docs, examples

_WHERE_EXAMPLE = (
    "SELECT * FROM articles "
    "WHERE laya.main.is_interesting(title, 'About databases and SQL') > 0.5"
)
_SELECT_EXAMPLE = (
    "SELECT laya.main.is_interesting('DuckDB releases new optimizer', 'About databases') AS relevance"
)


def instructions_of(raw: str | None) -> str:
    """Validate the instructions argument.

    Args:
        raw: The instructions argument, or None.

    Returns:
        The validated instructions string.

    Raises:
        ValueError: If instructions are missing or blank.
    """
    if raw is None or not raw.strip():
        raise ValueError(
            "is_interesting() needs instructions as its second argument, "
            "e.g. is_interesting(title, 'About databases and distributed systems')"
        )
    return raw


class IsInterestingFunction(ScalarFunction):
    """``is_interesting(state, instructions)`` — probability content matches criteria."""

    class Meta:
        """Catalog metadata."""

        name = "is_interesting"
        description = "Probability that content matches the given criteria (0-1), using local Laya model"
        categories = ["classification", "scalar"]
        tags = docs(
            category="classification",
            llm=(
                "Ask one yes/no question about a value using local Laya inference (ModernBERT-large). "
                "Returns a probability between 0 and 1: near 1 means yes, near 0 means no, 0.5 is "
                "undecided. Use in WHERE clauses to filter by subjective criteria, in CASE for "
                "conditional logic, or in ORDER BY to rank by relevance. No API key required."
            ),
            md=(
                "A scalar function for filtering by subjective criteria.\n\n"
                "### Arguments\n\n"
                "- `state` (positional): The content to evaluate — a literal or column.\n"
                "- `instructions`: What to look for, phrased so yes/no makes sense.\n\n"
                "### Reading the answer\n\n"
                "The result is a probability: near 1 means the content matches, near 0 means it "
                "doesn't, and 0.5 means the model cannot decide. Compare against a threshold you "
                "choose based on your tolerance for false positives/negatives.\n\n"
                "### Performance\n\n"
                "Inference runs locally on CPU/GPU. First call loads the model (~2GB RAM). "
                "Subsequent calls are fast (~30-50ms per evaluation on CPU).\n\n"
                "### Example\n\n"
                "```sql\n"
                "-- Filter articles by topic\n"
                "SELECT * FROM articles\n"
                "WHERE laya.main.is_interesting(title, 'About databases') > 0.5;\n"
                "```"
            ),
            example_queries=examples(
                ("Filter by topic relevance", _WHERE_EXAMPLE),
                ("Evaluate a single value", _SELECT_EXAMPLE),
            ),
        )
        examples = [
            FunctionExample(sql=_WHERE_EXAMPLE, description="Filter by topic relevance"),
            FunctionExample(sql=_SELECT_EXAMPLE, description="Evaluate a single value"),
        ]

    @classmethod
    def on_bind(cls, params: BindParameters) -> BindResult:
        """Validate instructions at plan time."""
        instructions_of(params.constant_arguments.get(0, default=None))
        return BindResult(output_type=pa.float64())

    @classmethod
    def compute(
        cls,
        state: Annotated[pa.StringArray, Param(doc="The content to evaluate")],
        instructions: Annotated[str, ConstParam(doc="What to look for")],
    ) -> Annotated[pa.DoubleArray, Returns()]:
        """Evaluate each row against the criteria.

        Args:
            state: Per-row content to evaluate.
            instructions: The criteria, constant for all rows.

        Returns:
            Probability per row that the content matches.
        """
        states = [None if s is None else str(s) for s in state.to_pylist()]
        results = laya_engine.ask_noul_batch(states, instructions_of(instructions))
        return pa.array(results, type=pa.float64())
