"""
WattWise — Streamlit app
========================

The clickable front end that ties the whole project together:
  real data  ->  pick appliances + deadlines  ->  optimise  ->  see £ & CO2 saved.

It reuses the SAME engine the notebooks use (backend/optimisation/scheduler.py),
so the app and the analysis can never disagree.

Run it from the project root:
    pip install streamlit
    streamlit run app/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

# make the backend package importable when run from anywhere
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.optimisation.scheduler import Appliance, schedule_appliance, run_at_fixed_hour

DATA = ROOT / "backend" / "data" / "processed" / "history.csv"

# ---- brand ----
EMERALD, PURPLE, INK = "#10B981", "#7C5CF0", "#241F3A"

st.set_page_config(page_title="WattWise", page_icon="⚡", layout="wide")


@st.cache_data
def load_day() -> tuple[pd.DataFrame, object]:
    """Most recent full 24h (48 slots) of real price + carbon."""
    df = pd.read_csv(DATA, parse_dates=["timestamp_utc"])
    local = df["timestamp_utc"].dt.tz_convert("Europe/London")
    df["hour"] = local.dt.hour + local.dt.minute / 60
    df["date"] = local.dt.date
    counts = df.groupby("date").size()
    full = counts[counts == 48].index[-1]
    return df[df["date"] == full].sort_values("hour").reset_index(drop=True), full


def hhmm(h: float) -> str:
    return f"{int(h):02d}:{int(round((h % 1) * 60)):02d}"


# ---- header ----
st.markdown(
    f"<h1 style='margin-bottom:0'>⚡🌿 WattWise</h1>"
    f"<p style='color:#6E6894;margin-top:4px'>Shift your flexible appliances to the cheapest, greenest half-hours.</p>",
    unsafe_allow_html=True,
)

if not DATA.exists():
    st.error("No data yet. Run `python backend/ingestion/fetch_history.py` first to download history.csv.")
    st.stop()

day, day_date = load_day()
st.caption(f"Using **real** NESO carbon + Octopus Agile data for North West England · {day_date}. "
           f"Appliance specs below are illustrative — edit them to match your home.")

# ---- controls ----
with st.sidebar:
    st.header("Your appliances")
    st.caption("Tick what you need to run, and set when it must be ready.")

    defaults = [
        ("EV charge", 10.0, 7.0, 7),
        ("Heat pump boost", 6.0, 3.0, 24),
        ("Dishwasher", 1.2, 0.6, 7),
        ("Washing machine", 1.0, 0.5, 22),
    ]
    chosen = []
    for name, kwh, kw, deadline in defaults:
        on = st.checkbox(name, value=True, key=f"on_{name}")
        if on:
            dl = st.slider(f"  {name} — ready by", 1, 24, deadline, key=f"dl_{name}")
            with st.expander(f"  {name} — advanced"):
                kwh = st.number_input("energy (kWh)", 0.1, 50.0, kwh, key=f"e_{name}")
                kw = st.number_input("power (kW)", 0.1, 22.0, kw, key=f"p_{name}")
            earliest = 8 if name == "Washing machine" else 0
            chosen.append(Appliance(name, kwh, kw, earliest, dl))

    st.divider()
    lam = st.slider("What matters more?", 0.0, 1.0, 0.5, 0.1,
                    help="0 = greenest · 1 = cheapest")
    st.caption(f"{'🌱 greenest' if lam < 0.4 else ('💷 cheapest' if lam > 0.6 else '⚖️ balanced')}")

if not chosen:
    st.info("Tick at least one appliance in the sidebar to see a plan.")
    st.stop()

# ---- optimise ----
rows, tot_sp, tot_bp, tot_sc, tot_bc = [], 0, 0, 0, 0
for a in chosen:
    try:
        smart = schedule_appliance(day, a, lam=lam)
    except ValueError as e:
        st.warning(str(e))
        continue
    base = run_at_fixed_hour(day, a, start_hour=18.0)
    tot_sp += smart["pounds"]; tot_bp += base["pounds"]
    tot_sc += smart["kg_co2"]; tot_bc += base["kg_co2"]
    rows.append({
        "Appliance": a.name,
        "Run": f"{hhmm(smart['start_hour'])}–{hhmm(smart['end_hour'])}",
        "Cost £": round(smart["pounds"], 2),
        "CO₂ kg": round(smart["kg_co2"], 2),
        "£ saved vs 6pm": round(base["pounds"] - smart["pounds"], 2),
        "kg saved vs 6pm": round(base["kg_co2"] - smart["kg_co2"], 2),
    })

# ---- headline metrics ----
c1, c2, c3 = st.columns(3)
c1.metric("💷 Saved vs 6pm", f"£{tot_bp - tot_sp:.2f}")
c2.metric("🌿 CO₂ avoided", f"{tot_bc - tot_sc:.2f} kg")
cheaper = (1 - tot_sp / tot_bp) * 100 if tot_bp else 0
c3.metric("vs the evening peak", f"{cheaper:.0f}% cheaper")

st.subheader("Tonight's plan")
st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

# ---- chart ----
st.subheader("When each appliance runs")
colors = ["#10B981", "#7C5CF0", "#3B82F6", "#F59E0B", "#EF4444"]
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 5), sharex=True)
ax1.plot(day["hour"], day["price_p_kwh"], color=INK, lw=1.6); ax1.set_ylabel("price p/kWh"); ax1.grid(alpha=.3)
ax2.plot(day["hour"], day["carbon_intensity"], color=INK, lw=1.6); ax2.set_ylabel("gCO₂/kWh"); ax2.set_xlabel("hour of day"); ax2.grid(alpha=.3)
for a, col in zip(chosen, colors):
    try:
        p = schedule_appliance(day, a, lam=lam)
    except ValueError:
        continue
    for ax in (ax1, ax2):
        ax.axvspan(p["start_hour"], p["end_hour"], color=col, alpha=0.22)
ax1.set_title("Shaded = when WattWise runs each appliance")
st.pyplot(fig)

st.caption("The optimiser and these numbers come from backend/optimisation/scheduler.py — the same engine used in the notebooks.")
