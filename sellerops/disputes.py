"""Dispute-triage engine — domain differentiator.

Classifies a dispute into refund / replace / escalate using an ordered rule
set. Every decision cites the rules that fired, in evaluation order, so the
outcome is auditable. First matching terminal rule wins.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# Policy rule IDs — cited in decisions and the audit trail.
R_NOT_RECEIVED_NO_SCAN = "DSP-REFUND-01"   # not received + no delivery scan -> refund
R_DAMAGED_IN_STOCK = "DSP-REPLACE-02"      # damaged + replaceable -> replace
R_HIGH_VALUE = "DSP-ESC-03"                # amount over threshold -> escalate
R_COUNTERFEIT = "DSP-POLICY-04"            # counterfeit allegation -> escalate + violation
R_DEFAULT = "DSP-ESC-00"                    # anything else -> escalate with reason

HIGH_VALUE_THRESHOLD = 500.0


@dataclass
class Dispute:
    dispute_id: str
    order_id: str
    reason_code: str        # not_received | damaged | not_as_described | other
    amount: float
    delivery_scanned: bool = False
    replaceable: bool = False
    counterfeit_alleged: bool = False


@dataclass
class TriageDecision:
    dispute_id: str
    action: str             # refund | replace | escalate
    rules_fired: list[str] = field(default_factory=list)
    reason: str = ""

    def cited(self) -> str:
        return ", ".join(self.rules_fired)


def triage(d: Dispute) -> TriageDecision:
    fired: list[str] = []
    if d.counterfeit_alleged:
        fired.append(R_COUNTERFEIT)
        return TriageDecision(d.dispute_id, "escalate", fired,
                              "counterfeit allegation requires trust-and-safety review")
    if d.amount > HIGH_VALUE_THRESHOLD:
        fired.append(R_HIGH_VALUE)
        return TriageDecision(d.dispute_id, "escalate", fired,
                              f"amount ${d.amount:.2f} exceeds ${HIGH_VALUE_THRESHOLD:.2f} auto-action limit")
    if d.reason_code == "not_received" and not d.delivery_scanned:
        fired.append(R_NOT_RECEIVED_NO_SCAN)
        return TriageDecision(d.dispute_id, "refund", fired,
                              "no delivery scan on record")
    if d.reason_code == "damaged" and d.replaceable:
        fired.append(R_DAMAGED_IN_STOCK)
        return TriageDecision(d.dispute_id, "replace", fired,
                              "item damaged and replacement stock available")
    fired.append(R_DEFAULT)
    return TriageDecision(d.dispute_id, "escalate", fired,
                          f"reason '{d.reason_code}' needs human review")
