"""
Tests for the WattWise optimiser. Run with:  pytest -q
These prove the schedule obeys deadlines and the £/CO2 maths is correct.
"""
import pandas as pd

from backend.optimisation.scheduler import (
    Appliance, cost_of_run, schedule_appliance, run_at_fixed_hour,
)


def _toy_day():
    """A 24-hour day (48 half-hour slots). Cheap+green at night, dear+dirty at 6pm."""
    rows = []
    for i in range(48):
        hour = i * 0.5
        price = 30 + 25 * (1 if 16 <= hour < 19 else 0)   # spike 16:00-19:00
        carbon = 200 if 16 <= hour < 19 else 100
        rows.append({"hour": hour, "price_p_kwh": price, "carbon_intensity": carbon})
    return pd.DataFrame(rows)


def test_duration_rounds_up():
    a = Appliance("EV", energy_kwh=10, power_kw=7, earliest_hour=0, deadline_hour=7)
    # 10 kWh / (7 kW * 0.5 h) = 2.857 -> 3 slots
    assert a.duration_slots == 3


def test_cost_maths():
    slots = pd.DataFrame({"price_p_kwh": [20.0, 40.0], "carbon_intensity": [100.0, 200.0]})
    # power 2 kW -> 1 kWh per half-hour slot
    out = cost_of_run(slots, power_kw=2.0)
    assert out["pounds"] == round((20 * 1 + 40 * 1) / 100, 3)   # £0.60
    assert out["kg_co2"] == round((100 * 1 + 200 * 1) / 1000, 3)  # 0.30 kg


def test_cheapest_avoids_peak():
    day = _toy_day()
    dishwasher = Appliance("Dishwasher", energy_kwh=1.2, power_kw=0.6,
                           earliest_hour=0, deadline_hour=24)
    plan = schedule_appliance(day, dishwasher, lam=1.0)  # cheapest
    # it must NOT overlap the 16:00-19:00 price spike
    assert not (16 <= plan["start_hour"] < 19)


def test_respects_deadline():
    day = _toy_day()
    ev = Appliance("EV", energy_kwh=10, power_kw=7, earliest_hour=0, deadline_hour=7)
    plan = schedule_appliance(day, ev, lam=0.5)
    assert plan["end_hour"] <= 7  # finished by the 7am deadline


def test_optimiser_beats_peak_baseline():
    day = _toy_day()
    wm = Appliance("Washing machine", energy_kwh=0.8, power_kw=0.8,
                   earliest_hour=0, deadline_hour=24)
    smart = schedule_appliance(day, wm, lam=1.0)
    peak = run_at_fixed_hour(day, wm, start_hour=17.0)
    assert smart["pounds"] <= peak["pounds"]
