"""
WattWise — Octopus Agile price ingestion
=========================================

Pulls real UK half-hourly electricity prices from the Octopus Energy API
(free, public tariff data — no account or API key needed) and saves them to
backend/data/raw/octopus_agile_prices.csv.

Octopus "Agile" is a tariff where the price changes every half hour and is
published a day ahead, tracking the wholesale market. That half-hourly price is
exactly the "cost signal" WattWise needs — the twin of the carbon signal we
already pull in carbon.py.

Why it's a little more involved than carbon.py:
  Octopus renames the Agile product every so often (AGILE-24-10-01, etc.), so we
  must *discover* the current product at runtime instead of hard-coding it — then
  build the regional tariff code and ask for its half-hourly rates.

The three steps:
  1. List products, find the newest live AGILE import product.
  2. Build the tariff code for your region:  E-1R-{product}-{region letter}.
  3. Get its half-hourly unit rates (p/kWh, incl. VAT) for the next 48 hours.

API docs: https://developer.octopus.energy/

Run it:
    python backend/ingestion/octopus.py
"""
from __future__ import annotations

import datetime as dt
from pathlib import Path

import pandas as pd
import requests

BASE = "https://api.octopus.energy/v1"

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"

# UK Grid Supply Point (GSP) region letters. Manchester = North West England = "G".
GSP_REGIONS = {
    "A": "East England", "B": "East Midlands", "C": "London",
    "D": "North Wales & Merseyside", "E": "West Midlands", "F": "North East England",
    "G": "North West England", "H": "Southern England", "J": "South East England",
    "K": "South Wales", "L": "South West England", "M": "Yorkshire",
    "N": "South Scotland", "P": "North Scotland",
}

# >>> Change this one letter if you want a different region. <<<
REGION = "G"  # North West England (Manchester)


def _get(url: str, params: dict | None = None) -> dict:
    """GET an Octopus endpoint and return parsed JSON, with a clear error on failure."""
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()
    return response.json()


def find_current_agile_product() -> str:
    """Find the newest Agile import product code (e.g. 'AGILE-24-10-01').

    We page through the products list, keep every code starting with 'AGILE-',
    and return the one with the latest 'available_from' date that has already
    started. This way we never hard-code a product that Octopus later retires.
    """
    today = dt.date.today().isoformat()
    candidates: list[tuple[str, str]] = []  # (available_from, code)

    url: str | None = f"{BASE}/products/"
    pages = 0
    while url and pages < 10:
        payload = _get(url, params={"is_variable": "true"})
        for product in payload["results"]:
            code = product["code"]
            available_from = (product.get("available_from") or "")[:10]
            # Agile import products only; skip Agile Outgoing (export) and future-only products.
            if code.startswith("AGILE-") and "OUTGOING" not in code:
                if available_from and available_from <= today:
                    candidates.append((available_from, code))
        url = payload.get("next")  # the API hands us the next page URL, or None
        pages += 1

    if not candidates:
        raise RuntimeError("Could not find a current Agile product — check the API is reachable.")

    candidates.sort()  # by available_from, oldest first
    return candidates[-1][1]  # newest live product


def fetch_agile_prices(region: str = REGION) -> pd.DataFrame:
    """Next 48 hours of half-hourly Agile prices (p/kWh, incl. VAT) for one region."""
    product = find_current_agile_product()
    tariff_code = f"E-1R-{product}-{region}"  # E-1R = single-rate electricity import

    now = dt.datetime.now(dt.timezone.utc)
    url = f"{BASE}/products/{product}/electricity-tariffs/{tariff_code}/standard-unit-rates/"
    payload = _get(
        url,
        params={
            "period_from": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "period_to": (now + dt.timedelta(hours=48)).strftime("%Y-%m-%dT%H:%M:%SZ"),
        },
    )

    rows = []
    for slot in payload["results"]:
        rows.append(
            {
                "timestamp_utc": slot["valid_from"],
                "price_p_kwh": slot["value_inc_vat"],  # pence per kWh, incl. VAT
                "region": GSP_REGIONS.get(region, region),
                "region_code": region,
                "product": product,
                "data_source": "Octopus Agile API",
                "data_type": "published_tariff",  # real published prices, not our own forecast
            }
        )

    df = pd.DataFrame(rows)
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True)
    return df.sort_values("timestamp_utc").reset_index(drop=True)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    prices = fetch_agile_prices()
    prices.to_csv(RAW_DIR / "octopus_agile_prices.csv", index=False)

    product = prices["product"].iloc[0]
    region_name = prices["region"].iloc[0]
    print(f"Agile product: {product}  ·  region: {region_name} ({REGION})")
    print(f"Prices retrieved: {len(prices)} half-hourly periods (next 48h)\n")
    print(prices[["timestamp_utc", "price_p_kwh", "data_type"]].head(6).to_string(index=False))

    cheapest = prices.loc[prices["price_p_kwh"].idxmin()]
    dearest = prices.loc[prices["price_p_kwh"].idxmax()]
    print(f"\nCheapest slot: {cheapest['price_p_kwh']:.2f} p/kWh at {cheapest['timestamp_utc']}")
    print(f"Dearest slot:  {dearest['price_p_kwh']:.2f} p/kWh at {dearest['timestamp_utc']}")
    print(f"\nSaved CSV to: {RAW_DIR}")


if __name__ == "__main__":
    main()
