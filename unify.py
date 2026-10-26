import pandas as pd
from loader import load_all

# nome originale nel file Excel -> nuovo nome (minuscolo, senza spazi)
COLUMN_MAP = {
    "Timestamp": "timestamp",
    "W": "w",                         # potenza attiva [W]
    "I": "i",                         # corrente [A]
    "Ea": "ea",                       # contatore energia attiva [Wh]
    "Er": "er",                       # contatore energia reattiva [varh]
    "Pa": "pa",                       # potenza apparente [VA]
    "E Device type": "device_type",   # tipo di circuito (= nome foglio)
    "Number of Edevices": "n_devices",
    "Lum": "lum",                     # luce [lux]
    "Hum": "hum",                     # umidita [%]
    "Temp": "temp",                   # temperatura interna [C]
    "Pres": "pres",                   # presenza 0/1
}
FLOAT_COLS = ["w", "i", "ea", "er", "pa", "lum", "hum", "temp", "pres"]


def unify(raw: pd.DataFrame) -> pd.DataFrame:
    # 1) i nomi delle colonne devono essere esattamente quelli attesi
    expected = set(COLUMN_MAP) | {"zone", "circuit"}
    if set(raw.columns) != expected:
        raise ValueError(f"Colonne diverse dal previsto: {set(raw.columns) ^ expected}")

    # 2) rinomina e riordina
    df = raw.rename(columns=COLUMN_MAP)
    df = df[["zone", "circuit"] + list(COLUMN_MAP.values())]

    # 3) tipi: un tipo solo per colonna. Testo non numerico -> NaN (e lo contiamo)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    for c in FLOAT_COLS:
        before = df[c].isna().sum()
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("float64")
        lost = df[c].isna().sum() - before
        if lost:
            print(f"ATTENZIONE: {lost} celle di '{c}' non erano numeri e sono diventate NaN")
    df["n_devices"] = pd.to_numeric(df["n_devices"], errors="coerce").astype("Int16")
    df["device_type"] = df["device_type"].astype("string")
    df["zone"] = df["zone"].astype("category")
    df["circuit"] = df["circuit"].astype("category")

    # 4) controlli
    assert df["timestamp"].notna().all(), "timestamp non validi"
    assert (df["device_type"] == df["circuit"].astype("string")).all(), "device_type != nome foglio"
    assert not df.duplicated(["zone", "circuit", "timestamp"]).any(), "timestamp duplicati"
    return df


if __name__ == "__main__":
    df = unify(load_all())
    print("\nTipi delle colonne:")
    print(df.dtypes.to_string())
    print(f"\nOK: {len(df):,} righe, {df.shape[1]} colonne")