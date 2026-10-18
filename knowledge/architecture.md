# Architecture

```mermaid
flowchart TB
    subgraph Capture["Marketplace telemetry (SQLite, synthetic)"]
        S[sellers] --> L[listings]
        L --> O[orders]
        O --> D[disputes]
        S --> V[violations]
    end

    subgraph Spine["FDE spine"]
        VIEWS["4 read-only views\n+ SELECT-only gateway\n(SEC-SELECT-01/02/03)"]
        T2S["text2sql\n5 intents + retry"]
        RAG["TF-IDF SOP RAG\n4 SOPs, cited"]
        Q["listing-quality scorer\n5 signals, bands"]
        DT["dispute-triage engine\nordered cited rules"]
        FS["fraud/chargeback feed\nfake | live | gap"]
    end

    subgraph Control["Control plane"]
        ORCH["ReAct orchestrator\nmulti-intent fan-out"]
        ESC["T1-T4 escalation\n+ confirmation gates"]
        AUD["hash-chained audit"]
        FB["feedback capture\nPII scrubbed"]
    end

    Capture --> VIEWS
    VIEWS --> T2S --> ORCH
    RAG --> ORCH
    Q --> ORCH
    DT --> ORCH
    FS --> ORCH
    ORCH --> ESC --> AUD
    ORCH --> FB --> AUD
```

## Data flow
1. A question fans out to text2sql, RAG, the quality scorer, the triage
   engine, and the fraud feed as applicable.
2. High-stakes outcomes (suspensions, >$500 refunds) route through the
   confirmation gate instead of executing.
3. Every step is hash-chained in the audit log; user feedback is
   PII-scrubbed before storage.
