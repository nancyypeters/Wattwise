"""
WattWise — Octopus Agile price ingestion  (NEXT MILESTONE — build together)
===========================================================================

This is a documented skeleton, NOT finished code. We'll implement and test it
together after carbon.py is working, because the Agile product code changes over
time and must be discovered at runtime — never hard-coded (a lesson from the spec).

The correct approach (to implement next):
  1. GET {BASE}/products/?is_variable=true  -> find the current AGILE product code.
  2. Pick the user's region letter (GSP group, "A".."P"; London = "C").
  3. Build the tariff code  E-1R-{product_code}-{region}  and GET its
     .../standard-unit-rates/  to retrieve half-hourly prices (p/kWh, inc. VAT).
  4. Return a tidy DataFrame with the SAME shape as carbon.py:
       timestamp_utc, price_p_kwh, region, data_source, data_type

API docs: https://developer.octopus.energy/   (public tariff data — no account needed)
"""
from __future__ import annotations

BASE = "https://api.octopus.energy/v1"

# UK Grid Supply Point (GSP) region letters -> human name. Confirm the user's region.
GSP_REGIONS = {
    "A": "East England", "B": "East Midlands", "C": "London", "D": "North Wales & Mersey",
    "E": "West Midlands", "F": "North East", "G": "North West", "H": "South England",
    "J": "South East", "K": "South Wales", "L": "South West", "M": "Yorkshire",
    "N": "South Scotland", "P": "North Scotland",
}


def fetch_agile_prices(region: str = "C"):
    """TODO (next milestone): implement steps 1–4 above and return a DataFrame."""
    raise NotImplementedError("We'll build and test this together after carbon.py runs.")


if __name__ == "__main__":
    print("octopus.py is a skeleton — run carbon.py first, then we build this next.")
