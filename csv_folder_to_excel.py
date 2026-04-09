import argparse
from pathlib import Path
import pandas as pd


def safe_sheet_name(name: str) -> str:
    """
    Rende il nome del foglio compatibile con Excel.
    Excel permette max 31 caratteri e vieta: \\ / * ? : [ ]
    """
    invalid = ['\\', '/', '*', '?', ':', '[', ']']
    for ch in invalid:
        name = name.replace(ch, '_')
    return name[:31]


def autofit_columns(ws, df: pd.DataFrame):
    """Adatta la larghezza delle colonne ai contenuti."""
    for idx, col in enumerate(df.columns, start=1):
        max_len = len(str(col))
        for val in df[col].astype(str).fillna(""):
            max_len = max(max_len, len(val))
        ws.column_dimensions[ws.cell(row=1, column=idx).column_letter].width = min(max_len + 2, 60)


def read_csv_flexible(csv_path: Path) -> pd.DataFrame:
    """
    Legge il CSV provando:
    - diversi encoding
    - diversi separatori
    """
    encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]
    seps = [",", ";", "\t"]

    last_error = None
    for enc in encodings:
        for sep in seps:
            try:
                return pd.read_csv(csv_path, encoding=enc, sep=sep)
            except Exception as e:
                last_error = e

    raise RuntimeError(f"Impossibile leggere {csv_path.name}: {last_error}")


def convert_folder_to_excel(input_dir: Path, output_xlsx: Path):
    csv_files = sorted(input_dir.glob("*.csv"))

    if not csv_files:
        raise FileNotFoundError(f"Nessun file CSV trovato in: {input_dir}")

    with pd.ExcelWriter(output_xlsx, engine="openpyxl") as writer:
        for csv_file in csv_files:
            print(f"Leggo: {csv_file.name}")
            df = read_csv_flexible(csv_file)

            sheet_name = safe_sheet_name(csv_file.stem)
            df.to_excel(writer, index=False, sheet_name=sheet_name)

            ws = writer.sheets[sheet_name]

            # Congela la prima riga
            ws.freeze_panes = "A2"

            # Filtro automatico
            ws.auto_filter.ref = ws.dimensions

            # Adatta colonne
            autofit_columns(ws, df)

    print(f"\nOK: creato file Excel -> {output_xlsx}")
    print(f"CSV inclusi: {len(csv_files)}")
    for f in csv_files:
        print(f" - {f.name}")


def main():
    parser = argparse.ArgumentParser(
        description="Converte tutti i CSV di una cartella in un unico file Excel (.xlsx)"
    )
    parser.add_argument(
        "input_dir",
        help="Cartella contenente i file CSV"
    )
    parser.add_argument(
        "-o", "--output",
        help="Percorso del file Excel di output (opzionale)"
    )

    args = parser.parse_args()

    input_dir = Path(args.input_dir)

    if not input_dir.exists() or not input_dir.is_dir():
        raise NotADirectoryError(f"Cartella non valida: {input_dir}")

    output_xlsx = Path(args.output) if args.output else input_dir.with_name(f"{input_dir.name}_completo.xlsx")

    convert_folder_to_excel(input_dir, output_xlsx)


if __name__ == "__main__":
    main()