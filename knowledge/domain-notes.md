# Domain notes — marketplace seller operations

Marketplace ops is a two-sided trust problem: buyers need to trust
listings, sellers need predictable enforcement. The failure modes that
motivate this repo:

- **Listing rot**: low-quality listings (keyword stuffing, no images,
  vague descriptions) erode buyer trust long before any single policy
  violation fires. A continuous quality score catches decay early.
- **Dispute inconsistency**: two agents resolving the same dispute type
  differently creates appeals and chargebacks. An ordered, cited rule set
  makes triage reproducible.
- **Suspension surprises**: sellers suspended without a visible trail
  appeal and win. The confirmation gate + hash-chained audit makes every
  high-stakes action defensible.
- **Feedback decay**: without a loop from resolutions back into evals,
  the triage rules drift from real buyer language. The feedback module
  captures corrections with PII scrubbed at capture time.

## Why this differs from coldchain / retail
Cold-chain is telemetry-and-compliance over physical goods in motion
(temperature, spoilage, reefer telemetry). Retail-ops is storefront
operations (shelves, staffing, promotions). This repo is **platform
governance**: scoring third-party sellers, triaging buyer-seller
disputes, and enforcing policy — the trust layer, not the logistics
layer.
