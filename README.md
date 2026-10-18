# Marketplace seller operations agents

**Recruiter summary.** Buyer trust is a marketplace's scarcest asset, and it
decays through two quiet channels: listing rot (technically compliant but
low-quality listings) and inconsistent dispute handling. This repo is an
end-to-end agentic system for marketplace seller operations on synthetic
data: a listing-quality scorer that turns decay into coachable per-signal
feedback, an ordered and cited dispute-triage engine, text-to-SQL over
read-only views, SOP-grounded RAG, a fraud-risk feed with honest gap
behavior, and human confirmation gates on suspensions and high-value
refunds. Proof: **74 tests green**, deterministic, stdlib-only.

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
2. `views.py` publishes 5 read-only views behind a SELECT-only gateway
   (rules SEC-SELECT-01/02/03, cited in errors and the audit trail); a SQLite
   authorizer makes the views the only readable objects (ADR 0001).
3. `text2sql.py` routes 5 intents to fixed SQL templates, all through the
   gateway; a failing query retries once as `SELECT * FROM <view> LIMIT 20`
   before escalating.
4. `quality.py` scores every listing 0–100 across 5 signals with a
   per-signal breakdown (SOP-01: prohibited phrases zero compliance, ALL CAPS
   and keyword stuffing cost title points); `disputes.py` triages disputes through ordered,
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
python -m pytest tests/ -q        # 74 tests, stdlib only
python scripts/count_tests.py     # prints the real count
pip install streamlit             # optional, demo only
streamlit run demo/app.py
```
Fully offline. The live fraud feed is a stub: without `api_key` +
`endpoint` it returns an explicit gap result.

## Guardrails and security controls
- SELECT-only SQL gateway (no stacked statements, no DDL/DML, view
  allowlist enforced by a SQLite authorizer, 100-row cap at fetch time).
- Suspensions and >$500 refunds require explicit confirmation.
- Dispute decisions cite ordered policy rules; first terminal match wins.
- PII (email/phone incl. `(555) 123-4567`/SSN/card) scrubbed from feedback before storage;
  audit entries never echo row data.
- Threat model: [docs/threat-model.md](docs/threat-model.md).

## How this differs from coldchain/retail
Cold-chain is telemetry-and-compliance over physical goods in motion;
retail-ops is storefront operations. This repo is **platform governance**:
scoring third-party sellers, triaging buyer–seller disputes, and
enforcing policy — the trust layer, not the logistics layer. The two
differentiators here (listing-quality scorer, cited dispute-triage
engine) exist in neither sibling repo.

**Boundary with retail-ops and fraud-detection.** retail-ops flags a
*customer* abusing returns at the retailer's own stores; this repo triages
disputes *between* a buyer and a third-party seller and scores the
seller's listings. fraud-detection scores card transactions at a bank;
here the fraud feed is one input (chargeback risk) into seller
governance, not a detector.

## Limitations and known failures
- The quality weights are heuristic, not fitted to conversion data.
- TF-IDF retrieval is keyword-based; paraphrased policy questions may
  miss (kept visible as the explicit not-found path, tested).
- The fraud feed's live backend is a stub; the demo runs on seeded scores.
- Dispute-triage inputs (delivery scan, replacement stock, counterfeit
  allegation) are not in the synthetic `disputes` table; the demo builds
  those three cases by hand.
- A listing with no image can still reach "excellent" (85) if every other
  signal is perfect.

## Standardization review (2026-10-18)

Reviewed against the portfolio standard after the build. Bugs found and fixed, each now pinned by a test:

1. **Gateway had no view allowlist.** It blocked writes, but `SELECT * FROM sellers`, a comma join, `"sqlite_master"` and `FROM/**/sellers` all read base tables or the schema, and any caller-written LIMIT skipped the 100-row cap (8,000 rows from a view self-join). The only allowlist check was a regex over names starting with `v_`. A SQLite authorizer (`sellerops/authz.py`, ADR 0001) now refuses any read that is not a published view (`SEC-SELECT-03`); rows past 100 are never fetched.
2. **One intent bypassed the gateway entirely.** `policy_violations` read the `violations` base table with `conn.execute`, a documented carve-out that contradicted "read-only views only". It now reads a new `v_policy_violations` view through the gateway.
3. **The documented retry did not exist.** The module said "one simplified retry on gateway or DB errors", but a failing template escalated immediately. A failing query now retries once as `SELECT * FROM <view> LIMIT 20` before escalating (tested).
4. **Prohibited phrases scored excellent.** `PROHIBITED_PHRASES` was defined but never checked, so "Cheapest enamel plates - best deal, buy now" scored 100/excellent; SOP-01 says such claims are "scored zero on compliance". They now zero compliance (80, good). ALL CAPS titles, also named in SOP-01, now lose title points.
5. **Function words counted as keyword stuffing.** "...set for camping and picnic, four for families" lost 20 title points for repeating "for". Stopwords and punctuation are ignored; "mug mug mug coffee mug" is still caught.
6. **Phone scrubber swallowed spaces and matched inside IDs.** The unanchored pattern turned `call (555) 123-4567` into `call[phone]` and `ORD-20261018-0001` into `ORD-20[phone]`. It now uses the shared anchored phone pattern.

Differentiator on the seeded data (regenerated and checked by CI on every push):

<!-- run: python scripts/show_differentiator.py -->
```text
Listing-quality scorer: 20 listings; bands {'excellent': 17, 'good': 1, 'needs-work': 1, 'poor': 1}
  LISTING-LOW-001: 17.0 poor {'title': 0.0, 'description': 2.0, 'image': 0.0, 'compliance': 0.0, 'pricing': 15.0}
  LISTING-LOW-002: 57.0 needs-work {'title': 10.0, 'description': 12.0, 'image': 0.0, 'compliance': 20.0, 'pricing': 15.0}
  LISTING-MID-002: 72.0 good {'title': 25.0, 'description': 12.0, 'image': 0.0, 'compliance': 20.0, 'pricing': 15.0}
  unflagged pressure phrases: 80.0 good; compliance flags: prohibited phrase 'best deal', prohibited phrase 'buy now', prohibited phrase 'cheapest'
Dispute triage (first terminal rule wins):
  DISP-REFUND-001: refund [DSP-REFUND-01] no delivery scan on record
  DISP-ESC-001: escalate [DSP-ESC-03] amount $645.00 exceeds $500.00 auto-action limit
  DISP-003: replace [DSP-REPLACE-02] item damaged and replacement stock available
Gateway: [SEC-SELECT-03] 'sellers' is not one of the published views
```
<!-- /run -->

Test count (also checked by CI):

<!-- run: python scripts/count_tests.py -->
```text
74 tests collected
```
<!-- /run -->

## Built vs planned

| Item | Status |
|---|---|
| Synthetic telemetry + 5 views + gateway | Built |
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
| CI on every push: ruff, tests, docs drift check, hashed brand check, gitleaks; CodeQL; Dependabot | Built |

## Docs
- [docs/implementation-guide.md](docs/implementation-guide.md) — adopting this in production
- [docs/interview-points.md](docs/interview-points.md) — talking points
- [docs/threat-model.md](docs/threat-model.md) — STRIDE-lite + LLM notes
- [knowledge/](knowledge/) — domain notes + architecture diagram
- [docs/adr/0001-sqlite-authorizer-backstop.md](docs/adr/0001-sqlite-authorizer-backstop.md) — gateway backstop

## Related repos
- [Jagadish-retail-ops-agents](https://github.com/jagadishmazure-jpg/Jagadish-retail-ops-agents) — retailer's own stores, customer returns abuse
- [Jagadish-fraud-detection-agents](https://github.com/jagadishmazure-jpg/Jagadish-fraud-detection-agents) — card-transaction fraud at a bank
- [Jagadish-coldchain-logistics-agents](https://github.com/jagadishmazure-jpg/Jagadish-coldchain-logistics-agents) — same spine, logistics

---
*Synthetic data only — all sellers, listings, and disputes are invented.
Independent demo project, not affiliated with any marketplace or employer.*
