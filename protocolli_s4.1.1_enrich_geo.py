import json
import os
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Iterable

REGIONE2CODICE = {
    "piemonte": "01",
    "valle d'aosta": "02",
    "valledaosta": "02",
    "lombardia": "03",
    "trentino alto adige": "04",
    "trentino-alto adige": "04",
    "veneto": "05",
    "friuli venezia giulia": "06",
    "liguria": "07",
    "emilia-romagna": "08",
    "emilia romagna": "08",
    "toscana": "09",
    "umbria": "10",
    "marche": "11",
    "lazio": "12",
    "abruzzo": "13",
    "molise": "14",
    "campania": "15",
    "puglia": "16",
    "basilicata": "17",
    "calabria": "18",
    "sicilia": "19",
    "sardegna": "20",
}

JSON_STEP2_FOLDER = "output/data/step_2"
JSON_STEP3_FOLDER = "output/data/step_3"
MERGED_JSON = "output/data/step_3.0/3.0_risultati_enriched_merged.json"
INPUT_JSON = Path(r"output\data\step_3.0\3.0_risultati_enriched.json")
OUTPUT_JSON = Path(r"output\data\step_3.0\3.0_risultati_enriched_geo.json")


def normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s0 = s.strip().casefold()
    s1 = "".join(
        c for c in unicodedata.normalize("NFKD", s0)
        if not unicodedata.combining(c)
    )
    s1 = s1.replace("\u2019", "'").replace("`", "'").replace("\u00b4", "'")
    s1 = " ".join(s1.split())
    return s1


def load_comuni_index(comuni_file: str) -> dict[str, list[dict]]:
    comuni_path = Path(comuni_file)
    if not comuni_path.exists():
        raise FileNotFoundError(f"File comuni non trovato: {comuni_path}")

    with comuni_path.open("r", encoding="utf-8") as f:
        comuni = json.load(f)

    by_name: dict[str, list[dict]] = defaultdict(list)
    for rec in comuni:
        nome = normalize_name(
            rec.get("denominazione_ita") or rec.get("denominazione_ita_altra") or ""
        )
        if nome:
            by_name[nome].append(rec)
    return by_name


def best_match(records: list[dict], provincia_entity: str) -> dict | None:
    if not records:
        return None

    if provincia_entity:
        prov_norm = normalize_name(provincia_entity)
        for record in records:
            sigla = (record.get("sigla_provincia") or "").strip().casefold()
            if sigla == prov_norm:
                return record

    return records[0]


def enrich_entity(ent: dict, by_name: dict[str, list[dict]]) -> dict:
    comune_norm = normalize_name(ent.get("comune") or "")
    regione_norm = normalize_name(ent.get("regione") or "")
    match = best_match(by_name.get(comune_norm, []), ent.get("provincia") or "")

    ent["codice_regione"] = REGIONE2CODICE.get(regione_norm, "")
    ent["codice_provincia"] = ""
    ent["codice_comune"] = ""

    if match:
        codice_comune = str(match.get("codice_istat") or "")
        ent["codice_comune"] = codice_comune
        if len(codice_comune) >= 3:
            ent["codice_provincia"] = codice_comune[:3]
        try:
            ent["lat"] = float(match["lat"])
            ent["lon"] = float(match["lon"])
        except Exception:
            pass

    return ent


def enrich_with_geo(input_file: str, output_file: str, comuni_file: str = "gi_comuni.json") -> str:
    """
    Arricchisce un file JSON di risultati con:
      - codice_regione
      - codice_provincia
      - codice_comune
      - lat, lon del comune
    """
    input_path = Path(input_file)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with input_path.open("r", encoding="utf-8") as f:
        risultati = json.load(f)

    by_name = load_comuni_index(comuni_file)

    for item in risultati:
        for ent in item.get("entities", []):
            enrich_entity(ent, by_name)

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(risultati, f, ensure_ascii=False, indent=2)

    print(f"✅ Salvato enrich json: {output_path}")
    return str(output_path)


def merge_json_folder(input_folder: str, output_file: str) -> str:
    """
    Legge tutti i file JSON nella cartella input_folder e li unisce in un unico file.
    """
    input_path = Path(input_folder)
    output_path = Path(output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    merged = []
    for path in sorted(input_path.glob("*.json")):
        try:
            with path.open("r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                merged.extend(data)
            else:
                print(f"Attenzione: {path.name} non contiene una lista, lo aggiungo comunque.")
                merged.append(data)
        except Exception as e:
            print(f"Errore nel file {path.name}: {e}")

    with output_path.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print(f"✅ File uniti in: {output_path}")
    return str(output_path)


def enrich_folder(
    input_folder: str = JSON_STEP2_FOLDER,
    output_folder: str = JSON_STEP3_FOLDER,
    comuni_file: str = "gi_comuni.json",
    only_codes: Iterable[int] | None = None,
) -> None:
    input_path = Path(input_folder)
    output_path = Path(output_folder)
    output_path.mkdir(parents=True, exist_ok=True)

    if only_codes is None:
        candidates = sorted(input_path.glob("*.json"))
    else:
        candidates = [input_path / f"{int(code):02d}.1_risultati.json" for code in only_codes]

    for path in candidates:
        if not path.exists():
            print(f"⚠️ File non trovato: {path}, skip")
            continue

        target = output_path / path.name
        print(f"\n=== Elaboro {path.name} ===")
        print(f"📥 Input:  {path}")
        print(f"📤 Output: {target}")
        enrich_with_geo(str(path), str(target), comuni_file=comuni_file)


if __name__ == "__main__":
    # Esempi:
    # 1) arricchire tutti i JSON in output/json/step_2
    enrich_folder()

    # 2) oppure solo alcuni codici regione:
    # enrich_folder(only_codes=[7, 8, 9])

    # 3) unire tutti i JSON enriched
    merge_json_folder(JSON_STEP3_FOLDER, MERGED_JSON)
