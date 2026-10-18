"""Listing-quality scorer — domain differentiator.

Scores a listing 0-100 from five signals, each with a per-signal breakdown
so sellers see exactly what to fix. Bands: excellent (>=85), good (70-84),
needs-work (50-69), poor (<50).
"""

from __future__ import annotations

from dataclasses import dataclass, field

TITLE_MIN, TITLE_MAX = 20, 140
DESC_MIN = 40

PROHIBITED_PHRASES = ("best deal", "buy now", "cheapest", "!!!", "free money")


@dataclass
class SignalScore:
    signal: str
    points: float      # 0..max_points
    max_points: float
    detail: str


@dataclass
class QualityReport:
    listing_id: str
    total: float
    band: str
    signals: list[SignalScore] = field(default_factory=list)

    def breakdown(self) -> dict[str, float]:
        return {s.signal: round(s.points, 1) for s in self.signals}


def _title_score(title: str) -> SignalScore:
    low = title.lower()
    if any(p in low for p in ("!!!",)):
        return SignalScore("title", 0.0, 25.0, "excessive punctuation")
    words = title.split()
    repeats = len(words) - len({w.lower() for w in words})
    if repeats >= 2:
        return SignalScore("title", 5.0, 25.0, f"keyword stuffing ({repeats} repeats)")
    n = len(title)
    if n < TITLE_MIN:
        return SignalScore("title", 10.0, 25.0, f"too short ({n} chars)")
    if n > TITLE_MAX:
        return SignalScore("title", 12.0, 25.0, f"too long ({n} chars)")
    return SignalScore("title", 25.0, 25.0, "clear and specific")


def _description_score(description: str) -> SignalScore:
    n = len(description.strip())
    if n < 10:
        return SignalScore("description", 2.0, 25.0, "nearly empty")
    if n < DESC_MIN:
        return SignalScore("description", 12.0, 25.0, f"thin ({n} chars)")
    return SignalScore("description", 25.0, 25.0, f"complete ({n} chars)")


def _image_score(has_image: bool) -> SignalScore:
    return SignalScore(
        "image", 15.0 if has_image else 0.0, 15.0,
        "present" if has_image else "missing — listings with images convert better",
    )


def _compliance_score(flags: str) -> SignalScore:
    items = [f for f in (flags or "").split(",") if f]
    if not items:
        return SignalScore("compliance", 20.0, 20.0, "clean")
    return SignalScore("compliance", 0.0, 20.0, f"flags: {', '.join(items)}")


def _pricing_score(price: float) -> SignalScore:
    if price <= 0:
        return SignalScore("pricing", 0.0, 15.0, "invalid price")
    # Round, sane prices score; absurd precision or zero pricing does not.
    if round(price, 2) != price:
        return SignalScore("pricing", 8.0, 15.0, "over-precise price")
    return SignalScore("pricing", 15.0, 15.0, "sane price")


def score_listing(listing_id: str, title: str, description: str,
                  has_image: bool, compliance_flags: str,
                  price: float) -> QualityReport:
    signals = [
        _title_score(title),
        _description_score(description),
        _image_score(bool(has_image)),
        _compliance_score(compliance_flags),
        _pricing_score(price),
    ]
    total = round(sum(s.points for s in signals), 1)
    band = ("excellent" if total >= 85 else "good" if total >= 70
            else "needs-work" if total >= 50 else "poor")
    return QualityReport(listing_id=listing_id, total=total, band=band,
                         signals=signals)
