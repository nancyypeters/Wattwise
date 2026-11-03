"""
WattWise — Streamlit app  (styled to match the Figma "mix" prototype)
=====================================================================

Real data -> pick appliances + deadlines -> optimise -> see £ & CO2 saved.
Reuses the same engine as the notebooks: backend/optimisation/scheduler.py.

Run from the project root:
    pip install streamlit
    streamlit run app/app.py
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from backend.optimisation.scheduler import Appliance, schedule_appliance, run_at_fixed_hour

DATA = ROOT / "backend" / "data" / "processed" / "history.csv"

st.set_page_config(page_title="WattWise", page_icon="⚡", layout="wide")

# ---------------------------------------------------------------- styling
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;600;700;800&family=Hanken+Grotesk:wght@400;500;600;700&display=swap');
.stApp { background:#F1EFFA; }
html, body, [class*="css"], .stApp, p, div, span, label { font-family:'Hanken Grotesk', system-ui, sans-serif; }
#MainMenu, header[data-testid="stHeader"], footer { visibility:hidden; height:0; }
[data-testid="stToolbar"] { display:none; }
.block-container { padding-top:1.3rem; padding-bottom:2rem; max-width:1240px; }
[data-testid="stSidebar"] { background:#FFFFFF; border-right:1px solid #E7E2F5; }
[data-testid="stSidebar"] h2 { font-family:'Nunito',sans-serif; font-weight:800; color:#241F3A; }

.ww-head { display:flex; align-items:center; gap:14px; margin:2px 0 2px; }
.ww-brand { font-family:'Nunito',sans-serif; font-weight:800; font-size:30px; color:#241F3A; line-height:1; }
.ww-tag { color:#6E6894; font-size:15px; margin-top:4px; }
.ww-note { color:#6E6894; font-size:13px; margin:10px 0 20px; }

.ww-row { display:flex; gap:18px; margin-bottom:22px; }
.ww-hero { flex:1.5; background:linear-gradient(135deg,#10B981,#0EA372); border-radius:26px; padding:26px 32px; color:#fff; box-shadow:0 26px 50px -28px rgba(16,185,129,.75); }
.ww-hero-label { font-family:'Nunito',sans-serif; font-weight:700; font-size:13px; letter-spacing:.06em; opacity:.92; text-transform:uppercase; }
.ww-hero-num { font-family:'Nunito',sans-serif; font-weight:800; font-size:70px; line-height:1; margin:6px 0 8px; letter-spacing:-.02em; }
.ww-hero-sub { font-size:15px; opacity:.95; }
.ww-stats { flex:1; display:flex; flex-direction:column; gap:14px; }
.ww-stat { flex:1; background:#fff; border-radius:20px; padding:16px 22px; box-shadow:0 16px 38px -28px rgba(36,31,58,.4); display:flex; flex-direction:column; justify-content:center; }
.ww-stat-num { font-family:'Nunito',sans-serif; font-weight:800; font-size:30px; }
.ww-stat-lab { font-size:13px; color:#6E6894; margin-top:2px; }

.ww-h2 { font-family:'Nunito',sans-serif; font-weight:800; font-size:19px; color:#241F3A; margin:8px 2px 14px; }
.ww-tiles { display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:16px; margin-bottom:20px; }
.ww-tile { border-radius:24px; padding:20px 22px; }
.ww-badge { width:46px; height:46px; border-radius:50%; display:flex; align-items:center; justify-content:center; margin-bottom:14px; }
.ww-tile-title { font-family:'Nunito',sans-serif; font-weight:800; font-size:18px; margin-bottom:3px; }
.ww-tile-time { font-size:14px; font-weight:600; }
.ww-tile-note { font-size:13px; margin-top:10px; }

.ww-why { background:#fff; border-radius:22px; padding:18px 24px; box-shadow:0 16px 40px -28px rgba(36,31,58,.4); font-size:14px; color:#4A4466; margin-bottom:8px; }
.ww-chartcard { background:#fff; border-radius:22px; padding:10px 14px 4px; box-shadow:0 16px 40px -28px rgba(36,31,58,.4); }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- data
@st.cache_data
def load_day():
    df = pd.read_csv(DATA, parse_dates=["timestamp_utc"])
    local = df["timestamp_utc"].dt.tz_convert("Europe/London")
    df["hour"] = local.dt.hour + local.dt.minute / 60
    df["date"] = local.dt.date
    counts = df.groupby("date").size()
    full = counts[counts == 48].index[-1]
    return df[df["date"] == full].sort_values("hour").reset_index(drop=True), full


def hhmm(h): return f"{int(h):02d}:{int(round((h % 1) * 60)):02d}"

# appliance visual themes + icons (match the Figma tiles)
CAR = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M4 14l1.6-4.6A2 2 0 0 1 7.5 8h9a2 2 0 0 1 1.9 1.4L20 14v3h-2m-12 0H4v-3h16" stroke="#fff" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/><circle cx="8" cy="17" r="1.6" fill="#fff"/><circle cx="16" cy="17" r="1.6" fill="#fff"/></svg>'
FLAME = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><path d="M12 3c3.2 3.8 5 6.2 5 9a5 5 0 0 1-10 0c0-1.9.8-3.3 2.1-4.4-.1 1.6.8 2.4 1.6 2.4.9 0 1.4-1 .4-2.6C10.5 5.8 11.1 4.3 12 3z" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>'
DISH = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect x="5" y="4" width="14" height="16" rx="2" stroke="#fff" stroke-width="1.6"/><path d="M5 8.5h14" stroke="#fff" stroke-width="1.6"/><circle cx="12" cy="14" r="3" stroke="#fff" stroke-width="1.6"/></svg>'
WASH = '<svg width="24" height="24" viewBox="0 0 24 24" fill="none"><rect x="5" y="3" width="14" height="18" rx="2" stroke="#fff" stroke-width="1.6"/><circle cx="12" cy="13" r="4.5" stroke="#fff" stroke-width="1.6"/><path d="M8.5 13a3.5 3.5 0 0 1 3.5-3.5" stroke="#fff" stroke-width="1.6" stroke-linecap="round"/></svg>'
THEME = {
    "EV charge":       {"card":"#CBF3E0","icon":"#10B981","title":"#0B6B49","sub":"#2C7A5C","svg":CAR,   "colour":"#10B981"},
    "Heat pump boost": {"card":"#FFE1D3","icon":"#F97316","title":"#B5431C","sub":"#B5563A","svg":FLAME, "colour":"#F97316"},
    "Dishwasher":      {"card":"#D7E6FF","icon":"#3B82F6","title":"#2158C9","sub":"#3A66C0","svg":DISH,  "colour":"#3B82F6"},
    "Washing machine": {"card":"#E7E0FF","icon":"#7C5CF0","title":"#5B3FC0","sub":"#6B5CAF","svg":WASH,  "colour":"#7C5CF0"},
}
MARK = '<svg width="40" height="40" viewBox="0 0 72 72"><path d="M30 6 L13 33 H24 L18 56 L41 27 H30 L36 6 Z" fill="#F2B705"/><path d="M58 14 C30 14 18 26 18 54 C46 54 58 42 58 14 Z" fill="#2E9E3F"/></svg>'

# ---------------------------------------------------------------- header
st.markdown(f"""
<div class="ww-head">{MARK}<div><div class="ww-brand">WattWise</div>
<div class="ww-tag">Shift your flexible appliances to the cheapest, greenest half-hours.</div></div></div>
""", unsafe_allow_html=True)

if not DATA.exists():
    st.error("No data yet — run `python backend/ingestion/fetch_history.py` first.")
    st.stop()

day, day_date = load_day()
st.markdown(f'<div class="ww-note">Using <b>real</b> NESO carbon + Octopus Agile data for North West England · {day_date}. '
            f'Appliance specs are illustrative — edit them in the sidebar.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Your appliances")
    st.caption("Tick what you need to run, and set when it must be ready.")
    defaults = [("EV charge",10.0,7.0,7), ("Heat pump boost",6.0,3.0,24),
                ("Dishwasher",1.2,0.6,7), ("Washing machine",1.0,0.5,22)]
    chosen = []
    for name, kwh, kw, dl0 in defaults:
        if st.checkbox(name, value=True, key=f"on_{name}"):
            dl = st.slider(f"{name} — ready by", 1, 24, dl0, key=f"dl_{name}")
            with st.expander(f"{name} — advanced"):
                kwh = st.number_input("energy (kWh)", 0.1, 50.0, kwh, key=f"e_{name}")
                kw = st.number_input("power (kW)", 0.1, 22.0, kw, key=f"p_{name}")
            chosen.append(Appliance(name, kwh, kw, 8 if name == "Washing machine" else 0, dl))
    st.divider()
    lam = st.slider("What matters more?", 0.0, 1.0, 0.5, 0.1, help="0 = greenest · 1 = cheapest")
    st.caption("🌱 greenest" if lam < 0.4 else ("💷 cheapest" if lam > 0.6 else "⚖️ balanced"))

if not chosen:
    st.info("Tick at least one appliance in the sidebar to see a plan.")
    st.stop()

# ---------------------------------------------------------------- optimise
plans, tot_sp, tot_bp, tot_sc, tot_bc = [], 0, 0, 0, 0
for a in chosen:
    try:
        smart = schedule_appliance(day, a, lam=lam)
    except ValueError as e:
        st.warning(str(e)); continue
    base = run_at_fixed_hour(day, a, start_hour=18.0)
    tot_sp += smart["pounds"]; tot_bp += base["pounds"]
    tot_sc += smart["kg_co2"]; tot_bc += base["kg_co2"]
    plans.append((a, smart, base["pounds"] - smart["pounds"]))

saved_p = tot_bp - tot_sp
saved_c = tot_bc - tot_sc
pct = (1 - tot_sp / tot_bp) * 100 if tot_bp else 0

# ---------------------------------------------------------------- hero + stats
st.markdown(f"""
<div class="ww-row">
  <div class="ww-hero">
    <div class="ww-hero-label">You'll save vs the 6pm peak</div>
    <div class="ww-hero-num">£{saved_p:.2f}</div>
    <div class="ww-hero-sub">running {len(plans)} appliance{'s' if len(plans)!=1 else ''} in the cheap, green hours — each ready on time</div>
  </div>
  <div class="ww-stats">
    <div class="ww-stat"><div class="ww-stat-num" style="color:#0E9E6E">{saved_c:.2f} kg</div><div class="ww-stat-lab">CO₂ avoided</div></div>
    <div class="ww-stat"><div class="ww-stat-num" style="color:#7C5CF0">{pct:.0f}%</div><div class="ww-stat-lab">cheaper than the 6 pm peak</div></div>
  </div>
</div>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------- appliance tiles
st.markdown('<div class="ww-h2">Your plan</div>', unsafe_allow_html=True)
tiles = '<div class="ww-tiles">'
for a, smart, saved in plans:
    t = THEME.get(a.name, THEME["Dishwasher"])
    tiles += f"""<div class="ww-tile" style="background:{t['card']}">
      <div class="ww-badge" style="background:{t['icon']}">{t['svg']}</div>
      <div class="ww-tile-title" style="color:{t['title']}">{a.name}</div>
      <div class="ww-tile-time" style="color:{t['sub']}">{hhmm(smart['start_hour'])} – {hhmm(smart['end_hour'])}</div>
      <div class="ww-tile-note" style="color:{t['sub']}">ready by {int(a.deadline_hour)}:00 · <b>saves £{saved:.2f}</b></div>
    </div>"""
tiles += '</div>'
st.markdown(tiles, unsafe_allow_html=True)

st.markdown('<div class="ww-why"><b>Why these hours?</b> Power is cheapest and greenest overnight — WattWise skips the 4–7 pm peak entirely and still has everything ready by your deadlines.</div>', unsafe_allow_html=True)

# ---------------------------------------------------------------- chart
st.markdown('<div class="ww-h2">When each appliance runs</div>', unsafe_allow_html=True)
fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(11, 4.6), sharex=True)
fig.patch.set_facecolor("#FFFFFF")
for ax, col, lab in [(ax1, "price_p_kwh", "price p/kWh"), (ax2, "carbon_intensity", "gCO₂/kWh")]:
    ax.set_facecolor("#FFFFFF")
    ax.plot(day["hour"], day[col], color="#241F3A", lw=1.7)
    ax.set_ylabel(lab, color="#6E6894")
    ax.grid(alpha=.25); ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(colors="#6E6894")
ax2.set_xlabel("hour of day", color="#6E6894")
for a, smart, _ in plans:
    col = THEME.get(a.name, THEME["Dishwasher"])["colour"]
    for ax in (ax1, ax2):
        ax.axvspan(smart["start_hour"], smart["end_hour"], color=col, alpha=0.22)
st.markdown('<div class="ww-chartcard">', unsafe_allow_html=True)
st.pyplot(fig)
st.markdown('</div>', unsafe_allow_html=True)

with st.expander("See the full numbers"):
    st.dataframe(pd.DataFrame([{
        "Appliance": a.name, "Run": f"{hhmm(s['start_hour'])}–{hhmm(s['end_hour'])}",
        "Cost £": round(s["pounds"], 2), "CO₂ kg": round(s["kg_co2"], 2), "£ saved": round(sv, 2),
    } for a, s, sv in plans]), hide_index=True, use_container_width=True)
    st.caption("Optimiser: backend/optimisation/scheduler.py — the same engine the notebooks use.")
