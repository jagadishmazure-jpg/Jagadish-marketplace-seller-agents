"""Fraud / chargeback-risk feed with fake and live backends.

The fake backend is seeded and deterministic. The live backend is a stub
with a documented interface: when no live credentials are configured it
returns an explicit gap result — it never hallucinates a risk score.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class RiskSignal:
    subject_id: str      # seller_id or order_id
    risk_score: float    # 0..1, higher = riskier
    backend: str         # "fake" | "live" | "gap"
    detail: str


class FakeFraudFeed:
    """Deterministic seeded risk scores."""

    def __init__(self, seed: int = 42):
        self.seed = seed

    def score(self, subject_id: str) -> RiskSignal:
        # Stable hash -> score; known-bad anchor scores high on purpose.
        h = sum((i + 1) * ord(c) for i, c in enumerate(subject_id)) % 100
        base = h / 100.0
        if "SUSP" in subject_id:
            base = max(base, 0.91)
        return RiskSignal(subject_id, round(base, 3), "fake",
                          f"seeded score (seed={self.seed})")


class LiveFraudFeed:
    """Stub for a real chargeback-risk provider.

    Configure via ``api_key`` + ``endpoint``. Without both, every call
    returns an explicit gap — callers must handle it, never invent data.
    """

    def __init__(self, api_key: str | None = None, endpoint: str | None = None):
        self.api_key = api_key
        self.endpoint = endpoint

    @property
    def configured(self) -> bool:
        return bool(self.api_key and self.endpoint)

    def score(self, subject_id: str) -> RiskSignal:
        if not self.configured:
            return RiskSignal(subject_id, -1.0, "gap",
                              "live feed not configured: api_key/endpoint missing; "
                              "no risk score available")
        raise NotImplementedError("live provider call goes here")
