"""
WattWise — the optimiser (Phase 4)
==================================

This is the heart of WattWise. Given:
  - a day of half-hourly slots, each with a price (p/kWh) and carbon (gCO2/kWh), and
  - a list of flexible appliances (energy needed, power, and a deadline),
it works out the BEST half-hours to run each appliance.

"Best" is a dial the user controls:
  lam = 1.0  -> only care about money (cheapest)
  lam = 0.0  -> only care about carbon (greenest)
  lam = 0.5  -> balance the two

How it works (simple + honest):
  Each appliance needs a run of N contiguous half-hours inside its allowed window.
  We slide that run across every feasible start time, score each option, and keep
  the cheapest/greenest. This IS an optimisation — we minimise an objective over
  all feasible schedules — just a transparent one. (The constraint-solver upgrade,
  OR-Tools/PuLP, is needed later when appliances share a power limit or can be
  paused and resumed; noted as future work.)

Everything here is explainable in an interview, which matters more than being fancy.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

SLOT_HOURS = 0.5  # each slot is half an hour


@dataclass
class Appliance:
    """A flexible load. Energy in kWh, power in kW, window as local hours (0-24)."""
    name: str
    energy_kwh: float
    power_kw: float
    earliest_hour: float   # earliest it may start
    deadline_hour: float   # must be finished by this hour

    @property
    def duration_slots(self) -> int:
        """How many half-hour slots the run needs (rounded up)."""
        return max(1, math.ceil(self.energy_kwh / (self.power_kw * SLOT_HOURS)))


def _normalise(series: pd.Series) -> pd.Series:
    """Scale to 0..1 so price and carbon can be compared on one scale."""
    lo, hi = series.min(), series.max()
    if hi == lo:
        return series * 0.0
    return (series - lo) / (hi - lo)


def cost_of_run(slots: pd.DataFrame, power_kw: float) -> dict:
    """£ and kgCO2 for running at `power_kw` across the given slots."""
    energy_per_slot = power_kw * SLOT_HOURS  # kWh in each half hour
    pounds = (slots["price_p_kwh"] * energy_per_slot).sum() / 100.0        # pence -> £
    kg_co2 = (slots["carbon_intensity"] * energy_per_slot).sum() / 1000.0  # g -> kg
    return {"pounds": round(pounds, 3), "kg_co2": round(kg_co2, 3)}


def schedule_appliance(day: pd.DataFrame, appliance: Appliance, lam: float = 0.5) -> dict:
    """Pick the best contiguous run for one appliance.

    `day` must have columns: hour, price_p_kwh, carbon_intensity (one row per slot,
    in time order). `lam` is the cost-vs-carbon dial (1=cheapest, 0=greenest).
    """
    d = day.reset_index(drop=True).copy()
    d["score"] = lam * _normalise(d["price_p_kwh"]) + (1 - lam) * _normalise(d["carbon_intensity"])

    n = appliance.duration_slots
    best = None
    for start in range(0, len(d) - n + 1):
        run = d.iloc[start:start + n]
        # feasible only if every slot in the run is inside the appliance's window
        if run["hour"].min() < appliance.earliest_hour:
            continue
        if run["hour"].max() >= appliance.deadline_hour:
            continue
        total_score = run["score"].sum()
        if best is None or total_score < best["total_score"]:
            best = {"start": start, "run": run, "total_score": total_score}

    if best is None:
        raise ValueError(f"No feasible slot for {appliance.name} in its window "
                         f"({appliance.earliest_hour:.0f}:00-{appliance.deadline_hour:.0f}:00).")

    run = best["run"]
    money = cost_of_run(run, appliance.power_kw)
    return {
        "appliance": appliance.name,
        "start_hour": float(run["hour"].iloc[0]),
        "end_hour": float(run["hour"].iloc[-1] + SLOT_HOURS),
        "slots": n,
        "pounds": money["pounds"],
        "kg_co2": money["kg_co2"],
    }


def run_at_fixed_hour(day: pd.DataFrame, appliance: Appliance, start_hour: float) -> dict:
    """Baseline: run the appliance starting at a fixed hour (e.g. 18:00 peak)."""
    d = day.reset_index(drop=True)
    start = int((d["hour"] - start_hour).abs().idxmin())
    n = appliance.duration_slots
    run = d.iloc[start:start + n]
    money = cost_of_run(run, appliance.power_kw)
    return {"appliance": appliance.name, "start_hour": start_hour,
            "pounds": money["pounds"], "kg_co2": money["kg_co2"]}
