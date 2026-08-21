from __future__ import annotations

from datetime import date

import pandas as pd
import plotly.express as px
import streamlit as st


st.set_page_config(page_title="Shipping Brain — AI Workflow Demo", page_icon="🚢", layout="wide")


@st.cache_data
def synthetic_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    vessels = pd.DataFrame(
        [
            ["MV ORION", 38200, "Handymax", "Shanghai", "CJK", "2026-09-02", "4x30t", "Open"],
            ["MV AURORA", 56800, "Supramax", "Singapore", "SE Asia", "2026-09-05", "4x30t", "Open"],
            ["MV HORIZON", 63500, "Ultramax", "Qingdao", "North China", "2026-09-06", "4x30t", "Open"],
            ["MV ATLAS", 32400, "Handysize", "Ho Chi Minh", "SE Asia", "2026-09-08", "4x25t", "On subs"],
            ["MV VEGA", 81200, "Panamax", "Ningbo", "CJK", "2026-09-10", "Gearless", "Open"],
            ["MV LUMEN", 60400, "Ultramax", "Kandla", "West India", "2026-09-12", "4x30t", "Open"],
        ],
        columns=["Vessel", "DWT", "Class", "Open port", "Region", "Open date", "Gear", "Status"],
    )
    cargoes = pd.DataFrame(
        [
            ["Steel coils", 33000, "Shanghai", "Mombasa", "2026-09-03", "CJK", "East Africa"],
            ["Fertilizer", 52000, "Qingdao", "Alexandria", "2026-09-07", "North China", "Mediterranean"],
            ["Bagged rice", 28000, "Ho Chi Minh", "Lagos", "2026-09-09", "SE Asia", "West Africa"],
            ["Pet coke", 58000, "Kandla", "Chittagong", "2026-09-13", "West India", "ISC"],
        ],
        columns=["Cargo", "Quantity (mt)", "Load port", "Discharge port", "Laycan", "Load region", "Discharge region"],
    )
    inbox = pd.DataFrame(
        [
            ["OPEN LIST — MV ORION", "TONNAGE", 0.96, "Ready for review", "broker@example.com"],
            ["33K STEEL COILS / SHANGHAI–MOMBASA", "CARGO", 0.93, "Ready for review", "charterer@example.com"],
            ["WEEKLY DRY BULK MARKET NOTE", "MARKET", 0.89, "Archived", "research@example.com"],
            ["RECAP — MV ATLAS", "FIXTURE", 0.84, "Needs verification", "ops@example.com"],
        ],
        columns=["Subject", "AI class", "Confidence", "Review state", "Sender"],
    )
    return vessels, cargoes, inbox


def fit_score(vessel: pd.Series, cargo: pd.Series) -> tuple[int, str]:
    capacity_ratio = cargo["Quantity (mt)"] / vessel["DWT"]
    capacity = 45 if 0.72 <= capacity_ratio <= 0.95 else 20 if capacity_ratio <= 1 else 0
    region = 35 if vessel["Region"] == cargo["Load region"] else 12
    days = abs((pd.Timestamp(vessel["Open date"]) - pd.Timestamp(cargo["Laycan"])).days)
    timing = max(0, 20 - days * 4)
    score = capacity + region + timing
    reason = f"capacity {capacity}/45 · position {region}/35 · timing {timing}/20"
    return score, reason


vessels, cargoes, inbox = synthetic_data()

st.title("Shipping Brain")
st.caption("AI-assisted email intelligence for shipping operations · synthetic portfolio demo")
st.info("This interface contains synthetic records only. It does not connect to a mailbox or external API.")

with st.sidebar:
    st.header("Market filters")
    all_regions = sorted(vessels["Region"].unique())
    all_classes = sorted(vessels["Class"].unique())
    regions = st.multiselect("Open region", all_regions, default=all_regions)
    vessel_classes = st.multiselect("Vessel class", all_classes, default=all_classes)
    st.caption(f"Snapshot date: {date(2026, 8, 21):%d %b %Y}")

filtered = vessels[vessels["Region"].isin(regions) & vessels["Class"].isin(vessel_classes)]

tab1, tab2, tab3, tab4 = st.tabs(["Inbox intelligence", "Market radar", "Matching", "Workflow & controls"])

with tab1:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Messages reviewed", len(inbox))
    c2.metric("Ready for review", int((inbox["Review state"] == "Ready for review").sum()))
    c3.metric("Average confidence", f"{inbox['Confidence'].mean():.0%}")
    c4.metric("Human checkpoints", "1 per record")
    st.dataframe(inbox.style.format({"Confidence": "{:.0%}"}), use_container_width=True, hide_index=True)
    selected = st.selectbox("Inspect extracted evidence", inbox["Subject"])
    row = inbox[inbox["Subject"] == selected].iloc[0]
    left, right = st.columns(2)
    with left:
        st.subheader("Source snippet")
        st.code(
            "Good day. Please note the following synthetic position:\n"
            "MV ORION / 38,200 DWT / OPEN SHANGHAI 02 SEP / 4X30T.\n"
            "Kindly advise suitable cargoes.",
            language=None,
        )
    with right:
        st.subheader("Proposed structured record")
        st.json(
            {
                "type": row["AI class"],
                "vessel_name": "MV ORION",
                "dwt": 38200,
                "open_port": "Shanghai",
                "open_date": "2026-09-02",
                "gear": "4x30t",
                "confidence": row["Confidence"],
                "review_required": True,
            }
        )

with tab2:
    a, b, c = st.columns(3)
    a.metric("Open vessels", len(filtered))
    b.metric("Synthetic cargo orders", len(cargoes))
    c.metric("Capacity represented", f"{filtered['DWT'].sum() / 1000:.0f}k DWT")
    chart = px.bar(
        filtered,
        x="Region",
        y="DWT",
        color="Class",
        hover_data=["Vessel", "Open port", "Open date"],
        title="Available capacity by open region",
    )
    st.plotly_chart(chart, use_container_width=True)
    st.dataframe(filtered, use_container_width=True, hide_index=True)

with tab3:
    cargo_name = st.selectbox("Cargo order", cargoes["Cargo"])
    cargo = cargoes[cargoes["Cargo"] == cargo_name].iloc[0]
    matches = []
    for _, vessel in filtered.iterrows():
        score, reason = fit_score(vessel, cargo)
        matches.append({"Vessel": vessel["Vessel"], "Fit score": score, "Why": reason, "Status": vessel["Status"]})
    st.caption("Transparent heuristic shortlist; the operator makes the final decision.")
    if matches:
        match_df = pd.DataFrame(matches).sort_values("Fit score", ascending=False)
        st.dataframe(match_df, use_container_width=True, hide_index=True)
    else:
        st.warning("Select at least one open region and vessel class to generate a shortlist.")

with tab4:
    st.subheader("Human-in-the-loop workflow")
    steps = pd.DataFrame(
        [
            [1, "Ingest", "Read approved mailbox", "Credentials remain local"],
            [2, "Classify", "Tonnage / cargo / market / fixture", "Confidence threshold"],
            [3, "Extract", "Map text to a typed schema", "Preserve source evidence"],
            [4, "Validate", "Normalize dates, ports, and quantities", "Flag uncertain fields"],
            [5, "Review", "Operator accepts or corrects", "Mandatory approval"],
            [6, "Use", "Dashboard, export, or matching shortlist", "Audit the decision trail"],
        ],
        columns=["Step", "Stage", "System action", "Control"],
    )
    st.dataframe(steps, use_container_width=True, hide_index=True)
    st.subheader("Production gaps intentionally left visible")
    st.markdown(
        "- Role-based access and enterprise identity\n"
        "- Field-level evaluation against a labeled test set\n"
        "- Approved integrations and retention policies\n"
        "- Monitoring for extraction drift and operator overrides"
    )
