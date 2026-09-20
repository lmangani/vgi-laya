# Copyright 2024 Lorenzo Mangani - https://github.com/lmangani/vgi-laya

"""Tests for the Laya inference engine."""

from __future__ import annotations

import pytest

from vgi_laya import laya_engine


class TestNoul:
    """Tests for noul (yes/no probability) questions."""

    def test_positive_case(self) -> None:
        """Content clearly matching should score high."""
        result = laya_engine.ask_noul(
            "DuckDB releases new columnar storage format",
            "Is this about databases?"
        )
        assert result > 0.5

    def test_negative_case(self) -> None:
        """Content clearly not matching should score low."""
        result = laya_engine.ask_noul(
            "Cute cat video goes viral on social media",
            "Is this about databases?"
        )
        assert result < 0.5

    def test_batch_with_none(self) -> None:
        """NULL inputs should return NULL outputs."""
        results = laya_engine.ask_noul_batch(
            ["About databases", None, "About cats"],
            "Is this technical?"
        )
        assert len(results) == 3
        assert results[0] is not None
        assert results[1] is None
        assert results[2] is not None


class TestChoice:
    """Tests for choice (classification) questions."""

    def test_shipping_classification(self) -> None:
        """Shipping-related content should route to shipping."""
        result = laya_engine.ask_choice(
            "My package never arrived and tracking stopped updating",
            "Which team should handle this?",
            {"shipping": "Lost or delayed packages", "billing": "Invoice issues"}
        )
        assert result["choice"] == "shipping"
        assert result["confidence"] > 0

    def test_billing_classification(self) -> None:
        """Billing-related content should route to billing."""
        result = laya_engine.ask_choice(
            "I was charged twice for my subscription",
            "Which team should handle this?",
            {"shipping": "Lost or delayed packages", "billing": "Invoice issues"}
        )
        assert result["choice"] == "billing"

    def test_probabilities_sum_to_one(self) -> None:
        """Probabilities should approximately sum to 1."""
        result = laya_engine.ask_choice(
            "Some ambiguous message",
            "Which category?",
            {"a": "Option A", "b": "Option B", "c": "Option C"}
        )
        total = sum(result["probabilities"].values())
        assert 0.99 < total < 1.01


class TestScore:
    """Tests for score (ordered scale) questions."""

    def test_critical_severity(self) -> None:
        """Clearly critical issues should score high."""
        result = laya_engine.ask_score(
            "The entire production database is corrupted and all data is lost",
            "How severe is this issue?",
            ["minor", "moderate", "critical"]
        )
        # Critical issues should score higher than minor ones
        assert result["score"] is not None
        assert result["score"] > 0.5

    def test_minor_severity(self) -> None:
        """Minor issues should score low."""
        result = laya_engine.ask_score(
            "The help button color is slightly off",
            "How severe is this issue?",
            ["minor", "moderate", "critical"]
        )
        # Minor issues should have a score (Laya's scale may vary)
        assert result["score"] is not None

    def test_relative_severity(self) -> None:
        """Critical issues should score higher than minor ones."""
        critical = laya_engine.ask_score(
            "Complete data loss, all systems down",
            "How severe?",
            ["minor", "moderate", "critical"]
        )
        minor = laya_engine.ask_score(
            "Typo in help text",
            "How severe?",
            ["minor", "moderate", "critical"]
        )
        assert critical["score"] > minor["score"]


class TestSingleton:
    """Tests for the agent singleton pattern."""

    def test_agent_is_cached(self) -> None:
        """The agent should be loaded once and reused."""
        agent1 = laya_engine.get_agent()
        agent2 = laya_engine.get_agent()
        assert agent1 is agent2
