# Copyright 2024 Lorenzo Mangani - https://github.com/lmangani/vgi-laya

"""``score()`` — place content on an ordered scale as a LATERAL-joinable table function.

A *score* question asks Laya to rate content on a scale you define. Unlike choice
(which picks exactly one option), score returns a weighted position based on the
probability distribution across all levels.

Example::

    SELECT t.issue, s.score, s.confidence
    FROM tickets t,
         LATERAL laya.main.score(t.issue,
             instructions => 'How severe is this issue?',
             criteria => ['minor', 'moderate', 'critical']) s
    WHERE s.score > 0.7;  -- Focus on severe issues

The criteria list should be ordered from low to high.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any, ClassVar

import pyarrow as pa
from vgi.arguments import Arg
from vgi.invocation import BindResponse
from vgi.metadata import FunctionExample
from vgi.table_function import BindParams, ProcessParams
from vgi.table_in_out_function import RowTransformFunction
from vgi_rpc.rpc import OutputCollector

from vgi_laya import laya_engine
from vgi_laya.meta import docs, examples, field

SCORE_SCHEMA = pa.schema([
    field(
        "score",
        pa.float64(),
        "Weighted position on the scale (0-1), where 0 is the first level and 1 is the last"
    ),
    field(
        "confidence",
        pa.float64(),
        "How concentrated the distribution was (0-1); high means the model was sure"
    ),
])

_LATERAL_EXAMPLE = (
    "SELECT s.score, s.confidence FROM laya.main.score('The entire site is down', "
    "instructions => 'How severe is this?', "
    "criteria => ['minor', 'disruptive', 'critical']) s"
)


def criteria_of(raw: Any) -> list[str]:
    """Convert Arrow LIST to Python list and validate.

    Args:
        raw: The criteria argument as DuckDB delivered it.

    Returns:
        List of scale levels, ordered low to high.

    Raises:
        ValueError: If criteria is missing or has fewer than 2 levels.
    """
    if raw is None:
        raise ValueError(
            "score() requires 'criteria', "
            "e.g. criteria => ['minor', 'moderate', 'critical']"
        )

    if isinstance(raw, list):
        criteria = [str(c) for c in raw]
    else:
        # Arrow list
        criteria = [str(c) for c in raw.to_pylist()]

    if len(criteria) < 2:
        raise ValueError("score() criteria must have at least 2 levels")

    return criteria


@dataclass(slots=True, frozen=True, kw_only=True)
class ScoreArgs:
    """``score(state, instructions =>, criteria =>)``."""

    state: Annotated[str, Arg(0, doc="The content to score")]
    instructions: Annotated[
        str,
        Arg("instructions", doc="What to score (required)", default="")
    ] = ""
    criteria: Annotated[
        list[str] | None,
        Arg(
            "criteria",
            arrow_type=pa.list_(pa.string()),
            doc="Ordered scale levels, from lowest to highest",
            default=None
        )
    ] = None


class ScoreFunction(RowTransformFunction[ScoreArgs]):
    """Rate content on an ordered scale — strictly 1:1."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = SCORE_SCHEMA

    class Meta:
        """Catalog metadata."""

        name = "score"
        description = "Rate each row on an ordered scale with confidence scores"
        categories = ["classification"]
        tags = docs(
            category="classification",
            result_schema=SCORE_SCHEMA,
            llm=(
                "Rate each row on an ordered scale using local Laya inference. The scale is "
                "defined by criteria (a list ordered low-to-high). Returns a score from 0 to 1 "
                "representing the weighted position, plus confidence. Use for severity ratings, "
                "quality assessments, or any ordered judgment. No API key required."
            ),
            md=(
                "Place content on an ordered scale.\n\n"
                "### Arguments\n\n"
                "- `state` (positional): The content to score.\n"
                "- `instructions =>`: What aspect to score.\n"
                "- `criteria =>`: A LIST of scale levels, ordered low to high.\n\n"
                "### Reading the answer\n\n"
                "- `score`: Position on the scale (0-1). 0 means the first level, 1 means the "
                "last. This is a weighted average based on the probability distribution.\n"
                "- `confidence`: How concentrated the distribution was.\n\n"
                "### Example\n\n"
                "```sql\n"
                "-- Rate issue severity\n"
                "SELECT s.score FROM laya.main.score('Site is slow',\n"
                "    instructions => 'How severe?',\n"
                "    criteria => ['minor', 'moderate', 'critical']) s;\n"
                "```"
            ),
            example_queries=examples(
                ("Rate severity", _LATERAL_EXAMPLE),
            ),
        )
        examples = [
            FunctionExample(sql=_LATERAL_EXAMPLE, description="Rate severity"),
        ]

    @classmethod
    def on_bind(cls, params: BindParams[ScoreArgs]) -> BindResponse:
        """Validate arguments at plan time."""
        if not params.args.instructions.strip():
            raise ValueError("score() requires 'instructions' parameter")
        criteria_of(params.args.criteria)
        return BindResponse(output_schema=cls.FIXED_SCHEMA)

    @classmethod
    def process(
        cls,
        params: ProcessParams[ScoreArgs],
        state: None,
        batch: pa.RecordBatch,
        out: OutputCollector,
    ) -> None:
        """Score each row."""
        states = [None if s is None else str(s) for s in batch.column("state").to_pylist()]
        criteria = criteria_of(params.args.criteria)
        results = laya_engine.ask_score_batch(states, params.args.instructions, criteria)

        output = pa.RecordBatch.from_pydict(
            {
                "score": [r["score"] if r else None for r in results],
                "confidence": [r["confidence"] if r else None for r in results],
            },
            schema=cls.FIXED_SCHEMA
        )
        out.emit(output.select(params.output_schema.names))
