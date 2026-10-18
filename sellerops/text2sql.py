"""Deterministic text-to-SQL over the five read-only views.

Five intents with fixed SQL templates, all run through the gateway. One
simplified retry (``SELECT * FROM <view> LIMIT 20``) on gateway or DB errors;
if the retry also fails, raise EscalationNeeded — never guess.
"""

from __future__ import annotations

import re
import sqlite3

from .views import GatewayError, run_query

INTENTS = (
    "listings_by_quality_band",
    "dispute_backlog",
    "seller_performance",
    "policy_violations",
    "refund_exposure",
)

_TEMPLATES = {
    "listings_by_quality_band": (
        "SELECT listing_id, seller_name, price, has_image, compliance_flags "
        "FROM v_listing_quality"
    ),
    "dispute_backlog": (
        "SELECT dispute_id, order_id, seller_id, reason_code, amount "
        "FROM v_dispute_backlog ORDER BY amount DESC"
    ),
    "seller_performance": (
        "SELECT seller_id, name, tier, rating, defect_rate, open_disputes "
        "FROM v_seller_performance ORDER BY defect_rate DESC"
    ),
    "policy_violations": (
        "SELECT violation_id, seller_id, policy_code, severity FROM v_policy_violations"
    ),
    "refund_exposure": (
        "SELECT seller_id, pending_refund_total, open_dispute_count "
        "FROM v_refund_exposure ORDER BY pending_refund_total DESC"
    ),
}

class EscalationNeeded(Exception):
    pass


def _detect_intent(question: str) -> str | None:
    q = question.lower()
    if any(k in q for k in ("quality", "listing score", "band", "poor listing")):
        return "listings_by_quality_band"
    if any(k in q for k in ("dispute", "backlog", "open case")):
        return "dispute_backlog"
    if any(k in q for k in ("seller performance", "tier", "defect rate", "rating")):
        return "seller_performance"
    if any(k in q for k in ("violation", "policy breach", "enforcement")):
        return "policy_violations"
    if any(k in q for k in ("refund exposure", "exposure", "pending refund")):
        return "refund_exposure"
    return None


def _simplify(question: str) -> str:
    """Narrow an unrecognized question to its safest keyword core."""
    words = [w for w in re.findall(r"[a-z]+", question.lower())
             if w not in {"the", "a", "an", "of", "for", "to", "and", "is", "are", "me", "show"}]
    return " ".join(words[:6])


def answer(conn: sqlite3.Connection, question: str) -> dict:
    intent = _detect_intent(question)
    if intent is None:
        intent = _detect_intent(_simplify(question))  # one simplified retry
    if intent is None:
        raise EscalationNeeded(f"no intent matched: {question!r}")
    sql = _TEMPLATES[intent]
    try:
        rows = run_query(conn, sql)
    except (GatewayError, sqlite3.Error):
        view = re.search(r"\bFROM\s+(v_\w+)", sql).group(1)
        sql = f"SELECT * FROM {view} LIMIT 20"  # one simplified retry
        try:
            rows = run_query(conn, sql)
        except (GatewayError, sqlite3.Error) as exc:
            raise EscalationNeeded(f"query failed after retry: {exc}") from exc
    return {"intent": intent, "sql": sql, "rows": rows, "row_count": len(rows)}
