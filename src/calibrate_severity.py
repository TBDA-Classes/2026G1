"""
Calibrate the severity thresholds (backlog F5.2, KAN-152, KAN-203) on the real detector output (EXP-12).

Input : reports/anomaly_events.csv   (notebook 03, one row per event with eur_all_in and hours)
Output: reports/severity_calibration.csv   every candidate pair of EUR thresholds with its counts and EUR shares
        reports/severity_calibration.json  chosen thresholds, the result, and the old kWh rule for comparison
        reports/figures/sev_01_calibration.png

Rule (a workload rule, written down before looking at the result):
  * high   = the alerts the building manager handles first: about the top 20 % of alerts (one in five),
             so the EUR threshold is the round value whose high share is closest to 20 %;
  * low    = alerts that are only logged: about the cheapest half, so the threshold whose low share is closest to 50 %;
  * events that last >= long_event_hours (24 h) go up one level (backlog F5.2: "based on EUR and duration").
The thresholds are searched on a short grid of round EUR values, so the result is easy to explain and to change.

Usage:  python src/calibrate_severity.py            (from the repository root)
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from src.anomalies import LEVELS, load_params, severity  # noqa: E402

GRID = [0.10, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00, 5.00]
TARGET_HIGH, TARGET_LOW = 0.20, 0.50


def apply_rule(events: pd.DataFrame, eur_cuts, long_hours: int, col: str = "eur_all_in") -> pd.Series:
    S = {"eur": list(eur_cuts), "long_event_hours": long_hours}
    return pd.Series([severity(e, h, S) for e, h in zip(events[col], events["hours"])], index=events.index)


def summary(events: pd.DataFrame, sev: pd.Series, weeks: float, col: str = "eur_all_in") -> dict:
    eur = events[col]
    out = {}
    for s in LEVELS:
        m = sev == s
        out[s] = {"alerts": int(m.sum()), "share_of_alerts": round(float(m.mean()), 3),
                  "per_week": round(float(m.sum() / weeks), 2), "share_of_eur": round(float(eur[m].sum() / eur.sum()), 3)}
    return out


def grid_table(events: pd.DataFrame, long_hours: int, weeks: float, col: str = "eur_all_in") -> pd.DataFrame:
    rows = []
    for lo in GRID:
        for hi in GRID:
            if hi <= lo:
                continue
            s = summary(events, apply_rule(events, (lo, hi), long_hours, col), weeks, col)
            rows.append({"eur_low_medium": lo, "eur_medium_high": hi,
                         **{f"{lvl}_{k}": v for lvl in LEVELS for k, v in s[lvl].items()}})
    return pd.DataFrame(rows)


def choose(table: pd.DataFrame) -> tuple:
    """Low/medium cut: low share closest to 50 %. Then medium/high cut: high share closest to 20 %."""
    lo = table.loc[(table["low_share_of_alerts"] - TARGET_LOW).abs().idxmin(), "eur_low_medium"]
    sub = table[table["eur_low_medium"] == lo]
    hi = sub.loc[(sub["high_share_of_alerts"] - TARGET_HIGH).abs().idxmin(), "eur_medium_high"]
    return float(lo), float(hi)


def main():
    P = load_params()
    S = P["severity"]
    col, long_h = S["eur_column"], S["long_event_hours"]
    rep = ROOT / "reports"
    ev = pd.read_csv(rep / "anomaly_events.csv", parse_dates=["start", "end"])

    from src.data import load                          # same history length as notebook 03 (lockdown dropped)
    weeks = len(load()) / 168

    table = grid_table(ev, long_h, weeks, col)
    table.to_csv(rep / "severity_calibration.csv", index=False)
    lo, hi = choose(table)

    new = apply_rule(ev, (lo, hi), long_h, col)
    no_duration = apply_rule(ev, (lo, hi), 10**9, col)
    old_kwh = pd.Series(np.where(ev["excess_kWh"] < 2, "low", np.where(ev["excess_kWh"] <= 10, "medium", "high")),
                        index=ev.index)                # the previous rule (params.yaml before EXP-12)
    top10 = ev.assign(severity=new).sort_values(col, ascending=False).head(10)
    res = {
        "events": len(ev), "weeks_of_history": round(weeks, 1), "eur_column": col,
        "chosen": {"eur": [lo, hi], "long_event_hours": long_h},
        "params_yaml_matches": [lo, hi] == [float(x) for x in S["eur"]],
        "result": summary(ev, new, weeks, col),
        "raised_by_duration_rule": int((new != no_duration).sum()),
        "previous_kwh_rule": summary(ev, old_kwh, weeks, col),
        "high_in_2025": int(((ev["start"] >= "2025-01-01") & (new == "high")).sum()),
        "top10_by_eur": top10[["circuit", "start", "hours", "excess_kWh", col, "severity"]]
                        .assign(start=lambda d: d["start"].astype(str)).round(2).to_dict("records"),
    }
    (rep / "severity_calibration.json").write_text(json.dumps(res, indent=2))
    figure(ev, new, old_kwh, col, rep / "figures" / "sev_01_calibration.png")
    print(json.dumps({k: v for k, v in res.items() if k != "top10_by_eur"}, indent=2))
    if not res["params_yaml_matches"]:
        print(f"\n!! params.yaml has eur = {S['eur']}; the calibration chose {[lo, hi]}. Update params.yaml.")


def figure(ev, new, old, col, path):
    import matplotlib.pyplot as plt
    order = ev[col].sort_values(ascending=False)
    cum = order.cumsum() / order.sum()
    x = np.arange(1, len(order) + 1) / len(order)
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(100 * x, 100 * cum.values, color="black", lw=1.5, label="all alerts, most expensive first")
    for name, sev, c in [("€ + duration rule (new)", new, "#c0392b"), ("kWh rule (previous)", old, "#7f8c8d")]:
        m = sev == "high"
        ax.scatter(100 * m.mean(), 100 * ev.loc[m, col].sum() / ev[col].sum(), s=70, color=c, zorder=5,
                   label=f"{name}: high = {100 * m.mean():.0f} % of alerts, {100 * ev.loc[m, col].sum() / ev[col].sum():.0f} % of €")
    ax.set_xlabel("% of alerts handled"); ax.set_ylabel("% of € at stake covered")
    ax.set_title("Which alerts to handle first? Severity calibration (EXP-12)")
    ax.grid(alpha=0.3); ax.legend(fontsize=8, loc="lower right")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    fig.savefig(path, dpi=110, bbox_inches="tight")


if __name__ == "__main__":
    main()
