# Copyright 2024 Lorenzo Mangani - https://github.com/lmangani/vgi-laya

"""End-to-end tests using real DuckDB with VGI extension.

These tests require haybarn (DuckDB with VGI) to be available.
They are skipped automatically if haybarn is not installed.
"""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

# Skip all tests in this module if haybarn is not available
try:
    import haybarn
    HAS_HAYBARN = True
except ImportError:
    HAS_HAYBARN = False

pytestmark = pytest.mark.skipif(not HAS_HAYBARN, reason="haybarn not installed")


@pytest.fixture
def connection():
    """Create a DuckDB connection with VGI loaded."""
    import haybarn
    con = haybarn.connect()
    con.execute("FORCE INSTALL vgi FROM community")
    con.execute("LOAD vgi")

    # Attach the Laya worker using the local source
    worker_path = os.path.join(os.path.dirname(__file__), "..", "laya_worker.py")
    worker_path = os.path.abspath(worker_path)
    con.execute(f"ATTACH 'laya' (TYPE vgi, LOCATION 'uv run {worker_path}')")

    yield con
    con.close()


class TestIsInteresting:
    """Tests for the is_interesting scalar function."""

    def test_basic_query(self, connection) -> None:
        """Basic is_interesting query should work."""
        result = connection.execute(
            "SELECT laya.main.is_interesting('About databases', 'Technical content')"
        ).fetchone()
        assert result is not None
        assert 0.0 <= result[0] <= 1.0

    def test_in_where_clause(self, connection) -> None:
        """is_interesting should work in WHERE clause."""
        result = connection.execute("""
            SELECT title FROM (
                VALUES ('Database optimization tips'),
                       ('Cute cat pictures'),
                       ('SQL performance tuning')
            ) t(title)
            WHERE laya.main.is_interesting(title, 'About databases') > 0.5
        """).fetchall()
        # Should return the database-related rows
        assert len(result) >= 1


class TestNoul:
    """Tests for the noul table function."""

    def test_lateral_join(self, connection) -> None:
        """noul should work with LATERAL join."""
        result = connection.execute("""
            SELECT t.title, n.noul
            FROM (VALUES ('Technical blog post'), ('Cat video')) t(title),
                 LATERAL laya.main.noul(t.title,
                     instructions => 'Is this technical content?') n
        """).fetchall()
        assert len(result) == 2
        # Both should have noul values
        assert all(0.0 <= row[1] <= 1.0 for row in result)


class TestChoice:
    """Tests for the choice table function."""

    def test_classification(self, connection) -> None:
        """choice should classify content."""
        result = connection.execute("""
            SELECT c.choice, c.confidence
            FROM laya.main.choice('My package is lost',
                instructions => 'Which team?',
                criteria => MAP {'shipping': 'Delivery', 'billing': 'Payments'}) c
        """).fetchone()
        assert result is not None
        assert result[0] in ("shipping", "billing")
        assert 0.0 <= result[1] <= 1.0


class TestScore:
    """Tests for the score table function."""

    def test_severity_rating(self, connection) -> None:
        """score should rate content on a scale."""
        result = connection.execute("""
            SELECT s.score, s.confidence
            FROM laya.main.score('The site is completely down',
                instructions => 'How severe?',
                criteria => ['minor', 'moderate', 'critical']) s
        """).fetchone()
        assert result is not None
        # Score is a weighted position; may exceed 1.0 for critical issues
        assert result[0] is not None
        assert result[1] is not None
