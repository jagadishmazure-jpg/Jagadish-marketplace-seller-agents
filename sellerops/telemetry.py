"""Synthetic marketplace telemetry on SQLite.

Fictional sellers, listings, orders, disputes, and policy violations.
Deterministic seed (42) so every run produces identical data. All names
are invented; no real merchants or brands appear anywhere.
"""

from __future__ import annotations

import random
import sqlite3
from pathlib import Path

SEED = 42

# Deterministic anchors the tests and demo rely on.
ANCHOR_SUSPENDED_SELLER = "SELLER-SUSP-01"   # bronze tier, defect rate over the suspension line
ANCHOR_LOW_LISTING = "LISTING-LOW-001"       # poor quality signals across the board
ANCHOR_REFUND_DISPUTE = "DISP-REFUND-001"    # item-not-received, no delivery scan -> refund
ANCHOR_ESCALATE_DISPUTE = "DISP-ESC-001"     # high-value dispute -> escalate
ANCHOR_COUNTERFEIT = "VIOLATION-001"         # counterfeit policy violation

_SELLERS = [
    # (seller_id, name, tier, rating, defect_rate)
    ("SELLER-PLAT-01", "CopperCanyon Traders", "platinum", 4.9, 0.004),
    ("SELLER-GOLD-01", "MapleRun Goods", "gold", 4.7, 0.012),
    ("SELLER-GOLD-02", "SilverPeak Outfitters", "gold", 4.6, 0.015),
    ("SELLER-SILV-01", "RedwoodBasin Supply", "silver", 4.3, 0.031),
    ("SELLER-SILV-02", "IronHill Mercantile", "silver", 4.2, 0.038),
    ("SELLER-BRON-01", "DustyTrail Bargains", "bronze", 3.8, 0.062),
    (ANCHOR_SUSPENDED_SELLER, "QuickFlip Liquidators", "bronze", 3.1, 0.118),
]

# (listing_id, seller_id, title, description, has_image, compliance_flags, price)
_LISTINGS = [
    ("LISTING-TOP-001", "SELLER-PLAT-01",
     "Hand-forged copper camping mug, 12 oz",
     "Solid copper mug with rolled rim. Dishwasher safe. Ships in 2 days.",
     1, "", 34.99),
    ("LISTING-TOP-002", "SELLER-GOLD-01",
     "Maple cutting board, end grain, 18x12",
     "End-grain hard maple board, food-safe oil finish. Includes care card.",
     1, "", 59.00),
    ("LISTING-MID-001", "SELLER-SILV-01",
     "Trail socks wool blend",
     "Wool blend hiking socks. Size L.",
     1, "", 14.50),
    ("LISTING-MID-002", "SELLER-SILV-02",
     "Cast iron skillet 10 inch",
     "Pre-seasoned cast iron skillet.",
     0, "", 42.00),
    (ANCHOR_LOW_LISTING, ANCHOR_SUSPENDED_SELLER,
     "CHEAP!!! mug mug mug best deal buy now",
     "mug",
     0, "keyword_stuffing,prohibited_claim", 9.99),
    ("LISTING-LOW-002", "SELLER-BRON-01",
     "phone case",
     "case for phone. good.",
     0, "", 7.49),
    ("LISTING-GOLD-03", "SELLER-GOLD-02",
     "Insulated trail jacket, waterproof",
     "Waterproof breathable trail jacket with taped seams. Machine washable.",
     1, "", 129.00),
    ("LISTING-SILV-03", "SELLER-SILV-01",
     "Enamel camp plate set of 4",
     "Set of four enamel camp plates, assorted colors.",
     1, "", 28.00),
]

# (order_id, listing_id, seller_id, amount, status)
_ORDERS = [
    ("ORDER-001", "LISTING-TOP-001", "SELLER-PLAT-01", 34.99, "delivered"),
    ("ORDER-002", "LISTING-MID-001", "SELLER-SILV-01", 14.50, "delivered"),
    ("ORDER-003", ANCHOR_LOW_LISTING, ANCHOR_SUSPENDED_SELLER, 9.99, "shipped"),
    ("ORDER-004", "LISTING-GOLD-03", "SELLER-GOLD-02", 129.00, "delivered"),
    ("ORDER-005", "LISTING-TOP-002", "SELLER-GOLD-01", 59.00, "delivered"),
    ("ORDER-006", "LISTING-MID-002", "SELLER-SILV-02", 42.00, "shipped"),
    ("ORDER-007", "LISTING-SILV-03", "SELLER-SILV-01", 28.00, "delivered"),
    ("ORDER-008", "LISTING-LOW-002", "SELLER-BRON-01", 7.49, "delivered"),
    ("ORDER-009", "LISTING-GOLD-03", "SELLER-GOLD-02", 645.00, "delivered"),
]

# (dispute_id, order_id, reason_code, status, amount)
_DISPUTES = [
    (ANCHOR_REFUND_DISPUTE, "ORDER-003", "not_received", "open", 9.99),
    (ANCHOR_ESCALATE_DISPUTE, "ORDER-009", "not_as_described", "open", 645.00),
    ("DISP-003", "ORDER-002", "damaged", "open", 14.50),
    ("DISP-004", "ORDER-008", "not_received", "resolved_refund", 7.49),
    ("DISP-005", "ORDER-006", "damaged", "open", 42.00),
]

# (violation_id, seller_id, policy_code, severity)
_VIOLATIONS = [
    (ANCHOR_COUNTERFEIT, ANCHOR_SUSPENDED_SELLER, "counterfeit", "critical"),
    ("VIOLATION-002", "SELLER-BRON-01", "late_shipment", "minor"),
    ("VIOLATION-003", ANCHOR_SUSPENDED_SELLER, "keyword_stuffing", "major"),
]

SCHEMA = """
CREATE TABLE sellers (
    seller_id TEXT PRIMARY KEY, name TEXT, tier TEXT, rating REAL, defect_rate REAL
);
CREATE TABLE listings (
    listing_id TEXT PRIMARY KEY, seller_id TEXT, title TEXT, description TEXT,
    has_image INTEGER, compliance_flags TEXT, price REAL
);
CREATE TABLE orders (
    order_id TEXT PRIMARY KEY, listing_id TEXT, seller_id TEXT,
    amount REAL, status TEXT
);
CREATE TABLE disputes (
    dispute_id TEXT PRIMARY KEY, order_id TEXT, reason_code TEXT,
    status TEXT, amount REAL
);
CREATE TABLE violations (
    violation_id TEXT PRIMARY KEY, seller_id TEXT, policy_code TEXT, severity TEXT
);
"""


def build_db(path: str | Path | None = None) -> sqlite3.Connection:
    """Create (or open) the telemetry DB and seed it deterministically."""
    rng = random.Random(SEED)
    conn = sqlite3.connect(":memory:" if path is None else str(path))
    conn.executescript(SCHEMA)
    conn.executemany("INSERT INTO sellers VALUES (?,?,?,?,?)", _SELLERS)
    conn.executemany("INSERT INTO listings VALUES (?,?,?,?,?,?,?)", _LISTINGS)
    conn.executemany("INSERT INTO orders VALUES (?,?,?,?,?)", _ORDERS)
    conn.executemany("INSERT INTO disputes VALUES (?,?,?,?,?)", _DISPUTES)
    conn.executemany("INSERT INTO violations VALUES (?,?,?,?)", _VIOLATIONS)
    # A few extra deterministic listings so aggregates are non-trivial.
    extra = []
    for i in range(1, 13):
        seller = _SELLERS[i % len(_SELLERS)][0]
        extra.append((
            f"LISTING-EXTRA-{i:02d}", seller,
            f"Outdoor accessory item {i}",
            f"Quality outdoor accessory number {i}. Ships in 3 days.",
            i % 3 != 0, "", round(10.0 + rng.random() * 90.0, 2),
        ))
    conn.executemany("INSERT INTO listings VALUES (?,?,?,?,?,?,?)", extra)
    conn.commit()
    return conn


def table_counts(conn: sqlite3.Connection) -> dict[str, int]:
    return {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("sellers", "listings", "orders", "disputes", "violations")
    }
