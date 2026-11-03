"""
WattWise — historical data for forecasting (Phase 3 prep)
=========================================================

Forecasting needs HISTORY to learn from. Our live scripts only see the next
48h, which isn't enough to train a model. Happily, both of our free APIs also
serve the PAST, so this script pulls roughly the last 30 days of half-hourly
data and saves a training set:

  backend/data/processed/history.csv   (timestamp, price_p_kwh, carbon_intensity)

  - Carbon: NESO gives the *actual measured* carbon for past half-hours
    (not a forecast) — pulled in <=10-day chunks because the API caps the window.
  - Price: Octopus serves past Agile unit rates for your region, paged.

Run it once (it takes a minute — it's downloading ~30 days of data):
    python backend/ingestion/fetch_history.py
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

CARBON_BASE = "https://api.carbonintensity.org.uk"
OCTO_BASE = "https://api.octopus.energy/v1"

PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"

GSP_REGIONS = {
    "A": "East England", "B": "East Midlands", "C": "London",
    "D": "North Wales & Merseyside", "E": "West Midlands", "F": "North East England",
    "G": "North West England", "H": "Southern England", "J": "South East England",
    "K": "South Wales", "L": "South West England", "M": "Yorkshire",
    "N": "South Scotland", "P": "North Scotland",
}
REGION = "G"      # North West England (Manchester) — match your other scripts
DAYS = 30         # how much history to pull


def _get(url: str, params: dict | None = None) -> dict:
    r = requests.get(url, params=params, headers={"Accept": "application/json"}, timeout=60)
    r.raise_for_status()
    return r.json()


def _iso(t: dt.datetime) -> str:
    return t.strftime("%Y-%m-%dT%H:%MZ")


def fetch_carbon_history(days: int = DAYS) -> pd.DataFrame:
    """Actual measured carbon intensity for the last `days` days, half-hourly."""
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(days=days)

    rows: list[dict] = []
    chunk_start = start
    while chunk_start < end:
        chunk_end = min(chunk_start + dt.timedelta(days=10), end)  # API caps the window
        data = _get(f"{CARBON_BASE}/intensity/{_iso(chunk_start)}/{_iso(chunk_end)}")["data"]
        for p in data:
            intensity = p["intensity"]
            value = intensity.get("actual")
            rows.append(
                {
                    "timestamp_utc": p["from"],
                    "carbon_intensity": value if value is not None else intensity.get("forecast"),
                }
            )
        chunk_start = chunk_end

    df = pd.DataFrame(rows)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df.drop_duplicates("timestamp_utc").sort_values("timestamp_utc").reset_index(drop=True)


def find_current_agile_product() -> str:
    today = dt.date.today().isoformat()
    candidates: list[tuple[str, str]] = []
    url: str | None = f"{OCTO_BASE}/products/"
    pages = 0
    while url and pages < 10:
        payload = _get(url, params={"is_variable": "true"})
        for product in payload["results"]:
            code = product["code"]
            available_from = (product.get("available_from") or "")[:10]
            if code.startswith("AGILE-") and "OUTGOING" not in code and available_from and available_from <= today:
                candidates.append((available_from, code))
        url = payload.get("next")
        pages += 1
    if not candidates:
        raise RuntimeError("Could not find a current Agile product.")
    candidates.sort()
    return candidates[-1][1]


def fetch_price_history(days: int = DAYS, region: str = REGION) -> pd.DataFrame:
    """Past Agile unit rates (p/kWh) for the last `days` days, paged."""
    product = find_current_agile_product()
    tariff_code = f"E-1R-{product}-{region}"
    end = dt.datetime.now(dt.timezone.utc)
    start = end - dt.timedelta(days=days)

    rows: list[dict] = []
    url: str | None = f"{OCTO_BASE}/products/{product}/electricity-tariffs/{tariff_code}/standard-unit-rates/"
    params: dict | None = {
        "period_from": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "period_to": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "page_size": 1500,
    }
    pages = 0
    while url and pages < 60:
        payload = _get(url, params=params)
        for slot in payload["results"]:
            rows.append({"timestamp_utc": slot["valid_from"], "price_p_kwh": slot["value_inc_vat"]})
        url = payload.get("next")
        params = None  # the "next" URL already carries the query
        pages += 1

    df = pd.DataFrame(rows)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df.drop_duplicates("timestamp_utc").sort_values("timestamp_utc").reset_index(drop=True)


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Downloading ~{DAYS} days of history for {GSP_REGIONS[REGION]} ({REGION})...")
    carbon = fetch_carbon_history()
    print(f"  carbon: {len(carbon)} half-hours")
    prices = fetch_price_history()
    print(f"  price:  {len(prices)} half-hours")

    history = pd.merge(carbon, prices, on="timestamp_utc", how="inner").sort_values("timestamp_utc")
    history["region"] = GSP_REGIONS[REGION]
    history["data_type"] = "historical_actual"  # real past data — the training set
    history.to_csv(PROCESSED_DIR / "history.csv", index=False)

    print(f"\nCombined history: {len(history)} half-hourly rows with BOTH price and carbon")
    span = history["timestamp_utc"]
    print(f"  from {span.min()}  to  {span.max()}")
    print(history.head(4).to_string(index=False))
    print(f"\nSaved to: {PROCESSED_DIR / 'history.csv'}")


if __name__ == "__main__":
    main()
