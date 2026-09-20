# Copyright 2024 Lorenzo Mangani - https://github.com/lmangani/vgi-laya

"""Laya model wrapper — the ONLY module that loads the model.

All inference goes through this module. The model is loaded lazily on first use
and cached for subsequent calls. This ensures:
1. Fast worker startup (model loads only when needed)
2. Single model instance across all function calls
3. Clean separation between VGI protocol and inference logic
"""

from __future__ import annotations

from typing import Any

from laya import Agent

# Global agent — loaded once, reused for all calls
_agent: Agent | None = None


def get_agent() -> Agent:
    """Get or create the Laya agent (lazy singleton).

    Returns:
        The shared Laya Agent instance.
    """
    global _agent
    if _agent is None:
        _agent = Agent()
    return _agent


def ask_noul(state: str, instructions: str) -> float:
    """Answer a yes/no question as a probability.

    Args:
        state: The content to evaluate.
        instructions: The yes/no question to answer.

    Returns:
        Probability between 0 and 1 that the answer is yes.
    """
    agent = get_agent()
    response = agent.predict(
        state,
        {"q": {"type": "noul", "instructions": instructions}}
    )
    noul_value = response.get("answers", {}).get("q", {}).get("noul")
    return float(noul_value) if noul_value is not None else 0.5


def ask_noul_batch(states: list[str | None], instructions: str) -> list[float | None]:
    """Answer a yes/no question for a batch of states.

    Args:
        states: List of content to evaluate (None elements return None).
        instructions: The yes/no question to answer about each state.

    Returns:
        List of probabilities, None where input was None.
    """
    results: list[float | None] = []
    for state in states:
        if state is None:
            results.append(None)
        else:
            results.append(ask_noul(state, instructions))
    return results


def ask_choice(
    state: str,
    instructions: str,
    criteria: dict[str, str]
) -> dict[str, Any]:
    """Pick one option from a set.

    Args:
        state: The content to evaluate.
        instructions: What to classify.
        criteria: Options to choose from, keyed by option name.

    Returns:
        Dict with 'choice', 'confidence', and 'probabilities'.
    """
    agent = get_agent()
    response = agent.predict(
        state,
        {"q": {"type": "choice", "instructions": instructions, "criteria": criteria}}
    )
    answer = response.get("answers", {}).get("q", {})
    return {
        "choice": answer.get("choice"),
        "confidence": answer.get("confidence"),
        "probabilities": answer.get("probabilities", {}),
    }


def ask_choice_batch(
    states: list[str | None],
    instructions: str,
    criteria: dict[str, str]
) -> list[dict[str, Any] | None]:
    """Pick one option for a batch of states.

    Args:
        states: List of content to evaluate.
        instructions: What to classify.
        criteria: Options to choose from.

    Returns:
        List of result dicts, None where input was None.
    """
    results: list[dict[str, Any] | None] = []
    for state in states:
        if state is None:
            results.append(None)
        else:
            results.append(ask_choice(state, instructions, criteria))
    return results


def ask_score(
    state: str,
    instructions: str,
    criteria: list[str]
) -> dict[str, Any]:
    """Place content on an ordered scale.

    Args:
        state: The content to evaluate.
        instructions: What to score.
        criteria: Ordered scale levels (low to high).

    Returns:
        Dict with 'score' (0-1 position) and 'confidence'.
    """
    agent = get_agent()
    response = agent.predict(
        state,
        {"q": {"type": "score", "instructions": instructions, "criteria": criteria}}
    )
    answer = response.get("answers", {}).get("q", {})
    return {
        "score": answer.get("score"),
        "confidence": answer.get("confidence"),
    }


def ask_score_batch(
    states: list[str | None],
    instructions: str,
    criteria: list[str]
) -> list[dict[str, Any] | None]:
    """Place a batch of content on an ordered scale.

    Args:
        states: List of content to evaluate.
        instructions: What to score.
        criteria: Ordered scale levels.

    Returns:
        List of result dicts, None where input was None.
    """
    results: list[dict[str, Any] | None] = []
    for state in states:
        if state is None:
            results.append(None)
        else:
            results.append(ask_score(state, instructions, criteria))
    return results
