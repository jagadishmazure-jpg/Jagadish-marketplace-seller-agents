"""Gateway bypasses found in review (2026-10-18); each used to succeed.

Before the SQLite-authorizer backstop the gateway had no view allowlist:
base tables and sqlite_master were readable, including through a comma join,
a quoted name or a comment used as whitespace, and any caller-written LIMIT skipped the 100-row cap.
"""
import pytest

from sellerops.telemetry import build_db
from sellerops.views import VIEWS, GatewayError, install_views, run_query


@pytest.fixture
def conn():
    c = build_db()
    install_views(c)
    yield c
    c.close()


def _run(conn, sql):
    return run_query(conn, sql)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM sellers",                                   # base table named directly
    "SELECT * FROM v_listing_quality, sellers",                           # comma join
    'SELECT name, sql FROM "sqlite_master"',                  # quoted schema table
    "SELECT * FROM/**/sellers",                                # comment as whitespace
])
def test_base_table_and_schema_reads_are_denied(conn, sql):
    with pytest.raises(GatewayError) as err:
        _run(conn, sql)
    assert "SEC-SELECT-03" in str(err.value)


@pytest.mark.parametrize("tail", ["LIMIT 100000", "LIMIT 100000 -- x", "LIMIT 100000 OFFSET 0"])
def test_caller_limit_cannot_exceed_the_cap(conn, tail):
    sql = f"SELECT a.* FROM v_listing_quality a JOIN v_listing_quality b JOIN v_listing_quality c {tail}"
    assert len(_run(conn, sql)) == 100


def test_view_self_join_is_not_falsely_denied(conn):
    # A flattened view whose tables supply no columns makes SQLite report an
    # empty-column read with no view name; that must still be allowed.
    assert _run(conn, "SELECT a.* FROM v_listing_quality a JOIN v_listing_quality b LIMIT 5")


def test_every_view_still_readable(conn):
    for v in VIEWS:
        _run(conn, f"SELECT * FROM {v}")


def test_authorizer_is_removed_after_the_query(conn):
    _run(conn, "SELECT * FROM v_listing_quality")
    assert conn.execute("SELECT count(*) FROM sellers").fetchone()[0] > 0
