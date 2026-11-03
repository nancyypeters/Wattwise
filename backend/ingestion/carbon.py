"""
WattWise — NESO Carbon Intensity ingestion
===========================================

Pulls real UK grid carbon-intensity data from the NESO Carbon Intensity API
(free, no API key required) and saves two tidy CSVs to backend/data/raw/:

  1. carbon_national_forecast.csv  — the next 48 hours, half-hourly (national)
  2. carbon_regional_now.csv       — a current snapshot for all 14 GB regions

Why this is the first thing we build: it proves WattWise can retrieve, parse and
store *real* energy data before we build anything on top of it. Carbon intensity is
also the easier of our two feeds (no key, stable endpoints), so it's the right place
to start.

API docs: https://carbon-intensity.github.io/api-definitions/

Run it:
    python backend/ingestion/carbon.py
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

BASE = "https://api.carbonintensity.org.uk"

# backend/data/raw/ relative to this file (…/backend/ingestion/carbon.py -> …/backend/data/raw)
RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def _get(url: str) -> dict:
    """GET a NESO endpoint and return the parsed JSON, with a clear error on failure."""
    response = requests.get(url, headers={"Accept": "application/json"}, timeout=30)
    response.raise_for_status()  # turns HTTP 4xx/5xx into an exception we can see
    return response.json()


def fetch_national_forecast_48h() -> pd.DataFrame:
    """Next 48 hours of national carbon intensity, half-hourly (gCO2/kWh)."""
    now = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%MZ")
    payload = _get(f"{BASE}/intensity/{now}/fw48h")["data"]

    rows = []
    for period in payload:
        rows.append(
            {
                "timestamp_utc": period["from"],
                "carbon_intensity": period["intensity"].get("forecast"),
                "index": period["intensity"].get("index"),  # e.g. "low" / "moderate" / "high"
                "data_source": "NESO Carbon Intensity API",
                "data_type": "published_forecast",  # NOT our own model, NOT an actual reading
            }
        )

    df = pd.DataFrame(rows)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df


def fetch_regional_now() -> pd.DataFrame:
    """Current carbon-intensity snapshot for all 14 GB regions."""
    block = _get(f"{BASE}/regional")["data"][0]

    rows = []
    for region in block["regions"]:
        rows.append(
            {
                "timestamp_utc": block["from"],
                "region_id": region["regionid"],
                "region": region["shortname"],  # e.g. "North Scotland", "London"
                "carbon_intensity": region["intensity"].get("forecast"),
                "index": region["intensity"].get("index"),
                "data_source": "NESO Carbon Intensity API (regional)",
                "data_type": "published_forecast",
            }
        )

    df = pd.DataFrame(rows)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    national = fetch_national_forecast_48h()
    regional = fetch_regional_now()

    national.to_csv(RAW_DIR / "carbon_national_forecast.csv", index=False)
    regional.to_csv(RAW_DIR / "carbon_regional_now.csv", index=False)

    print(f"National forecast: {len(national)} half-hourly periods (next 48h)")
    print(national.head(6).to_string(index=False))
    print(f"\nRegional snapshot: {len(regional)} GB regions")
    print(
        regional.sort_values("carbon_intensity")[["region", "carbon_intensity", "index"]]
        .to_string(index=False)
    )
    print(f"\nSaved CSVs to: {RAW_DIR}")


if __name__ == "__main__":
    main()
