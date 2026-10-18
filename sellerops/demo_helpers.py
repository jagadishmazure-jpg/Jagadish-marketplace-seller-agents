"""Stdlib-only helpers for the thin Streamlit demo (demo/app.py).

All logic lives here so it is fully testable without streamlit installed.
"""

from __future__ import annotations

from .disputes import Dispute, triage
from .quality import score_listing
from .telemetry import ANCHOR_ESCALATE_DISPUTE, ANCHOR_REFUND_DISPUTE, build_db
from .views import install_views


def quality_summary() -> list[dict]:
    conn = build_db()
    rows = conn.execute(
        "SELECT listing_id, title, description, has_image, compliance_flags, price "
        "FROM listings ORDER BY listing_id").fetchall()
    out = []
    for lid, title, desc, img, flags, price in rows:
        r = score_listing(lid, title, desc, bool(img), flags or "", price)
        out.append({"listing_id": lid, "band": r.band, "total": r.total,
                    "breakdown": r.breakdown()})
    return out


def dispute_triage_demo() -> list[dict]:
    cases = [
        Dispute(ANCHOR_REFUND_DISPUTE, "ORDER-003", "not_received", 9.99,
                delivery_scanned=False),
        Dispute(ANCHOR_ESCALATE_DISPUTE, "ORDER-009", "not_as_described", 645.00),
        Dispute("DISP-003", "ORDER-002", "damaged", 14.50, replaceable=True),
    ]
    return [{"dispute_id": c.dispute_id,
             "action": (d := triage(c)).action,
             "rules": d.cited(),
             "reason": d.reason} for c in cases]


def seller_health() -> list[dict]:
    conn = build_db()
    install_views(conn)
    conn.row_factory = None
    rows = conn.execute(
        "SELECT seller_id, name, tier, rating, defect_rate, open_disputes "
        "FROM v_seller_performance ORDER BY defect_rate DESC").fetchall()
    return [{"seller_id": r[0], "name": r[1], "tier": r[2],
             "rating": r[3], "defect_rate": r[4],
             "open_disputes": r[5]} for r in rows]
