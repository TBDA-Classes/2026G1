"""
TBDA Group 1 - Storey 1: final table of every zone (NE, NW, SE, SW) = cleaned building data + weather + calendar + price + CO2.

Reads   data/zones/hourly_<Z>.parquet            (from clean_zones.py)
        data/zones/hourly_<Z>_reasons.parquet    (why each empty cell is empty)
        data/external/external_hourly.parquet    (weather Open-Meteo, price OMIE, CO2 ESIOS, public holidays: already downloaded)
Writes  data/final/zone_<Z>_hourly.parquet       the table (wide: ONE ROW PER HOUR, one column per circuit / sensor)
        data/final/zone_<Z>_empty_reasons.parquet  same rows, one column per measurement: the reason code of each empty cell
        data/final/zone_<Z>_hourly.xlsx          for people without Python: sheets DATA, COLUMNS, WARNINGS, REASON_CODES, CLEANING_LOG

EMPTY CELL = missing or discarded value. It is NOT zero. Nothing was invented.
In the Excel file every empty cell is coloured with the colour of its reason (see sheet REASON_CODES);
the column `empty_reasons` writes the reasons of the row in words.

Run (project root):   py src/build_zone_files.py      (needs openpyxl:  py -m pip install openpyxl)
"""
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
ZDIR, EXT = ROOT / "data" / "zones", ROOT / "data" / "external" / "external_hourly.parquet"
FINAL = ROOT / "data" / "final"
FINAL.mkdir(parents=True, exist_ok=True)
ZONES = ["NE", "NW", "SE", "SW"]
ZONE_NAME = {"NE": "North-East", "NW": "North-West", "SE": "South-East", "SW": "South-West"}

CAL_COLS = ["is_working_day", "is_weekend", "is_holiday", "holiday_name", "is_christmas_break", "is_holy_week",
            "is_august_closure", "is_covid_lockdown"]
WX_COLS = ["wx_temp_c", "wx_feels_like_c", "wx_humidity_pct", "wx_precip_mm", "wx_cloud_pct", "wx_wind_ms",
           "wx_solar_wm2", "wx_pressure_hpa"]

# ---------------------------------------------------------------- reason codes (text and Excel colour)
REASONS = {
    "NO_DATA": ("D9D9D9", "No value for this hour in the original file for this circuit/sensor only (the other circuits of the zone have data)."),
    "NO_DATA_ZONE": ("BFBFBF", "No value for this hour in ANY circuit of the zone: the whole zone was not logged (acquisition outage, data logger or network). Nothing to recover."),
    "R6_NEG": ("F4B6B6", "Value below -10 W: impossible for a consumer, not meter noise. Discarded."),
    "R7_STUCK": ("F8CBAD", "Same non-zero value for 6+ hours in a row (period A): stuck sensor. Discarded."),
    "R8_ZERO_RUN": ("FFE699", "Exact 0 for 6+ hours where the circuit normally uses more than 1 W at that weekday and hour: the sensor stopped sending, it is not real consumption. Discarded."),
    "X1_LEVEL_DROP": ("D9C3E8", "NW Emerg. Lighting below 3 W after the sign flip: the level jumps to about 0 W for weeks (Dec 2021, Feb-Apr 2022), probably work on the measuring system. Discarded."),
    "R9_ENV_ZEROS": ("BDD7EE", "Light, humidity and temperature all read 0 at the same time: the environment sensor was not reporting. Discarded."),
    "R10_TEMP_RANGE": ("F7C6E1", "Indoor temperature outside 0-45 C (SW sensor 739-1,411 C on 1-7 Mar 2022): sensor fault, so temperature, humidity, light and presence of that hour are discarded."),
    "TOTAL_INCOMPLETE": ("EDEDED", "The zone total is only computed when ALL circuits of the zone have a value in that hour; at least one is empty (see the other columns of the row)."),
}

# ---------------------------------------------------------------- column dictionary
SRC_B, SRC_W, SRC_C, SRC_P = "building (cleaned)", "weather (Open-Meteo)", "calendar", "price (OMIE) / CO2 (ESIOS)"
FIXED = {
    "timestamp_utc": (SRC_B, "Hour of the measurement. Assumed UTC (to be confirmed with the professor)."),
    "Regime": (SRC_B, "A = 2020-04..2023-02, one reading per hour. B = 2025-08..2025-10, average of per-minute readings."),
    "timestamp_local": (SRC_B, "Same hour in Madrid local time (summer/winter time included)."),
    "weekday_local": (SRC_B, "Day of the week in local time: 0 = Monday ... 6 = Sunday."),
    "hour_local": (SRC_B, "Hour of the day in local time (0-23)."),
    "month": (SRC_B, "Month number in local time (1-12)."),
    "low_coverage": (SRC_B, "TRUE when the hour was built from fewer than 30 per-minute readings in at least one circuit of the zone (period B only)."),
    "ZONE TOTAL W": (SRC_B, "Sum of all the circuits of the zone (W). Empty unless ALL circuits of the zone have a value in that hour (to keep only complete hours, filter on non-empty)."),
    "wx_temp_c": (SRC_W, "Outdoor air temperature, deg C."),
    "wx_feels_like_c": (SRC_W, "Apparent ('feels like') temperature, deg C."),
    "wx_humidity_pct": (SRC_W, "Outdoor relative humidity, %."),
    "wx_precip_mm": (SRC_W, "Precipitation in the previous hour, mm."),
    "wx_cloud_pct": (SRC_W, "Cloud cover, %."),
    "wx_wind_ms": (SRC_W, "Wind speed at 10 m, m/s."),
    "wx_solar_wm2": (SRC_W, "Solar radiation on a horizontal surface, W/m2."),
    "wx_pressure_hpa": (SRC_W, "Surface air pressure, hPa."),
    "is_working_day": (SRC_C, "MAIN open/closed column. TRUE = normal working day: NOT weekend, NOT holiday, NOT Christmas break, NOT Holy Week, NOT August closure (provisional, see is_august_closure), NOT COVID lockdown."),
    "is_weekend": (SRC_C, "TRUE on Saturday and Sunday (local time)."),
    "is_holiday": (SRC_C, "TRUE on national, Madrid-region and Madrid-city public holidays and on the UPM non-teaching day (28 Jan, Santo Tomas)."),
    "holiday_name": (SRC_C, "Name of the holiday, when there is one."),
    "is_christmas_break": (SRC_C, "TRUE from 23 Dec to 6 Jan (both included). Follows the UPM staff (PAS) calendar and the UPM academic calendars (Christmas break starts on 23 Dec)."),
    "is_holy_week": (SRC_C, "TRUE from Monday to Sunday of Holy Week. Follows the UPM STAFF (PAS) calendar, where the whole week is non-working (the students' calendar can differ by a day or two)."),
    "is_august_closure": (SRC_C, "TRUE for the whole of August. PROVISIONAL: UPM centres may close about two weeks in August; the exact dates of CeDInt are still to be confirmed with the professor. Until then the whole month is marked."),
    "is_covid_lockdown": (SRC_C, "TRUE until 2020-06-21 (end of the Spanish state of alarm): building practically closed."),
    "price_eur_mwh": (SRC_P, "Day-ahead electricity price of the Spanish market (OMIE), EUR/MWh. Every hour of the table has a real OMIE price (the monthly-average fallback of the download script was never needed: 0 hours)."),
    "co2_intensity_g_kwh": (SRC_P, "CO2 emitted per kWh of electricity generated in the Spanish peninsular grid, hourly average, g CO2/kWh (Red Electrica ESIOS indicator 10355). Every hour of the table has a real ESIOS value (the monthly-average fallback of the download script was never needed: 0 hours)."),
    "empty_reasons": ("cleaning", "Words: why the empty cells of this row are empty, grouped by reason code. ALL = every measurement column of the zone. See sheet REASON_CODES."),
}
ENV_TXT = {"ENV Hum %RH": "humidity, %RH", "ENV Lum lux": "light, lux", "ENV Pres share": "presence, share of readings (0-1)",
           "ENV Temp °C": "indoor temperature, deg C"}

# ---------------------------------------------------------------- reliability (rating + what to know), from the group's review
RELI = {
    ("NE", "HVAC W"): ("RELIABLE", "No problems found."),
    ("NE", "Plugs & Sockets W"): ("RELIABLE WITH CAUTION", "Normal load ~192 W, but it drops to ~25 W for about 94 days in 10 periods (e.g. 22/11-03/12/2020, 22/02-09/03/2021, 16/10-17/11/2022). Plausible, not verified: ask whether the load is really switched off. KEPT."),
    ("NW", "Emerg. Lighting W"): ("LOW RELIABILITY", "Reversed sign (97.7% negative): multiplied by -1 (to be confirmed by the group: flip or drop). About 0-2 W for whole hours in 2 periods (2/12-29/12/2021 and 25/02-04/04/2022) and a level that changes (16 W -> 8 W from 29/12/2021): values < 3 W are emptied (X1). Gaps of 887 h (May-Jun 2021) and ~550 h (Dec 2022-Jan 2023). Do not compare before/after Dec 2021."),
    ("NW", "HVAC W"): ("RELIABLE WHERE PRESENT", "Large gaps shared with Emerg. Lighting: 12/05-18/06/2021 (887 h) and 23/12/2022-19/01/2023 (~550 h)."),
    ("NW", "Hand Dryer W"): ("RELIABLE", "15,922 small negatives (noise) set to 0. Peaks up to 2.75 kW kept: they are real."),
    ("NW", "Lighting W"): ("RELIABLE", "Small negatives -> 0; 13 long zero runs emptied."),
    ("NW", "Plugs & Sockets W"): ("RELIABLE", "Peaks up to 8.25 kW (05/01/2023 14:00) over several consecutive hours: consistent, kept. Ask what happened in January 2023."),
    ("NW", "RACK W"): ("RELIABLE", "No problems found (NW RACK is kept and part of the NW total; SW RACK instead stops in Dec 2021 and was excluded)."),
    ("SE", "Emerg. Lighting W"): ("USE WITH CAUTION", "908 zeros in runs emptied; Emerg. and HVAC of SE are both at zero together for 2,100 hours: probably the SE panel was switched off/not read, not real consumption. Short zeros that cannot be classified remain."),
    ("SE", "HVAC W"): ("USE WITH CAUTION", "886 zeros in runs emptied (same cause as Emerg. Lighting)."),
    ("SE", "Lighting W"): ("RELIABLE", "Zero is normal (light off). 4 values below -10 W emptied. When the value is zero, 'off' cannot be told apart from 'not read'."),
    ("SE", "Plugs & Sockets W"): ("USE WITH CAUTION", "1,130 zeros in runs emptied (runs up to 354 h). Peak of 4.78 kW on Sunday 04/12/2022 at 12:00-13:00, together with negative Lighting values: event to be checked."),
    ("SW", "Emerg. Lighting W"): ("RELIABLE", "Small negatives -> 0."),
    ("SW", "Hand Dryer W"): ("RELIABLE", "2,602 small negatives -> 0; peaks up to 3.3 kW kept."),
    ("SW", "Lighting W"): ("RELIABLE", "10,631 small negatives -> 0; 232 long zero runs emptied."),
    ("SW", "Plugs & Sockets W"): ("RELIABLE", "No problems found."),
    ("NW", "ENV Hum %RH"): ("RELIABLE", "Values 26-34%, no stuck runs."),
    ("NW", "ENV Lum lux"): ("RELIABLE", "Zero is normal (dark)."),
    ("NW", "ENV Pres share"): ("LOW RELIABILITY", "Presence = 1.0 with no interruption for 3+ days: 6,626 hours (up to 1,997 h = 83 days). Impossible for real presence. LEFT AS IT IS (documented only). Do not use presence to reason about office hours."),
    ("NW", "ENV Temp °C"): ("RELIABLE", "OK."),
    ("SE", "ENV Hum %RH"): ("USE WITH CAUTION", "7,194 hours (28%) in runs with the same value for 3+ days: low-sensitivity or stuck sensor. LEFT AS IT IS (documented only)."),
    ("SE", "ENV Lum lux"): ("RELIABLE", "Zero is normal (dark)."),
    ("SE", "ENV Pres share"): ("LOW RELIABILITY", "Presence = 1.0 stuck for 9,165 hours (up to 1,444 h). LEFT AS IT IS (documented only). Do not use presence to reason about office hours."),
    ("SE", "ENV Temp °C"): ("RELIABLE", "OK."),
    ("SW", "ENV Hum %RH"): ("LOW RELIABILITY", "18,962 hours (74%) in runs with the same value for 3+ days (up to 1,703 h = 71 days). LEFT AS IT IS (documented only): unusable as a time series."),
    ("SW", "ENV Lum lux"): ("RELIABLE", "Peak of 11,027 lux plausible (sunlight). 140 hours emptied (1-7 Mar 2022, faulty temperature)."),
    ("SW", "ENV Pres share"): ("USE WITH CAUTION", "Presence = 1.0 stuck for 1,642 hours. LEFT AS IT IS (documented only). 140 hours emptied (1-7 Mar 2022)."),
    ("SW", "ENV Temp °C"): ("RELIABLE", "140 impossible hours (739-1,411 degrees, 01-07/03/2022) emptied together with humidity, light and presence."),
}

LEFT_OUT = {
    "SE": "SE Projector: always 0 (24,934 values), circuit that does not measure. Left out of the zone files and of the zone total.",
    "SW": "SW RACK: stops on 03/12/2021 17:00, then no data (13,792 empty hours). Left out of the zone files and of the zone total.",
}

WARN_GENERAL = [
    ("Time zone", "The timestamps of the original files carry no time zone. They behave like UTC (no daylight-saving jump), so they were treated as UTC and Madrid local time was added. NOT confirmed by the professor: if they are not UTC, timestamp_local, weekday_local, hour_local, month and all calendar columns are shifted."),
    ("Two different periods", "Period A (2020-04..2023-02): ONE instantaneous reading per hour, so short peaks can be missed. Period B (2025-08..2025-10): average of up to ~51 readings per hour. Do not mix A and B without saying so. Column Regime tells which is which."),
    ("901-day gap", "No rows from 01/03/2023 to 18/08/2025. The grid of the table is the same for the 4 zones (26,830 hours); the hours of the gap are NOT in the table. A whole annual cycle (Mar-Aug) is missing, so 2020-23 and 2025 cover different months."),
    ("Empty cell", "Empty = missing or discarded. It is NOT zero. Every empty cell has a reason code (sheet REASON_CODES, column empty_reasons, cell colour in Excel)."),
    ("Small negatives set to 0", "Rule R5: values between -10 W and 0 W (typically -0.1 to -2 W) are meter noise around zero and were set to 0 W. These zeros are NOT marked cell by cell. Counts per circuit are in CLEANING_LOG. Zero is also a real value (light off, hand dryer idle): a 0 can be a real 0, a rounded noise value, or (before cleaning) a stopped sensor, which is emptied instead when the zeros last 6+ hours (reason R8_ZERO_RUN)."),
    ("TRUE/FALSE in this Excel file", "TRUE/FALSE columns are written as text so they look the same in any language of Excel (otherwise an Italian Excel shows VERO/FALSO). In the Parquet files they are real booleans."),
    ("low_coverage", "Period B hours built from fewer than 30 per-minute readings in at least one circuit of the zone. The value is kept (not removed), the flag only warns."),
    ("Not done on purpose", "No interpolation, no filling of gaps, spikes kept, energy counters (Ea, Er) not used. Price and CO2: no gap filling was needed (every hour has a real value)."),
    ("August closure", "is_august_closure marks the WHOLE month and is_working_day is FALSE in August. PROVISIONAL: the real closing days of CeDInt are to be confirmed (UPM centres may close about two weeks)."),
    ("Presence and humidity", "Presence = 1.0 stuck for days/weeks and humidity with the same value for days/weeks in some zones (see COLUMNS, 'reliability'). Left as they are: documented only."),
]
WARN_ZONE = {
    "NE": [("No environment sensor", "The NE zone has NO environment sensor (all original values are 0): the file has no ENV columns."),
           ("Plugs & Sockets", "Drops to ~25 W for about 94 days in 10 periods. Kept, to be confirmed.")],
    "NW": [("Emerg. Lighting", "Sign flipped (x -1) and values below 3 W emptied (reason X1_LEVEL_DROP). Open group decision: flip or drop the circuit."),
           ("Shared gaps", "NW Emerg. Lighting and NW HVAC have the same holes: 12/05-18/06/2021 (887 h), 23/12/2022-19/01/2023 (~550 h). The zone total is empty in those hours."),
           ("RACK", "NW RACK is reliable and is part of the NW total.")],
    "SE": [("Projector", LEFT_OUT["SE"]),
           ("Emerg. Lighting + HVAC", "Both at exact zero together for ~2,100 hours: probably the panel was not read. Emptied (reason R8_ZERO_RUN)."),
           ("Event", "04/12/2022: 4.78 kW on SE Plugs & Sockets (Sunday) together with negative Lighting values: to be checked.")],
    "SW": [("RACK", LEFT_OUT["SW"]),
           ("Temperature fault", "1-7 Mar 2022: temperature 739-1,411 C. 140 hours of temperature, humidity, light and presence emptied (reason R10_TEMP_RANGE)."),
           ("Humidity", "Same value for up to 71 days: unusable as a time series.")],
}


def calendar(df, ext):
    d = df["date_local"]
    cal = pd.DataFrame(index=df.index)
    cal["is_weekend"] = df["weekday_local"] >= 5
    cal["is_holiday"] = ext["is_holiday"].values
    cal["holiday_name"] = ext["holiday_name"].values
    cal["is_christmas_break"] = ((d.dt.month == 12) & (d.dt.day >= 23)) | ((d.dt.month == 1) & (d.dt.day <= 6))
    cal["is_holy_week"] = ext["is_holy_week"].values
    cal["is_august_closure"] = d.dt.month == 8
    cal["is_covid_lockdown"] = d <= pd.Timestamp("2020-06-21")
    closed = cal[["is_weekend", "is_holiday", "is_christmas_break", "is_holy_week", "is_august_closure", "is_covid_lockdown"]].any(axis=1)
    cal["is_working_day"] = ~closed
    return cal[CAL_COLS]


def reasons_text(why, cols):
    """One sentence per row: CODE[col, col]; CODE[...]  ('ALL' when the code covers every measurement column)."""
    out = []
    arr = why[cols].to_numpy(dtype=object)
    for row in arr:
        groups = {}
        for c, code in zip(cols, row):
            if isinstance(code, str):
                groups.setdefault(code, []).append(c)
        if not groups:
            out.append(None)
            continue
        parts = []
        for code, cs in groups.items():
            parts.append(f"{code}[{'ALL' if len(cs) == len(cols) else ', '.join(cs)}]")
        out.append("; ".join(parts))
    return out


def describe(col, zone):
    if col in FIXED:
        return FIXED[col]
    if col.startswith("ENV "):
        return (SRC_B, f"Environment sensor of the zone: {ENV_TXT[col]}. One sensor per zone.")
    if col.endswith(" W"):
        return (SRC_B, "Electric power of the circuit, average W in the hour (negative noise set to 0, impossible values empty).")
    return (SRC_B, "")


def write_excel(path, zone, df, why, log_zone):
    import openpyxl
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    df = df.copy()
    for c in df.columns:                                       # booleans as text: same look in every Excel language
        if df[c].dtype == bool:
            df[c] = df[c].map({True: "TRUE", False: "FALSE"})
    cols = list(df.columns)
    dict_rows = []
    for i, c in enumerate(cols, start=1):
        src, meaning = describe(c, zone)
        rating, note = RELI.get((zone, c), ("", ""))
        if c == "ZONE TOTAL W":
            rating, note = "DERIVED", "Reliability = that of its circuits; empty if any circuit of the zone is empty."
        dict_rows.append((i, c, src, meaning, rating, note))
    desc = pd.DataFrame(dict_rows, columns=["#", "column", "source", "meaning", "reliability", "what to know"])

    warn = pd.DataFrame(WARN_GENERAL + WARN_ZONE[zone], columns=["topic", "what to know"])
    meas = [c for c in why.columns]
    counts = why.stack().value_counts()
    rc = pd.DataFrame([(code, REASONS[code][1], int(counts.get(code, 0))) for code in REASONS],
                      columns=["code", "meaning", f"empty cells in zone {zone}"])
    rc.insert(1, "colour in DATA", "")
    lg = log_zone[["rule", "column", "values_affected", "detail"]].copy()
    lg.columns = ["rule", "column", "values affected", "what was done"]

    with pd.ExcelWriter(path, engine="openpyxl", datetime_format="yyyy-mm-dd hh:mm") as xw:
        df.to_excel(xw, sheet_name="DATA", index=False)
        desc.to_excel(xw, sheet_name="COLUMNS", index=False)
        warn.to_excel(xw, sheet_name="WARNINGS", index=False)
        rc.to_excel(xw, sheet_name="REASON_CODES", index=False)
        lg.to_excel(xw, sheet_name="CLEANING_LOG", index=False)
        ws = xw.sheets["DATA"]
        ws.freeze_panes = "B2"
        ws.auto_filter.ref = ws.dimensions
        for i, col in enumerate(cols, start=1):
            w = max(12, min(24, len(str(col)) + 2))
            if col == "empty_reasons":
                w = 60
            ws.column_dimensions[get_column_letter(i)].width = w
        # colour every empty cell with the colour of its reason
        pos = {c: i + 1 for i, c in enumerate(cols)}
        fills = {code: PatternFill("solid", fgColor=colr) for code, (colr, _) in REASONS.items()}
        for c in meas:
            j = pos[c]
            codes = why[c]
            for r in np.flatnonzero(codes.notna().to_numpy()):
                ws.cell(row=int(r) + 2, column=j).fill = fills[codes.iloc[r]]
        for name, widths in (("COLUMNS", (5, 28, 22, 90, 24, 110)), ("WARNINGS", (28, 150)),
                             ("REASON_CODES", (20, 14, 120, 22)), ("CLEANING_LOG", (8, 28, 16, 110))):
            w = xw.sheets[name]
            w.freeze_panes = "A2"
            for letter, wd in zip("ABCDEF", widths):
                w.column_dimensions[letter].width = wd
            for row in w.iter_rows(min_row=2):
                for cell in row:
                    cell.alignment = Alignment(wrap_text=True, vertical="top")
        for cell in list(ws[1]) + [c for n in ("COLUMNS", "WARNINGS", "REASON_CODES", "CLEANING_LOG") for c in xw.sheets[n][1]]:
            cell.font = Font(bold=True)
        wr = xw.sheets["REASON_CODES"]
        for r, code in enumerate(REASONS, start=2):
            wr.cell(row=r, column=2).fill = fills[code]


def main():
    ext = pd.read_parquet(EXT)
    log = pd.read_csv(ROOT / "out" / "cleaning_log.csv")
    for z in ZONES:
        d = pd.read_parquet(ZDIR / f"hourly_{z}.parquet")
        why = pd.read_parquet(ZDIR / f"hourly_{z}_reasons.parquet").drop(columns="timestamp_utc")
        e = ext.set_index("timestamp_utc").reindex(d["timestamp_utc"])
        assert e["wx_temp_c"].notna().all(), "external data does not cover the whole grid"
        cal = calendar(d, e)

        meas_cols = [c for c in d.columns if c.endswith(" W") or c.startswith("ENV ")]
        head = ["timestamp_utc", "Regime", "timestamp_local", "weekday_local", "hour_local", "month"]
        parts = [d[head], d[meas_cols], d[["low_coverage"]]]
        out = pd.concat(parts, axis=1)
        out = pd.concat([out, e[WX_COLS].reset_index(drop=True), cal,
                         e[["price_eur_mwh", "co2_intensity_g_kwh"]].reset_index(drop=True)], axis=1)
        out["empty_reasons"] = reasons_text(why, meas_cols)
        assert out["timestamp_utc"].is_unique and len(out) == 26830

        out.to_parquet(FINAL / f"zone_{z}_hourly.parquet", index=False)
        why_out = why[meas_cols].copy()
        why_out.insert(0, "timestamp_utc", d["timestamp_utc"])
        why_out.to_parquet(FINAL / f"zone_{z}_empty_reasons.parquet", index=False)
        print(f"Zone {z}: {out.shape[0]:,} rows x {out.shape[1]} columns; writing Excel ...")
        write_excel(FINAL / f"zone_{z}_hourly.xlsx", z, out, why[meas_cols], log[log["zone"] == z])
        print("   saved", (FINAL / f"zone_{z}_hourly.xlsx").relative_to(ROOT))
    print("\nDone. Files in data/final/")


if __name__ == "__main__":
    main()
