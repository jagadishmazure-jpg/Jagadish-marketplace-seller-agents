"""Tests for the marketplace seller-ops scaffold. All deterministic."""
from pathlib import Path

import pytest

from sellerops import disputes as dm
from sellerops import quality as qm
from sellerops.audit import AuditLog
from sellerops.escalation import ConfirmationGate, tier_for
from sellerops.feedback import FeedbackError, FeedbackStore, scrub_pii
from sellerops.fraudsignal import FakeFraudFeed, LiveFraudFeed
from sellerops.orchestrator import Orchestrator
from sellerops.sop_rag import SopIndex, load_chunks
from sellerops.sop_rag import answer as rag_answer
from sellerops.telemetry import (
    ANCHOR_ESCALATE_DISPUTE,
    ANCHOR_REFUND_DISPUTE,
    ANCHOR_SUSPENDED_SELLER,
    build_db,
    table_counts,
)
from sellerops.text2sql import _TEMPLATES as T2S_TEMPLATES
from sellerops.text2sql import EscalationNeeded
from sellerops.text2sql import answer as t2s_answer
from sellerops.views import GatewayError, install_views, run_query

ROOT = Path(__file__).resolve().parent.parent
SOP_DIR = ROOT / "docs" / "sops"


def conn():
    c = build_db()
    install_views(c)
    return c


# ---------- telemetry ----------

def test_table_counts():
    counts = table_counts(build_db())
    assert counts["sellers"] == 7
    assert counts["disputes"] == 5
    assert counts["violations"] == 3
    assert counts["listings"] == 8 + 12


def test_suspension_anchor():
    c = build_db()
    row = c.execute("SELECT defect_rate, tier FROM sellers WHERE seller_id=?",
                    (ANCHOR_SUSPENDED_SELLER,)).fetchone()
    assert row[0] > 0.10 and row[1] == "bronze"


def test_seed_deterministic():
    a = table_counts(build_db())
    b = table_counts(build_db())
    assert a == b


# ---------- quality scorer ----------

def test_quality_excellent():
    r = qm.score_listing("X", "Hand-forged copper camping mug, 12 oz",
                         "Solid copper mug with rolled rim. Ships in 2 days.",
                         True, "", 34.99)
    assert r.band == "excellent" and r.total == 100.0


def test_quality_poor_anchor():
    r = qm.score_listing("LISTING-LOW-001", "CHEAP!!! mug mug mug best deal buy now",
                         "mug", False, "keyword_stuffing,prohibited_claim", 9.99)
    assert r.band == "poor"
    assert r.breakdown()["title"] == 0.0
    assert r.breakdown()["compliance"] == 0.0


def test_quality_bands_cover_spectrum():
    good = qm.score_listing("G", "Maple cutting board, end grain, 18x12",
                            "End-grain hard maple board, food-safe oil finish. "
                            "Includes care card.", True, "", 59.00)
    assert good.band in ("excellent", "good")
    mid = qm.score_listing("M", "phone case",
                           "case for phone. good.", False, "", 7.49)
    assert mid.band == "needs-work"


def test_quality_breakdown_sums():
    r = qm.score_listing("X", "A decent title with enough characters here",
                         "A reasonably complete description of the item.", False, "", 10.0)
    assert abs(sum(r.breakdown().values()) - r.total) < 0.01


def test_quality_invalid_price():
    r = qm.score_listing("X", "A decent title with enough characters here",
                         "A reasonably complete description of the item.", True, "", 0)
    assert r.breakdown()["pricing"] == 0.0


# ---------- dispute triage ----------

def test_triage_refund():
    d = dm.triage(dm.Dispute(ANCHOR_REFUND_DISPUTE, "ORDER-003",
                             "not_received", 9.99, delivery_scanned=False))
    assert d.action == "refund" and d.rules_fired == ["DSP-REFUND-01"]


def test_triage_replace():
    d = dm.triage(dm.Dispute("DISP-003", "ORDER-002", "damaged", 14.50,
                             replaceable=True))
    assert d.action == "replace" and "DSP-REPLACE-02" in d.rules_fired


def test_triage_high_value_escalates():
    d = dm.triage(dm.Dispute(ANCHOR_ESCALATE_DISPUTE, "ORDER-009",
                             "not_as_described", 645.00))
    assert d.action == "escalate" and d.rules_fired == ["DSP-ESC-03"]


def test_triage_counterfeit_outranks_value():
    d = dm.triage(dm.Dispute("X", "ORDER-009", "not_as_described", 9999.00,
                             counterfeit_alleged=True))
    assert d.action == "escalate" and d.rules_fired == ["DSP-POLICY-04"]


def test_triage_default_escalates_with_reason():
    d = dm.triage(dm.Dispute("X", "O", "weird_reason", 5.00))
    assert d.action == "escalate" and d.rules_fired == ["DSP-ESC-00"]
    assert d.reason


def test_triage_citation_string():
    d = dm.triage(dm.Dispute("X", "O", "not_received", 5.00, delivery_scanned=False))
    assert d.cited() == "DSP-REFUND-01"


# ---------- gateway ----------

def test_gateway_select_ok():
    rows = run_query(conn(), "SELECT seller_id FROM v_seller_performance")
    assert len(rows) == 7


def test_gateway_rejects_write():
    with pytest.raises(GatewayError) as e:
        run_query(conn(), "DELETE FROM sellers")
    assert e.value.rule_id == "SEC-SELECT-01"


def test_gateway_rejects_stacked():
    with pytest.raises(GatewayError) as e:
        run_query(conn(), "SELECT 1; DROP TABLE sellers")
    assert e.value.rule_id == "SEC-SELECT-02"


def test_gateway_write_keyword_outside_literal_rejected():
    with pytest.raises(GatewayError):
        run_query(conn(), "SELECT * FROM v_listing_quality WHERE 1=1 UPDATE x")


def test_gateway_write_keyword_inside_literal_ok():
    rows = run_query(conn(), "SELECT 'update later' AS note FROM v_listing_quality")
    assert rows and rows[0]["note"] == "update later"


def test_gateway_unknown_view():
    with pytest.raises(GatewayError) as e:
        run_query(conn(), "SELECT * FROM v_nope")
    assert e.value.rule_id == "SEC-SELECT-03"


def test_gateway_adds_limit():
    rows = run_query(conn(), "SELECT * FROM v_listing_quality", limit=3)
    assert len(rows) == 3


# ---------- text2sql ----------

@pytest.mark.parametrize("q,intent", [
    ("show listings by quality band", "listings_by_quality_band"),
    ("what is the dispute backlog", "dispute_backlog"),
    ("seller performance by defect rate", "seller_performance"),
    ("list policy violations", "policy_violations"),
    ("what is our refund exposure", "refund_exposure"),
])
def test_intents(q, intent):
    r = t2s_answer(conn(), q)
    assert r["intent"] == intent and r["row_count"] >= 0


def test_unknown_question_escalates():
    with pytest.raises(EscalationNeeded):
        t2s_answer(conn(), "flibberty gibbet wozzle")


def test_dispute_backlog_sorted():
    r = t2s_answer(conn(), "dispute backlog")
    amounts = [x["amount"] for x in r["rows"]]
    assert amounts == sorted(amounts, reverse=True)


# ---------- fraud signal ----------

def test_fake_feed_deterministic():
    a = FakeFraudFeed().score("SELLER-GOLD-01").risk_score
    b = FakeFraudFeed().score("SELLER-GOLD-01").risk_score
    assert a == b and 0 <= a <= 1


def test_fake_feed_anchor_high():
    s = FakeFraudFeed().score(ANCHOR_SUSPENDED_SELLER)
    assert s.risk_score >= 0.91 and s.backend == "fake"


def test_live_feed_gap():
    s = LiveFraudFeed().score("ORDER-001")
    assert s.backend == "gap" and s.risk_score == -1.0
    assert "not configured" in s.detail


# ---------- RAG ----------

def test_rag_finds_dispute_sop():
    idx = SopIndex(load_chunks(SOP_DIR))
    r = rag_answer(idx, "how are disputes triaged")
    assert r["found"] and any("sop-02" in c for c in r["citations"])


def test_rag_not_found_explicit():
    idx = SopIndex(load_chunks(SOP_DIR))
    r = rag_answer(idx, "xylophone zebra quasar")
    assert not r["found"] and r["citations"] == []


def test_chunks_have_no_title_only_intro():
    chunks = load_chunks(SOP_DIR)
    assert chunks and all(c.section != "intro" for c in chunks)


# ---------- escalation ----------

def test_tier_suspension_t4():
    assert tier_for("seller_suspension", defect_rate=0.12).tier == "T4"


def test_tier_refund_threshold():
    assert tier_for("refund", amount=600).tier == "T3"
    assert tier_for("refund", amount=50).tier == "T2"


def test_gate_flow():
    g = ConfirmationGate()
    g.request("suspend:S1", "defect 0.12")
    assert not g.granted("suspend:S1")
    g.decide("suspend:S1", True)
    assert g.granted("suspend:S1")


# ---------- audit ----------

def test_audit_chain_verifies():
    log = AuditLog()
    log.record("agent", "triage", "ok")
    log.record("user", "feedback", "up")
    assert log.verify_chain()


def test_audit_tamper_detected():
    log = AuditLog()
    log.record("agent", "triage", "ok")
    log.entries[0].details = "forged"
    assert not log.verify_chain()


# ---------- feedback + PII ----------

def test_scrub_email_phone_ssn():
    out, n = scrub_pii("mail me at jane@example.com or 555-123-4567, ssn 123-45-6789")
    assert "[email]" in out and "[phone]" in out and "[ssn]" in out
    assert "jane@example.com" not in out and n == 3


def test_feedback_capture_scrubs():
    store = FeedbackStore(AuditLog())
    fb = store.capture("S1", "T1", "down", "wrong refund, contact bob@example.com")
    assert fb.redactions == 1 and "bob@example.com" not in fb.correction


def test_feedback_thumbs_down_needs_text():
    with pytest.raises(FeedbackError):
        FeedbackStore(AuditLog()).capture("S1", "T1", "down", "   ")


def test_feedback_bad_rating():
    with pytest.raises(FeedbackError):
        FeedbackStore(AuditLog()).capture("S1", "T1", "meh")


def test_feedback_up_ok_and_audited():
    audit = AuditLog()
    store = FeedbackStore(audit)
    fb = store.capture("S1", "T1", "up")
    assert fb.rating == "up" and audit.verify_chain()


# ---------- orchestrator ----------

def test_orchestrator_fans_out():
    orch = Orchestrator(sop_dir=SOP_DIR)
    r = orch.ask("show dispute backlog and seller performance")
    intents = [s.get("intent") for s in r["steps"]]
    assert intents[:2] == ["dispute_backlog", "seller_performance"] and audit_ok(orch)


def audit_ok(orch: Orchestrator) -> bool:
    return orch.audit.verify_chain()


def test_orchestrator_triage_gates_high_value():
    orch = Orchestrator(sop_dir=SOP_DIR)
    r = orch.triage_dispute(dm.Dispute(ANCHOR_ESCALATE_DISPUTE, "ORDER-009",
                                       "not_as_described", 645.00))
    assert r["gated"] and r["tier"] == "T3"


def test_orchestrator_score_listing():
    orch = Orchestrator(sop_dir=SOP_DIR)
    r = orch.score_listing("L", "Hand-forged copper camping mug, 12 oz",
                           "Solid copper mug. Ships in 2 days.", True, "", 34.99)
    assert r["band"] == "excellent"


def test_orchestrator_sop_lookup():
    orch = Orchestrator(sop_dir=SOP_DIR)
    r = orch.ask("what is the sop for dispute handling")
    assert any(s["tool"] == "sop_rag" and s.get("found") for s in r["steps"])


# ---------- demo helpers ----------

def test_demo_quality_summary():
    from sellerops.demo_helpers import quality_summary
    rows = quality_summary()
    bands = {r["listing_id"]: r["band"] for r in rows}
    assert bands["LISTING-LOW-001"] == "poor"
    assert bands["LISTING-TOP-001"] == "excellent"


def test_demo_triage_actions():
    from sellerops.demo_helpers import dispute_triage_demo
    acts = {r["dispute_id"]: r["action"] for r in dispute_triage_demo()}
    assert acts[ANCHOR_REFUND_DISPUTE] == "refund"
    assert acts[ANCHOR_ESCALATE_DISPUTE] == "escalate"
    assert acts["DISP-003"] == "replace"


def test_demo_seller_health_sorted():
    from sellerops.demo_helpers import seller_health
    rows = seller_health()
    rates = [r["defect_rate"] for r in rows]
    assert rates == sorted(rates, reverse=True)
    assert rows[0]["seller_id"] == ANCHOR_SUSPENDED_SELLER


# ---------- review fixes (grokbot-portfolio, 2026-10-18) ----------

def test_review_policy_violations_go_through_the_gateway():
    c = conn()
    out = t2s_answer(c, "list policy violations")
    assert "FROM v_policy_violations" in out["sql"] and out["row_count"] == 3


def test_review_simplified_retry_on_gateway_error(monkeypatch):
    monkeypatch.setitem(T2S_TEMPLATES, "dispute_backlog",
                        "SELECT nope FROM v_dispute_backlog")  # invalid column
    out = t2s_answer(conn(), "show the dispute backlog")
    assert out["sql"] == "SELECT * FROM v_dispute_backlog LIMIT 20" and out["row_count"] > 0


GOOD_DESC = "Set of four enamel camp plates, assorted colors, dishwasher safe."


def test_review_prohibited_phrases_zero_compliance():
    r = qm.score_listing("L", "Cheapest enamel plates - best deal, buy now", GOOD_DESC, True, "", 24.0)
    assert r.breakdown()["compliance"] == 0.0 and "best deal" in r.signals[3].detail


def test_review_function_words_are_not_keyword_stuffing():
    r = qm.score_listing("L", "Enamel camp plate set for camping and picnic, four for families",
                         GOOD_DESC, True, "", 24.0)
    assert r.breakdown()["title"] == 25.0


def test_review_real_stuffing_still_caught():
    r = qm.score_listing("L", "mug mug mug coffee mug ceramic", GOOD_DESC, True, "", 9.0)
    assert r.signals[0].detail.startswith("keyword stuffing")


def test_review_all_caps_title_penalised():
    r = qm.score_listing("L", "ENAMEL CAMP PLATES SET OF FOUR", GOOD_DESC, True, "", 24.0)
    assert r.signals[0].detail == "all caps (SOP-01)" and r.breakdown()["title"] == 10.0


@pytest.mark.parametrize("text, expected", [
    ("call (555) 123-4567 now", "call [phone] now"),     # used to swallow the space
    ("call +1 (555) 123-4567 now", "call [phone] now"),
    ("order ORD-20261018-0001", "order ORD-20261018-0001"),   # used to become ORD-20[phone]
    ("ref 1234567890123", "ref 1234567890123"),
])
def test_review_phone_pattern_is_anchored(text, expected):
    assert scrub_pii(text)[0] == expected
