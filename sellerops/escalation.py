"""Escalation tiers T1-T4 + confirmation gates.

T1 routine -> T2 watch -> T3 urgent -> T4 critical. Seller suspensions and
high-value refunds require explicit confirmation before execution.
"""

from __future__ import annotations

from dataclasses import dataclass

SUSPEND_DEFECT_RATE = 0.10
HIGH_REFUND_THRESHOLD = 500.0


class ConfirmationGate:
    """Human approval gate. decide() records an explicit grant/deny."""

    def __init__(self) -> None:
        self.decisions: dict[str, bool] = {}

    def request(self, key: str, summary: str) -> str:
        self.decisions.setdefault(key, False)
        return f"confirmation required [{key}]: {summary}"

    def decide(self, key: str, approved: bool) -> bool:
        self.decisions[key] = bool(approved)
        return self.decisions[key]

    def granted(self, key: str) -> bool:
        return self.decisions.get(key, False)


@dataclass
class Tiered:
    tier: str   # T1..T4
    reason: str


def tier_for(event: str, **kw) -> Tiered:
    if event == "seller_suspension":
        rate = kw.get("defect_rate", 0.0)
        return Tiered("T4" if rate >= SUSPEND_DEFECT_RATE else "T3",
                      f"defect_rate={rate:.3f}")
    if event == "refund":
        amount = kw.get("amount", 0.0)
        return Tiered("T3" if amount > HIGH_REFUND_THRESHOLD else "T2",
                      f"amount=${amount:.2f}")
    if event == "dispute_backlog":
        n = kw.get("open_count", 0)
        return Tiered("T3" if n >= 5 else "T2", f"open_count={n}")
    if event == "policy_violation":
        sev = kw.get("severity", "minor")
        return Tiered("T4" if sev == "critical" else "T3", f"severity={sev}")
    return Tiered("T1", "routine")
