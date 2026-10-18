"""Print the domain differentiators on the seeded data (README block, CI-checked)."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from sellerops.demo_helpers import dispute_triage_demo, quality_summary  # noqa: E402
from sellerops.quality import score_listing  # noqa: E402
from sellerops.telemetry import build_db  # noqa: E402
from sellerops.views import GatewayError, install_views, run_query  # noqa: E402

rows = quality_summary()
print(f"Listing-quality scorer: {len(rows)} listings; bands "
      f"{dict(sorted({b: sum(r['band'] == b for r in rows) for b in {r['band'] for r in rows}}.items()))}")
for r in rows:
    if r["band"] in ("poor", "needs-work", "good"):
        print(f"  {r['listing_id']}: {r['total']} {r['band']} {r['breakdown']}")
r = score_listing("EXAMPLE", "Cheapest enamel plates - best deal, buy now",
                  "Set of four enamel camp plates, assorted colors, dishwasher safe.", True, "", 24.0)
print(f"  unflagged pressure phrases: {r.total} {r.band}; compliance {r.signals[3].detail}")
print("Dispute triage (first terminal rule wins):")
for d in dispute_triage_demo():
    print(f"  {d['dispute_id']}: {d['action']} [{d['rules']}] {d['reason']}")
conn = build_db()
install_views(conn)
try:
    run_query(conn, 'SELECT * FROM v_listing_quality, "sellers"')
except GatewayError as exc:
    print(f"Gateway: {exc}")
