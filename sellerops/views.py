"""Read-only SQL views + SELECT-only gateway.

Rule IDs (cited in audit + errors):
  SEC-SELECT-01 — only a single SELECT statement is allowed.
  SEC-SELECT-02 — no stacked statements, comments, or DDL/DML keywords
                  outside string literals.
  SEC-SELECT-03 — queries may only touch the four published views.
"""

from __future__ import annotations

import re
import sqlite3

VIEWS = {
    "v_listing_quality": """
        CREATE VIEW v_listing_quality AS
        SELECT l.listing_id, l.seller_id, s.name AS seller_name,
               l.price, l.has_image, l.compliance_flags
        FROM listings l JOIN sellers s ON s.seller_id = l.seller_id
    """,
    "v_dispute_backlog": """
        CREATE VIEW v_dispute_backlog AS
        SELECT d.dispute_id, d.order_id, o.seller_id, d.reason_code,
               d.status, d.amount
        FROM disputes d JOIN orders o ON o.order_id = d.order_id
        WHERE d.status = 'open'
    """,
    "v_seller_performance": """
        CREATE VIEW v_seller_performance AS
        SELECT s.seller_id, s.name, s.tier, s.rating, s.defect_rate,
               (SELECT COUNT(*) FROM disputes d JOIN orders o
                 ON o.order_id = d.order_id
                WHERE o.seller_id = s.seller_id AND d.status = 'open') AS open_disputes
        FROM sellers s
    """,
    "v_refund_exposure": """
        CREATE VIEW v_refund_exposure AS
        SELECT o.seller_id, SUM(d.amount) AS pending_refund_total,
               COUNT(*) AS open_dispute_count
        FROM disputes d JOIN orders o ON o.order_id = d.order_id
        WHERE d.status = 'open' AND d.reason_code IN ('not_received', 'damaged')
        GROUP BY o.seller_id
    """,
}

_WRITE_KEYWORDS = re.compile(
    r"\b(insert|update|delete|drop|alter|create|replace|truncate|grant|revoke|attach|detach)\b",
    re.IGNORECASE,
)


def _strip_literals(sql: str) -> str:
    return re.sub(r"'(?:[^']|'')*'", "''", sql)


class GatewayError(Exception):
    def __init__(self, rule_id: str, detail: str):
        super().__init__(f"[{rule_id}] {detail}")
        self.rule_id = rule_id


def install_views(conn: sqlite3.Connection) -> None:
    for ddl in VIEWS.values():
        conn.execute(ddl)
    conn.commit()


def run_query(conn: sqlite3.Connection, sql: str, limit: int = 100) -> list[dict]:
    """Execute a read-only query after gateway checks."""
    text = sql.strip().rstrip(";")
    if not re.match(r"(?is)^\s*select\b", text):
        raise GatewayError("SEC-SELECT-01", "only a single SELECT statement is allowed")
    if ";" in _strip_literals(text):
        raise GatewayError("SEC-SELECT-02", "stacked statements are not allowed")
    if _WRITE_KEYWORDS.search(_strip_literals(text)):
        raise GatewayError("SEC-SELECT-02", "write/DDL keywords are not allowed")
    mentioned = set(re.findall(r"(?i)\bv_\w+", text))
    unknown = mentioned - set(VIEWS)
    if unknown:
        raise GatewayError("SEC-SELECT-03",
                           f"unknown views: {sorted(unknown)}")
    if not re.search(r"(?i)\blimit\b", text):
        text = f"{text} LIMIT {limit}"
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(text).fetchall()
    except sqlite3.Error as exc:
        raise GatewayError("SEC-SELECT-01", f"query failed: {exc}") from exc
    return [dict(r) for r in rows]
