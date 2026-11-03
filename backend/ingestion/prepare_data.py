"""
WattWise — combine price + carbon into one tidy dataset
=======================================================

Takes the two raw files we just downloaded:
  - carbon_national_forecast.csv   (next 48h of GB carbon intensity)
  - octopus_agile_prices.csv       (published half-hourly prices for your region)

...and lines them up on the SAME half-hourly timestamps, saving one combined file:
  backend/data/processed/energy_data.csv

This is the file every later part of WattWise reads from — the charts, the
forecasting, the optimiser. One clean source of truth.

A key honesty point baked in:
  Carbon is published for the full next 48h, but Octopus only publishes prices
  up to ~11pm tonight. So later rows have carbon but NO price yet. We keep those
  rows and mark them 'awaiting_publish' instead of throwing them away — that gap
  is exactly what the forecasting model will fill in Phase 3.

Everything is stored in UTC (both APIs return UTC). We convert to UK local time
only when we display charts later, so British Summer Time never corrupts stored data.

Run it (after carbon.py and octopus.py):
    python backend/ingestion/prepare_data.py
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"
PROCESSED_DIR = Path(__file__).resolve().parents[1] / "data" / "processed"


def load_combined() -> pd.DataFrame:
    """Merge carbon + price on their half-hourly timestamps."""
    carbon = pd.read_csv(RAW_DIR / "carbon_national_forecast.csv", parse_dates=["timestamp_utc"])
    prices = pd.read_csv(RAW_DIR / "octopus_agile_prices.csv", parse_dates=["timestamp_utc"])

    carbon = carbon.rename(columns={"index": "carbon_index"})

    # Outer merge: keep the FULL 48h carbon horizon, attach price where it exists.
    merged = pd.merge(
        carbon[["timestamp_utc", "carbon_intensity", "carbon_index"]],
        prices[["timestamp_utc", "price_p_kwh", "region"]],
        on="timestamp_utc",
        how="outer",
    ).sort_values("timestamp_utc").reset_index(drop=True)

    # Fill the region label down (carbon is national, so it has no region of its own).
    region_name = prices["region"].iloc[0] if len(prices) else "unknown"
    merged["region"] = region_name

    # Honest status label for each row.
    merged["price_status"] = merged["price_p_kwh"].apply(
        lambda v: "published" if pd.notna(v) else "awaiting_publish"
    )

    merged["data_source"] = "Octopus Agile API + NESO Carbon Intensity API"
    merged["data_type"] = "published"  # real published data — NOT a model output, NOT simulated

    return merged[
        [
            "timestamp_utc",
            "price_p_kwh",
            "carbon_intensity",
            "carbon_index",
            "region",
            "price_status",
            "data_source",
            "data_type",
        ]
    ]


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    df = load_combined()
    df.to_csv(PROCESSED_DIR / "energy_data.csv", index=False)

    n_total = len(df)
    n_priced = int(df["price_p_kwh"].notna().sum())
    print(f"Combined dataset: {n_total} half-hourly rows (next 48h of carbon)")
    print(f"  · {n_priced} rows have a published price")
    print(f"  · {n_total - n_priced} rows are awaiting price publication (forecasting fills these)\n")
    print(df.head(6).to_string(index=False))

    both = df.dropna(subset=["price_p_kwh"])
    if len(both):
        print("\nWhere we have BOTH signals right now:")
        print(f"  cheapest price : {both['price_p_kwh'].min():.2f} p/kWh")
        print(f"  dearest price  : {both['price_p_kwh'].max():.2f} p/kWh")
        print(f"  carbon range   : {both['carbon_intensity'].min():.0f}–{both['carbon_intensity'].max():.0f} gCO2/kWh")
    print(f"\nSaved combined file to: {PROCESSED_DIR / 'energy_data.csv'}")


if __name__ == "__main__":
    main()
