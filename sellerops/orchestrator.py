"""ReAct orchestrator with multi-intent fan-out.

Plans a question into tool calls (text2sql, SOP RAG, quality scorer,
dispute triage, fraud signal), executes them, audits every step, and
assembles a cited answer. High-stakes actions route through the
confirmation gate instead of executing directly.
"""

from __future__ import annotations

import sqlite3

from . import disputes as dispute_mod
from . import quality as quality_mod
from .audit import AuditLog
from .escalation import ConfirmationGate, tier_for
from .fraudsignal import FakeFraudFeed
from .sop_rag import SopIndex, load_chunks
from .sop_rag import answer as rag_answer
from .telemetry import build_db
from .text2sql import EscalationNeeded
from .text2sql import answer as t2s_answer
from .views import install_views


class Orchestrator:
    def __init__(self, conn: sqlite3.Connection | None = None,
                 sop_dir=None):
        self.conn = conn or build_db()
        install_views(self.conn)
        self.audit = AuditLog()
        self.gate = ConfirmationGate()
        self.fraud = FakeFraudFeed()
        self.sop_index = SopIndex(load_chunks(sop_dir)) if sop_dir else None

    def _intents(self, question: str) -> list[str]:
        q = question.lower()
        out = []
        if any(k in q for k in ("dispute", "refund", "backlog", "exposure")):
            out.append("dispute_backlog")
        if any(k in q for k in ("quality", "listing score", "band")):
            out.append("listings_by_quality_band")
        if any(k in q for k in ("seller performance", "tier", "defect")):
            out.append("seller_performance")
        if any(k in q for k in ("violation", "policy", "suspend")):
            out.append("policy_violations")
        if any(k in q for k in ("sop", "policy doc", "how do we", "guideline")):
            out.append("sop_lookup")
        return out or ["dispute_backlog"]

    def ask(self, question: str, session_id: str = "demo") -> dict:
        self.audit.record("user", "question", question[:200])
        results: dict = {"question": question, "steps": []}
        for intent in self._intents(question):
            if intent == "sop_lookup" and self.sop_index is not None:
                r = rag_answer(self.sop_index, question)
                results["steps"].append({"tool": "sop_rag", **r})
            else:
                try:
                    r = t2s_answer(self.conn, intent.replace("_", " "))
                except EscalationNeeded as exc:
                    r = {"intent": intent, "escalated": str(exc)}
                results["steps"].append({"tool": "text2sql", **r})
            self.audit.record("agent", intent, "ok")
        return results

    def triage_dispute(self, dispute: dispute_mod.Dispute) -> dict:
        decision = dispute_mod.triage(dispute)
        tier = tier_for("refund", amount=dispute.amount)
        gated = tier.tier in ("T3", "T4") or decision.action == "escalate"
        key = f"dispute:{dispute.dispute_id}"
        if gated:
            note = self.gate.request(key, f"{decision.action} ${dispute.amount:.2f}")
            self.audit.record("agent", "triage", f"{key} {decision.cited()} gated")
            return {"decision": decision, "tier": tier.tier,
                    "gated": True, "gate_note": note}
        self.audit.record("agent", "triage", f"{key} {decision.cited()}")
        return {"decision": decision, "tier": tier.tier, "gated": False}

    def score_listing(self, listing_id: str, title: str, description: str,
                      has_image: bool, flags: str, price: float) -> dict:
        report = quality_mod.score_listing(listing_id, title, description,
                                           has_image, flags, price)
        self.audit.record("agent", "quality_score",
                          f"{listing_id} {report.band} {report.total}")
        return {"band": report.band, "total": report.total,
                "breakdown": report.breakdown()}
