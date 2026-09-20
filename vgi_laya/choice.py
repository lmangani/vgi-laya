# Copyright 2024 Lorenzo Mangani - https://github.com/lmangani/vgi-laya

"""``choice()`` — pick one option from a set as a LATERAL-joinable table function.

A *choice* question asks Laya to classify content into one of several options you
define. The answer includes which option was chosen, a confidence score, and the
probability distribution across all options.

Example::

    SELECT t.message, c.choice, c.confidence
    FROM tickets t,
         LATERAL laya.main.choice(t.message,
             instructions => 'Which team should handle this?',
             criteria => MAP {'shipping': 'Lost or delayed packages',
                              'billing': 'Invoice and payment issues',
                              'support': 'General questions'}) c;

Use the confidence to decide when to route automatically vs. escalate to a human.
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

CHOICE_SCHEMA = pa.schema([
    field("choice", pa.string(), "The selected option from the criteria"),
    field("confidence", pa.float64(), "How concentrated the probability distribution was (0-1)"),
    field(
        "probabilities",
        pa.map_(pa.string(), pa.float64()),
        "Probability assigned to each option"
    ),
])

_LATERAL_EXAMPLE = (
    "SELECT c.choice, c.confidence FROM laya.main.choice('My package never arrived', "
    "instructions => 'Which team should handle this?', "
    "criteria => MAP {'shipping': 'Lost packages', 'billing': 'Invoice issues'}) c"
)


def criteria_of(raw: Any) -> dict[str, str]:
    """Convert Arrow MAP to Python dict and validate.

    Args:
        raw: The criteria argument as DuckDB delivered it.

    Returns:
        Dict mapping option names to descriptions.

    Raises:
        ValueError: If criteria is missing or empty.
    """
    if raw is None:
        raise ValueError(
            "choice() requires 'criteria', "
            "e.g. criteria => MAP {'option1': 'Description 1', 'option2': 'Description 2'}"
        )

    if isinstance(raw, dict):
        criteria = raw
    else:
        # Arrow map comes as list of (key, value) pairs
        criteria = {}
        for item in raw:
            if isinstance(item, dict):
                criteria[str(item["key"])] = str(item["value"])
            else:
                criteria[str(item[0])] = str(item[1])

    if not criteria:
        raise ValueError("choice() criteria must have at least two options")

    return criteria


@dataclass(slots=True, frozen=True, kw_only=True)
class ChoiceArgs:
    """``choice(state, instructions =>, criteria =>)``."""

    state: Annotated[str, Arg(0, doc="The content to classify")]
    instructions: Annotated[
        str,
        Arg("instructions", doc="What to classify (required)", default="")
    ] = ""
    criteria: Annotated[
        dict[str, str] | None,
        Arg(
            "criteria",
            arrow_type=pa.map_(pa.string(), pa.string()),
            doc="Options to choose from, as MAP {'option': 'description'}",
            default=None
        )
    ] = None


class ChoiceFunction(RowTransformFunction[ChoiceArgs]):
    """Classify content into one of several options — strictly 1:1."""

    FIXED_SCHEMA: ClassVar[pa.Schema] = CHOICE_SCHEMA

    class Meta:
        """Catalog metadata."""

        name = "choice"
        description = "Classify each row into one of several options with confidence scores"
        categories = ["classification"]
        tags = docs(
            category="classification",
            result_schema=CHOICE_SCHEMA,
            llm=(
                "Classify each row into one of the options defined in criteria using local Laya "
                "inference. Returns the chosen option, a confidence score (how certain the model "
                "was), and probabilities for all options. Use confidence to decide when to "
                "auto-route vs escalate. No API key required."
            ),
            md=(
                "Pick one option from a set for each row.\n\n"
                "### Arguments\n\n"
                "- `state` (positional): The content to classify.\n"
                "- `instructions =>`: What to classify it as.\n"
                "- `criteria =>`: A MAP of options to descriptions.\n\n"
                "### Reading the answer\n\n"
                "- `choice`: The selected option name.\n"
                "- `confidence`: How concentrated the distribution was (0-1). High confidence "
                "means the model was sure; low means it was guessing.\n"
                "- `probabilities`: The probability assigned to each option.\n\n"
                "### Example\n\n"
                "```sql\n"
                "SELECT c.choice, c.confidence\n"
                "FROM laya.main.choice('My package is lost',\n"
                "    instructions => 'Which team?',\n"
                "    criteria => MAP {'shipping': 'Delivery issues',\n"
                "                     'billing': 'Payment issues'}) c;\n"
                "```"
            ),
            example_queries=examples(
                ("Classify a support ticket", _LATERAL_EXAMPLE),
            ),
        )
        examples = [
            FunctionExample(sql=_LATERAL_EXAMPLE, description="Classify a support ticket"),
        ]

    @classmethod
    def on_bind(cls, params: BindParams[ChoiceArgs]) -> BindResponse:
        """Validate arguments at plan time."""
        if not params.args.instructions.strip():
            raise ValueError("choice() requires 'instructions' parameter")
        criteria_of(params.args.criteria)
        return BindResponse(output_schema=cls.FIXED_SCHEMA)

    @classmethod
    def process(
        cls,
        params: ProcessParams[ChoiceArgs],
        state: None,
        batch: pa.RecordBatch,
        out: OutputCollector,
    ) -> None:
        """Classify each row."""
        states = [None if s is None else str(s) for s in batch.column("state").to_pylist()]
        criteria = criteria_of(params.args.criteria)
        results = laya_engine.ask_choice_batch(states, params.args.instructions, criteria)

        output = pa.RecordBatch.from_pydict(
            {
                "choice": [r["choice"] if r else None for r in results],
                "confidence": [r["confidence"] if r else None for r in results],
                "probabilities": [
                    list(r["probabilities"].items()) if r and r.get("probabilities") else None
                    for r in results
                ],
            },
            schema=cls.FIXED_SCHEMA
        )
        out.emit(output.select(params.output_schema.names))
