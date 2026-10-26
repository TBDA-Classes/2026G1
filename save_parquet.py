from pathlib import Path
import pandas as pd
from loader import load_all
from unify import unify

OUT_FILE = Path(__file__).resolve().parents[1] / "data" / "raw_combined_long.parquet"


def main():
    df = unify(load_all())
    df = df.sort_values(["zone", "circuit", "timestamp"]).reset_index(drop=True)

    OUT_FILE.parent.mkdir(exist_ok=True)
    df.to_parquet(OUT_FILE, index=False)          # richiede la libreria pyarrow
    print(f"\nSalvato: {OUT_FILE}  ({OUT_FILE.stat().st_size / 1e6:.1f} MB)")

    # controllo: rileggo il file e verifico che sia identico a quello salvato
    back = pd.read_parquet(OUT_FILE)
    assert back.shape == df.shape, "numero di righe/colonne diverso"
    assert (back.dtypes == df.dtypes).all(), "tipi diversi dopo la rilettura"
    print(f"Controllo OK: riletto {len(back):,} righe, {back.shape[1]} colonne, tipi invariati")


if __name__ == "__main__":
    main()