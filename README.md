# WattWise

**An AI-powered, carbon- and cost-aware UK home energy optimisation platform.**

WattWise forecasts two live signals for your region — the **electricity price** (p/kWh,
e.g. Octopus Agile) and the **grid carbon intensity** (gCO2/kWh, from NESO) — and
recommends *when* to run flexible appliances (EV charging, heat pump, dishwasher,
washing machine) so they finish by your deadline while being as cheap and clean as
possible. It then reports the £ and kgCO2 saved versus the evening peak, and an AI
assistant explains the plan.

> **Status: in development.** A visual prototype exists (built on *simulated* data). This
> repository is the *real* system: data pipeline → analysis → forecasting → optimisation
> → savings → AI assistant → dashboards → multi-agent simulation. Figures from the visual
> prototype (e.g. "£6.28 / 4.46 kg") are **illustrative**, not proven savings.

Final-year BSc (Hons) Computer Science project — Nancy Peter, UA92 Manchester.

---

## Quick start (Windows / PowerShell)

```powershell
# 1. Create and activate a virtual environment
python -m venv .venv
.venv\Scripts\Activate.ps1

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run the first data ingestion (NESO carbon intensity — free, no key)
python backend/ingestion/carbon.py
```

On macOS/Linux, activate with `source .venv/bin/activate` instead.

You should see the next-48h national carbon forecast and a regional snapshot printed,
and two CSVs written to `backend/data/raw/`.

---

## Project structure

```
wattwise/
  backend/
    ingestion/        # pull raw data from external APIs
      carbon.py         # NESO Carbon Intensity API  (DONE — run this first)
      octopus.py        # Octopus Agile prices       (next milestone)
    analysis/         # clean + combine datasets, feature engineering
    forecasting/      # ML models vs naive baselines
    optimisation/     # appliance scheduling (OR-Tools / PuLP)
    tests/            # pytest unit tests for calculations
    data/
      raw/            # untouched API pulls
      processed/      # combined, cleaned datasets
  notebooks/          # exploratory analysis (Jupyter)
  app/                # Streamlit interface (later)
  documentation/      # master spec, data dictionary, methodology
  requirements.txt
```

## Data sources
- **NESO Carbon Intensity API** — https://carbon-intensity.github.io/api-definitions/ (free, no key)
- **Octopus Energy API** — https://developer.octopus.energy/ (free public tariff data)
- **Open-Meteo** (optional, weather features) — https://open-meteo.com/

## Honesty rules (kept throughout)
- Never present simulated data as live.
- Distinguish actual data, published forecasts and model predictions (`data_type` column).
- The optimiser does the maths; the LLM only explains results.
