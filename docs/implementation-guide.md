# Implementation guide

For teams adopting this pattern in a real marketplace.

## 1. Replace the telemetry layer
Swap `telemetry.py`'s seeded SQLite for your warehouse (Snowflake,
BigQuery, Postgres). Keep the four read-only views as the agent's only
interface — the gateway rules (SEC-SELECT-01/02/03) transfer unchanged.

## 2. Calibrate the quality scorer
The five signals and their weights are a starting point. Fit weights
against your historical listing-conversion data; keep the per-signal
breakdown so sellers see what to fix.

## 3. Encode your real policy
`disputes.py`'s ordered rules mirror SOP-02. Encode your actual dispute
policy the same way: ordered, cited, terminal-first-match. Every
production decision should cite rule IDs.

## 4. Wire the fraud feed
`fraudsignal.py`'s live stub defines the interface. Plug in your
chargeback-risk provider; the gap behavior (explicit "unavailable",
never hallucinated) stays.

## 5. Human gates
Suspensions and >$500 refunds stay behind `ConfirmationGate`. In
production this is a Slack/Teams approval or a case-queue task, not a
boolean in code.

## 6. Close the loop
`feedback.py` captures corrections with PII scrubbed at capture time.
Feed corrections into eval sets (see the agent-feedback-loop pattern)
so triage rules improve with real buyer language.
