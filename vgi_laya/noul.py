# Copyright 2024 Lorenzo Mangani - https://github.com/lmangani/vgi-laya

"""``noul()`` — a yes/no question as a LATERAL-joinable table function.

A *noul* (yes/no/unsure/likely) is Laya's probability primitive: the answer is
one number between 0 and 1. Near 1 means yes, near 0 means no, and 0.5 means
the model genuinely cannot decide.

Example::

    SELECT t.title, n.noul
    FROM articles t,
         LATERAL laya.main.noul(t.title,
             instructions => 'Is this about machine learning?') n
    WHERE n.noul > 0.5;

Unlike the scalar ``is_interesting()``, this table function can be extended with
additional output columns in the future.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, ClassVar

import pyarrow as pa
from vgi.arguments import Arg
from vgi.invocation import BindResponse
from vgi.metadata import FunctionExample
from vgi.table_function import BindParams, ProcessParams
from vgi.table_in_out_function import RowTransformFunction
from vgi_rpc.rpc import OutputCollector

from vgi_laya import laya_engine
from vgi_laya.meta import docs, examples, field

NOUL_SCHEMA = pa.schema([
    field(
        "noul",
        pa.float64(),
        "Probability between 0 and 1 that the answer is yes; near 1 is yes, near 0 is no, "
        "0.5 is genuinely undecided. NULL when the input state was NULL.",
    ),
])

_LATERAL_EXAMPLE = (
    "SELECT t.title, n.noul "
    "FROM (VALUES ('New database engine released'), ('Cat video goes viral')) t(title), "
    "LATERAL laya.main.noul(t.title, "
    "instructions => 'Is this about technology?') n"
)


def instructions_of(raw: str) -> str:
    """Validate the instructions argument.

    Args:
        raw: The instructions argument.

    Returns:
        The validated instructions string.

    Raises:
        ValueError: If instructions are missing or blank.
    """
    if not raw.strip():
        raise ValueError(
            "noul() requires 'instructions', "
            "e.g. instructions => 'Is this about databases?'"
        )
    return raw


@dataclass(slots=True, frozen=True, kw_only=True)
class NoulArgs:
    """``noul(state, instructions =>)``."""

    state: Annotated[str, Arg(0, doc="The content to evaluate — the per-row input column")]
    instructions: Annotated[
        str,
        Arg("instructions", doc="The yes/no question to answer about each state (required)", default="")
    ] = ""


class NoulFunction(RowTransformFunction[NoulArgs]):
    """Answer one yes/no question per input row — strictly 1:1."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = NOUL_SCHEMA

    class Meta:
        """Catalog metadata."""

        name = "noul"
        description = "Answer a yes/no question about each row as a calibrated probability"
        categories = ["classification"]
        tags = docs(
            category="classification",
            result_schema=NOUL_SCHEMA,
            llm=(
                "Ask one yes/no question about each row using local Laya inference. Returns a "
                "probability between 0 and 1: near 1 is yes, near 0 is no, 0.5 means undecided. "
                "Use under LATERAL to evaluate a whole table. Compare against a threshold you "
                "choose. No API key required."
            ),
            md=(
                "One yes/no question, answered for every input row.\n\n"
                "### Arguments\n\n"
                "- `state` (positional): The content to evaluate — a column under LATERAL.\n"
                "- `instructions =>`: The question, phrased so yes/no makes sense.\n\n"
                "### Reading the answer\n\n"
                "`noul` is a probability: near 1 is yes, near 0 is no, and 0.5 is the model "
                "saying the content does not decide the question. Pick a threshold that suits "
                "your use case.\n\n"
                "### Row semantics\n\n"
                "Strictly one output row per input row. A NULL state yields NULL.\n\n"
                "### When to use this vs is_interesting()\n\n"
                "Use `noul()` when you want the table function form for LATERAL joins. "
                "Use `is_interesting()` when you want a scalar for WHERE/CASE/ORDER BY."
            ),
            example_queries=examples(
                ("Evaluate each row via LATERAL", _LATERAL_EXAMPLE),
            ),
        )
        examples = [
            FunctionExample(sql=_LATERAL_EXAMPLE, description="Evaluate each row via LATERAL"),
        ]

    @classmethod
    def on_bind(cls, params: BindParams[NoulArgs]) -> BindResponse:
        """Validate instructions at plan time."""
        instructions_of(params.args.instructions)
        return BindResponse(output_schema=cls.FIXED_SCHEMA)

    @classmethod
    def process(
        cls,
        params: ProcessParams[NoulArgs],
        state: None,
        batch: pa.RecordBatch,
        out: OutputCollector,
    ) -> None:
        """Answer the question for each row."""
        states = [None if s is None else str(s) for s in batch.column("state").to_pylist()]
        results = laya_engine.ask_noul_batch(states, params.args.instructions)

        output = pa.RecordBatch.from_pydict(
            {"noul": results},
            schema=cls.FIXED_SCHEMA
        )
        out.emit(output.select(params.output_schema.names))
