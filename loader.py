from pathlib import Path
import re
import pandas as pd

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def read_workbook(path: Path) -> dict:
    """Un file .xlsx -> {nome_foglio: DataFrame}. sheet_name=None = tutti i fogli."""
    try:
        return pd.read_excel(path, sheet_name=None, engine="calamine")   # veloce
    except (ImportError, ValueError):
        return pd.read_excel(path, sheet_name=None, engine="openpyxl")   # lento ma sicuro


def load_all(raw_dir: Path = RAW_DIR) -> pd.DataFrame:
    files = sorted(raw_dir.glob("Storey1_*_report_by_device.xlsx"))
    if len(files) != 4:
        raise FileNotFoundError(f"Servono 4 file Excel in {raw_dir}, trovati {len(files)}")

    parts = []
    for f in files:
        zone = re.search(r"Storey1_([A-Z]{2})_", f.name).group(1)       # NE / NW / SE / SW
        for sheet, df in read_workbook(f).items():
            df.insert(0, "circuit", sheet)
            df.insert(0, "zone", zone)
            parts.append(df)
            print(f"{zone} | {sheet:16s} | {len(df):>7,} rows")
    return pd.concat(parts, ignore_index=True)


if __name__ == "__main__":
    raw = load_all()
    print(f"\nTOTAL: {len(raw):,} rows, {raw.shape[1]} columns, {raw.groupby(['zone','circuit']).ngroups} sheets")
    print(raw.head(3).to_string())