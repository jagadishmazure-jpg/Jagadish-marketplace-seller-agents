# Marketplace seller operations agents

**Recruiter summary.** Buyer trust is a marketplace's scarcest asset, and it
decays through two quiet channels: listing rot (technically compliant but
low-quality listings) and inconsistent dispute handling. This repo is an
end-to-end agentic system for marketplace seller operations on synthetic
data: a listing-quality scorer that turns decay into coachable per-signal
feedback, an ordered and cited dispute-triage engine, text-to-SQL over
read-only views, SOP-grounded RAG, a fraud-risk feed with honest gap
behavior, and human confirmation gates on suspensions and high-value
refunds. Proof: **51 tests green**, deterministic, stdlib-only.

## Purpose
Built for marketplace trust-and-safety and seller-ops teams evaluating how
agentic patterns (tool calling, RAG, guardrails, audit) apply to platform
governance. Also a portfolio showcase of the FDE end-to-end spine:
problem → synthetic data → design → build → guardrails.

## Architecture
See [knowledge/architecture.md](knowledge/architecture.md) (Mermaid) and
[knowledge/domain-notes.md](knowledge/domain-notes.md) for the domain
write-up.

## How it works, step by step
1. `telemetry.py` seeds a SQLite marketplace: 7 sellers, 20 listings,
   9 orders, 5 disputes, 3 violations (seed 42, fully deterministic).
2. `views.py` publishes 4 read-only views behind a SELECT-only gateway
   (rules SEC-SELECT-01/02/03, cited in errors and the audit trail).
3. `text2sql.py` routes 5 intents to fixed SQL templates, with one
   simplified retry before escalating.
4. `quality.py` scores every listing 0–100 across 5 signals with a
   per-signal breakdown; `disputes.py` triages disputes through ordered,
   cited policy rules.
5. `sop_rag.py` answers policy questions from the 4 SOP docs with
   `file §section` citations, or explicit not-found.
6. `fraudsignal.py` adds chargeback risk: seeded fake backend, or an
   explicit gap when the live feed isn't configured — never hallucinated.
7. `orchestrator.py` fans a question out across tools; `escalation.py`
   gates suspensions and >$500 refunds on human confirmation;
   `audit.py` hash-chains every step; `feedback.py` captures corrections
   with PII scrubbed before storage.

## Real code excerpts and their real output

```python
from sellerops.quality import score_listing
r = score_listing("LISTING-LOW-001", "CHEAP!!! mug mug mug best deal buy now",
                  "mug", False, "keyword_stuffing,prohibited_claim", 9.99)
print(r.band, r.total, r.breakdown())
# poor 17.0 {'title': 0.0, 'description': 2.0, 'image': 0.0,
#            'compliance': 0.0, 'pricing': 15.0}
```

```python
from sellerops.disputes import Dispute, triage
d = triage(Dispute("DISP-ESC-001", "ORDER-009", "not_as_described", 645.00))
print(d.action, d.cited())
# escalate DSP-ESC-03
```

## How to run
```bash
python -m pytest tests/ -q        # 51 tests, stdlib only
python scripts/count_tests.py     # prints the real count
pip install streamlit             # optional, demo only
streamlit run demo/app.py
```
Fully offline. The live fraud feed is a stub: without `api_key` +
`endpoint` it returns an explicit gap result.

## Guardrails and security controls
- SELECT-only SQL gateway (no stacked statements, no DDL/DML, view
  allowlist, 100-row cap).
- Suspensions and >$500 refunds require explicit confirmation.
- Dispute decisions cite ordered policy rules; first terminal match wins.
- PII (email/phone/SSN/card) scrubbed from feedback before storage;
  audit entries never echo row data.
- Threat model: [docs/threat-model.md](docs/threat-model.md).

## How this differs from coldchain/retail
Cold-chain is telemetry-and-compliance over physical goods in motion;
retail-ops is storefront operations. This repo is **platform governance**:
scoring third-party sellers, triaging buyer–seller disputes, and
enforcing policy — the trust layer, not the logistics layer. The two
differentiators here (listing-quality scorer, cited dispute-triage
engine) exist in neither sibling repo.

## Limitations and known failures
- The quality weights are heuristic, not fitted to conversion data.
- TF-IDF retrieval is keyword-based; paraphrased policy questions may
  miss (kept visible as the explicit not-found path, tested).
- The fraud feed's live backend is a stub; the demo runs on seeded scores.

## Built vs planned

| Item | Status |
|---|---|
| Synthetic telemetry + 4 views + gateway | Built |
| 5 text-to-SQL intents + retry | Built |
| Listing-quality scorer | Built |
| Dispute-triage engine | Built |
| SOP RAG with citations | Built |
| Fraud feed (fake + gap) | Built |
| Escalation tiers + confirmation gates | Built |
| Hash-chained audit | Built |
| PII-scrubbed feedback | Built |
| Streamlit demo | Built |
| Live fraud provider wiring | Planned |
| CI (added by standardizer) | Planned |

## Docs
- [docs/implementation-guide.md](docs/implementation-guide.md) — adopting this in production
- [docs/interview-points.md](docs/interview-points.md) — talking points
- [docs/threat-model.md](docs/threat-model.md) — STRIDE-lite + LLM notes
- [knowledge/](knowledge/) — domain notes + architecture diagram

---
*Synthetic data only — all sellers, listings, and disputes are invented.
Independent demo project, not affiliated with any marketplace or employer.*
