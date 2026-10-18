# Threat model (STRIDE-lite)

| Threat | Example | Mitigation in this repo |
|---|---|---|
| Spoofing | Fake buyer feedback poisoning triage | Feedback requires session/turn linkage; thumbs-down requires text |
| Tampering | Editing the audit trail to hide a bad suspension | Hash-chained audit; `verify_chain()` detects edits |
| Repudiation | "I never approved that refund" | Confirmation gate records approver + timestamp in the chain |
| Information disclosure | PII in feedback or error messages | PII scrubbed before storage; errors never echo row data |
| Denial of service | Expensive queries over the views | SELECT-only gateway, 100-row cap, no stacked statements |
| Elevation of privilege | Agent suspending sellers unilaterally | Suspensions always gated; tiers separate routine vs critical |

## LLM-specific (OWASP LLM Top 10, where relevant)
- **Prompt injection**: user questions never reach SQL unfiltered — the
  gateway strips literals before keyword scanning and only fixed
  templates execute.
- **Excessive agency**: the agent cannot write to any table; all
  high-stakes actions need confirmation.
- **Training-data poisoning**: N/A (no training here); feedback is
  scrubbed and human-reviewed before becoming eval data.
