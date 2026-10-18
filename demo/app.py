"""Thin Streamlit demo. streamlit is imported lazily so the package
and its tests never require it. Run:  pip install streamlit; streamlit run demo/app.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    import streamlit as st
except ImportError:  # pragma: no cover
    raise SystemExit("pip install streamlit, then: streamlit run demo/app.py") from None

from sellerops.demo_helpers import (  # noqa: E402
    dispute_triage_demo,
    quality_summary,
    seller_health,
)

st.title("Marketplace seller operations — demo")

tab1, tab2, tab3 = st.tabs(["Listing quality", "Dispute triage", "Seller health"])

with tab1:
    for row in quality_summary():
        st.write(f"**{row['listing_id']}** — {row['band']} ({row['total']})")
        st.json(row["breakdown"])

with tab2:
    for row in dispute_triage_demo():
        st.write(f"**{row['dispute_id']}** → {row['action']} "
                 f"({row['rules']}) — {row['reason']}")

with tab3:
    for row in seller_health():
        st.write(f"**{row['seller_id']}** {row['name']} — {row['tier']}, "
                 f"rating {row['rating']}, defect {row['defect_rate']}, "
                 f"open disputes {row['open_disputes']}")
