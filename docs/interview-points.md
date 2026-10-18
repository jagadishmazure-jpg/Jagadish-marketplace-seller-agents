# Interview points

- **Why a quality scorer instead of binary policy checks?** Binary
  checks catch violations; a continuous score catches *decay* — listings
  that are technically compliant but eroding buyer trust. The
  per-signal breakdown turns the score into seller coaching.
- **Why ordered, cited dispute rules?** Reproducibility. Two runs over
  the same dispute must produce the same decision and the same cited
  rules, or appeals and chargebacks multiply.
- **What's the blast radius of a bad triage?** A wrong refund costs
  money; a wrong suspension costs a seller relationship. That's why
  suspensions and high-value refunds sit behind confirmation gates
  while low-value refunds auto-resolve.
- **How do you know the RAG isn't hallucinating policy?** Citations are
  `file §section`; below-threshold queries return explicit not-found.
  The SOPs are the only policy source the agent may quote.
- **Where does PII go?** Nowhere persistent unscrubbed: feedback text
  is scrubbed for emails, phones, SSNs, and card numbers *before*
  storage, and audit entries never echo raw row data.
