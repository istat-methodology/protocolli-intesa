#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

REGION_CODE_TO_NAME = {
    "01": "Piemonte",
    "02": "Valle d'Aosta/Vallée d'Aoste",
    "03": "Lombardia",
    "04": "Bolzano/Bozen",
    "05": "Trento",
    "06": "Veneto",
    "07": "Liguria",
    "08": "Emilia-Romagna",
    "09": "Toscana",
    "10": "Umbria",
    "11": "Marche",
    "12": "Lazio",
    "13": "Abruzzo",
    "14": "Molise",
    "15": "Campania",
    "16": "Puglia",
    "17": "Basilicata",
    "18": "Calabria",
    "19": "Sicilia",
    "20": "Sardegna",
    "21": "Friuli-Venezia Giulia",
}

REGIONI_ORDINE = [
    "Abruzzo", "Basilicata", "Bolzano/Bozen", "Calabria", "Campania",
    "Emilia-Romagna", "Friuli-Venezia Giulia", "Lazio", "Liguria",
    "Lombardia", "Marche", "Molise", "Piemonte", "Puglia", "Sardegna",
    "Sicilia", "Toscana", "Trento", "Umbria",
    "Valle d'Aosta/Vallée d'Aoste", "Veneto"
]

AMBITO_ORDER = [
    "Comunale",
    "Ambito intercomunale (Unione comuni etc.)",
    "Area metropolitana/provinciale",
    "Ambito sociale",
    "Ambito sanitario coincidente con articolazioni locali delle Aziende Sanitarie Locali e/o Case della Salute e/o ATS",
    "Ambito regionale/Prov. Autonome",
    "Ambito distrettuale - legale",
    "Altro",
]

ATTO_FORMALE_PATTERNS = [
    r"\bprotocollo\b",
    r"\baccordo\b",
    r"\bconvenzione\b",
    r"\bintesa\b",
    r"\bdelibera\b",
    r"\bdecreto\b",
    r"\blinee di indirizzo\b",
]

def clean(s: Any) -> str:
    return str(s or "").strip()

def norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", clean(s)).strip()

def safe_int(v: Any) -> int:
    try:
        if pd.isna(v):
            return 0
        return int(v)
    except Exception:
        return 0

def normalize_regione(value: Any) -> str:
    return norm_spaces(str(value or ""))

def sort_region_df(df: pd.DataFrame, col: str = "regione") -> pd.DataFrame:
    if df.empty or col not in df.columns:
        return df
    order_map = {r: i for i, r in enumerate(REGIONI_ORDINE)}
    out = df.copy()
    out["_ord"] = out[col].map(order_map).fillna(9999)
    out = out.sort_values(["_ord", col]).drop(columns=["_ord"])
    return out.reset_index(drop=True)

def read_csv_flexible(path: Path) -> pd.DataFrame:
    encodings = ["utf-8", "utf-8-sig", "latin1", "cp1252"]
    seps = [",", ";", "\t"]
    last_error = None
    for enc in encodings:
        for sep in seps:
            try:
                return pd.read_csv(path, encoding=enc, sep=sep)
            except Exception as e:
                last_error = e
    raise RuntimeError(f"Impossibile leggere {path}: {last_error}")

def load_json(path: Path) -> List[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and "regioni" in data:
        flat: List[dict] = []
        for reg_code, blocco in (data.get("regioni") or {}).items():
            reg_code = str(reg_code).zfill(2)
            reg_name = REGION_CODE_TO_NAME.get(reg_code, "")
            for item in (blocco.get("files") or []):
                if isinstance(item, dict):
                    rec = dict(item)
                    rec["_regione_code"] = reg_code
                    rec["_regione_name"] = reg_name
                    flat.append(rec)
        return flat
    if isinstance(data, list):
        return [dict(x) for x in data if isinstance(x, dict)]
    raise ValueError("Il JSON di input deve contenere una lista di record oppure un oggetto con chiave 'regioni'")

def get_soggetti_list(file_item: dict) -> List[dict]:
    if isinstance(file_item.get("soggetti"), list):
        return file_item["soggetti"]
    risultato = file_item.get("risultato") or {}
    if isinstance(risultato.get("entities"), list):
        return risultato["entities"]
    entities = file_item.get("entities")
    if isinstance(entities, dict) and isinstance(entities.get("entities"), list):
        return entities["entities"]
    if isinstance(entities, list):
        return entities
    return []

def get_file_title(file_item: dict) -> str:
    file_name = clean(file_item.get("file"))
    if not file_name:
        return ""
    stem = Path(file_name).stem
    stem = re.sub(r"^\d{2}[_ ]+", "", stem)
    return norm_spaces(stem)

def infer_atto_formale(file_item: dict) -> int:
    haystack = " ".join([
        clean(file_item.get("file")),
        get_file_title(file_item),
        " ".join(clean(x) for x in file_item.get("firmatari", []) or []),
        " ".join(clean(x) for x in file_item.get("soggetti_proponenti", []) or []),
    ]).lower()
    return 1 if any(re.search(p, haystack) for p in ATTO_FORMALE_PATTERNS) else 0

def infer_rete_region(file_item: dict, df_soggetti_file: pd.DataFrame) -> str:
    vals = [clean(x) for x in df_soggetti_file.get("regione", pd.Series(dtype=str)).tolist() if clean(x)]
    if vals:
        return Counter(vals).most_common(1)[0][0]
    reg = clean(file_item.get("_regione_name"))
    if reg:
        return reg
    for ent in get_soggetti_list(file_item):
        reg = clean(ent.get("regione"))
        if reg:
            return reg
    return ""

def infer_rete_provincia(file_item: dict, df_soggetti_file: pd.DataFrame) -> str:
    vals = [clean(x) for x in df_soggetti_file.get("provincia", pd.Series(dtype=str)).tolist() if clean(x)]
    if vals:
        return Counter(vals).most_common(1)[0][0]
    for ent in get_soggetti_list(file_item):
        prov = clean(ent.get("provincia"))
        if prov:
            return prov
    return ""

def infer_ambito_territoriale(file_item: dict, df_soggetti_file: pd.DataFrame) -> str:
    text_parts = [
        clean(file_item.get("file")),
        get_file_title(file_item),
        " ".join(clean(x) for x in file_item.get("firmatari", []) or []),
        " ".join(clean(x) for x in file_item.get("soggetti_proponenti", []) or []),
        " ".join(clean(x) for x in file_item.get("attori_coinvolti", []) or []),
    ]
    for ent in get_soggetti_list(file_item):
        text_parts.extend([
            clean(ent.get("nome")),
            clean(ent.get("tipo")),
            clean(ent.get("note")),
            clean(ent.get("ente_capofila")),
        ])
    hay = " ".join(text_parts).lower()

    if any(x in hay for x in ["regione ", "regionale", "provincia autonoma"]):
        return "Ambito regionale/Prov. Autonome"
    if any(x in hay for x in ["città metropolitana", "citta metropolitana", "provincia di ", "provinciale", "area vasta"]):
        return "Area metropolitana/provinciale"
    if any(x in hay for x in ["distretto giudiziario", "corte d'appello", "corte d appello"]):
        return "Ambito distrettuale - legale"
    if any(x in hay for x in ["ats", "distretto sanitario", "casa della salute", "case della salute"]):
        return "Ambito sanitario coincidente con articolazioni locali delle Aziende Sanitarie Locali e/o Case della Salute e/o ATS"
    if any(x in hay for x in ["società della salute", "societa della salute", "piano di zona", "ambito sociale", "distretto socio-sanitario", "distretto sociosanitario", "conferenza dei sindaci asl", "conferenza zonale dei sindaci"]):
        return "Ambito sociale"
    if any(x in hay for x in ["unione dei comuni", "unione montana", "comunità montana", "comunita montana"]):
        return "Ambito intercomunale (Unione comuni etc.)"

    tipi30 = set(df_soggetti_file.get("tipo_dettaglio", pd.Series(dtype=str)).astype(str))
    if "Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)" in tipi30:
        return "Ambito sociale"
    if "Enti territoriali sovracomunali" in tipi30:
        return "Ambito intercomunale (Unione comuni etc.)"
    if "Province/Città metropolitane" in tipi30 or "Polizia provinciale" in tipi30:
        return "Area metropolitana/provinciale"
    if "Regioni/Province Autonome" in tipi30:
        return "Ambito regionale/Prov. Autonome"

    prov = infer_rete_provincia(file_item, df_soggetti_file)
    if prov:
        return "Area metropolitana/provinciale"

    comuni = set(x for x in df_soggetti_file.get("comune_soggetto", pd.Series(dtype=str)).astype(str) if clean(x))
    if len(comuni) > 1:
        return "Ambito intercomunale (Unione comuni etc.)"
    if len(comuni) == 1:
        return "Comunale"

    return "Altro"

def compute_dominant_tipo10(df_file_valid: pd.DataFrame) -> str:
    if df_file_valid.empty:
        return ""
    attori = df_file_valid.loc[df_file_valid["ruolo_attore"] == 1].copy()
    if attori.empty:
        attori = df_file_valid.copy()
    counts = attori["tipo_aggregato_10"].value_counts()
    return counts.index[0] if not counts.empty else ""

def normalize_soggetti_csv(df: pd.DataFrame, input_json_name: str) -> pd.DataFrame:
    out = df.copy()
    if "file" not in out.columns:
        raise ValueError("Nel CSV soggetti manca la colonna 'file'")

    if "nome_soggetto" not in out.columns:
        if "nome_canonico" in out.columns:
            out["nome_soggetto"] = out["nome_canonico"]
        elif "nome" in out.columns:
            out["nome_soggetto"] = out["nome"]
        else:
            out["nome_soggetto"] = ""

    if "tipo_dettaglio" not in out.columns:
        if "denominazione_soggetti_questionari" in out.columns:
            out["tipo_dettaglio"] = out["denominazione_soggetti_questionari"]
        elif "tipo_standard" in out.columns:
            out["tipo_dettaglio"] = out["tipo_standard"]
        elif "tipo" in out.columns:
            out["tipo_dettaglio"] = out["tipo"]
        else:
            out["tipo_dettaglio"] = "Altro"

    if "tipo_aggregato_10" not in out.columns:
        if "descrizione_aggregazione_2" in out.columns:
            out["tipo_aggregato_10"] = out["descrizione_aggregazione_2"]
        else:
            out["tipo_aggregato_10"] = ""

    if "regione" not in out.columns:
        out["regione"] = out["regione_finale"] if "regione_finale" in out.columns else ""
    if "provincia" not in out.columns:
        out["provincia"] = out["provincia_finale"] if "provincia_finale" in out.columns else ""
    if "comune_soggetto" not in out.columns:
        if "comune_finale" in out.columns:
            out["comune_soggetto"] = out["comune_finale"]
        elif "comune" in out.columns:
            out["comune_soggetto"] = out["comune"]
        else:
            out["comune_soggetto"] = ""

    for col, default in {
        "ruolo_attore": 1,
        "ruolo_firmatario": 0,
        "ruolo_proponente": 0,
    }.items():
        if col not in out.columns:
            out[col] = default
        out[col] = out[col].map(safe_int)

    if "stato_osservazione" not in out.columns:
        out["stato_osservazione"] = "valido_localizzato"

    out = out.loc[out["stato_osservazione"].isin(["valido_localizzato", "valido_non_localizzato"])].copy()

    out["id_rete"] = out["file"].astype(str)
    out["input_json"] = input_json_name
    out["titolo_rete"] = out["file"].astype(str).map(lambda x: re.sub(r"^\d{2}[_ ]+", "", Path(str(x)).stem))
    out["regione"] = out["regione"].astype(str).map(normalize_regione)
    out["provincia"] = out["provincia"].astype(str)
    out["comune_soggetto"] = out["comune_soggetto"].astype(str)
    out["nome_soggetto"] = out["nome_soggetto"].astype(str)
    out["tipo_dettaglio"] = out["tipo_dettaglio"].astype(str)
    out["tipo_aggregato_10"] = out["tipo_aggregato_10"].astype(str)
    out["macro_tipologia"] = out["tipo_aggregato_10"]

    keep = [
        "id_rete", "input_json", "titolo_rete", "file",
        "regione", "provincia", "comune_soggetto",
        "nome_soggetto", "tipo_dettaglio", "tipo_aggregato_10", "macro_tipologia",
        "ruolo_attore", "ruolo_firmatario", "ruolo_proponente",
        "stato_osservazione"
    ]
    return out[keep].copy()

def build_tabella_reti(data: List[dict], df_soggetti: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for file_item in data:
        file_name = clean(file_item.get("file"))
        if not file_name:
            continue
        df_file = df_soggetti.loc[df_soggetti["file"].astype(str) == file_name].copy()
        rows.append({
            "id_rete": file_name,
            "file": file_name,
            "titolo_rete": get_file_title(file_item),
            "regione": infer_rete_region(file_item, df_file),
            "provincia": infer_rete_provincia(file_item, df_file),
            "ambito_territoriale": infer_ambito_territoriale(file_item, df_file),
            "atto_formale": infer_atto_formale(file_item),
            "tipologia_dominante_10": compute_dominant_tipo10(df_file),
            "n_soggetti": len(df_file),
            "n_attori": int(df_file["ruolo_attore"].sum()) if not df_file.empty else 0,
            "n_firmatari": int(df_file["ruolo_firmatario"].sum()) if not df_file.empty else 0,
            "n_proponenti": int(df_file["ruolo_proponente"].sum()) if not df_file.empty else 0,
        })
    df_reti = pd.DataFrame(rows)
    if not df_reti.empty:
        df_reti = sort_region_df(df_reti, "regione")
    return df_reti

def build_prospetti(df_reti: pd.DataFrame, df_soggetti: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    prospetti: Dict[str, pd.DataFrame] = {}
    p1 = (
        df_reti.groupby("regione", dropna=False)
        .agg(
            reti=("id_rete", "nunique"),
            soggetti=("n_soggetti", "sum"),
            attori=("n_attori", "sum"),
            firmatari=("n_firmatari", "sum"),
            proponenti=("n_proponenti", "sum"),
        )
        .reset_index()
    )
    prospetti["prospetto_reti_per_regione"] = sort_region_df(p1, "regione")

    p2 = pd.crosstab(df_reti["regione"], df_reti["ambito_territoriale"]).reset_index()
    for col in AMBITO_ORDER:
        if col not in p2.columns:
            p2[col] = 0
    p2 = p2[["regione"] + AMBITO_ORDER]
    prospetti["prospetto_ambito_per_regione"] = sort_region_df(p2, "regione")

    p3 = pd.pivot_table(
        df_soggetti,
        index="regione",
        columns="tipo_aggregato_10",
        values="nome_soggetto",
        aggfunc="count",
        fill_value=0,
    ).reset_index()
    prospetti["prospetto_soggetti_tipo10_per_regione"] = sort_region_df(p3, "regione")

    p4 = pd.pivot_table(
        df_soggetti,
        index="regione",
        columns="tipo_dettaglio",
        values="nome_soggetto",
        aggfunc="count",
        fill_value=0,
    ).reset_index()
    prospetti["prospetto_soggetti_tipo30_per_regione"] = sort_region_df(p4, "regione")

    return prospetti

def write_report_controlli(path: Path, df_reti: pd.DataFrame, df_soggetti: pd.DataFrame) -> None:
    lines = []
    lines.append("REPORT CONTROLLI RETI VIOLENZA")
    lines.append("")
    lines.append(f"Totale reti: {df_reti['id_rete'].nunique() if not df_reti.empty else 0}")
    lines.append(f"Totale soggetti: {len(df_soggetti)}")
    lines.append(f"Totale attori: {int(df_soggetti['ruolo_attore'].sum()) if not df_soggetti.empty else 0}")
    lines.append(f"Totale firmatari: {int(df_soggetti['ruolo_firmatario'].sum()) if not df_soggetti.empty else 0}")
    lines.append(f"Totale proponenti: {int(df_soggetti['ruolo_proponente'].sum()) if not df_soggetti.empty else 0}")
    lines.append("")
    lines.append("RETI PER REGIONE")
    if df_reti.empty:
        lines.append("- nessuna rete")
    else:
        for reg, n in df_reti.groupby("regione")["id_rete"].nunique().items():
            lines.append(f"- {reg}: {n}")
    path.write_text("\n".join(lines), encoding="utf-8")

def export_excel(path: Path, df_soggetti: pd.DataFrame, df_reti: pd.DataFrame, prospetti: Dict[str, pd.DataFrame]) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df_soggetti.to_excel(writer, index=False, sheet_name="tabella_soggetti")
        df_reti.to_excel(writer, index=False, sheet_name="tabella_reti")
        for name, df in prospetti.items():
            df.to_excel(writer, index=False, sheet_name=name[:31])

input_path= Path(r"G:\develpment\protocolli-intesa\output\json\merged\all_risultati_enriched_2.4.json")
soggetti_csv = Path(r"G:\develpment\protocolli-intesa\output\reports_integrati\soggetti_unici_puliti.csv")
output_dir = Path(r"G:\develpment\protocolli-intesa\output\reti_violenza")

def main() -> None:
    
    


    if not input_path.exists():
        raise FileNotFoundError(f"JSON input non trovato: {input_path}")

    if not soggetti_csv.exists():
        raise FileNotFoundError(f"CSV soggetti puliti non trovato: {soggetti_csv_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    print("📂 INPUT_JSON   :", input_path)
    print("📄 SOGGETTI_CSV :", soggetti_csv)
    print("💾 OUTPUT_DIR   :", output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"📂 INPUT_JSON   : {input_path}")
    print(f"📄 SOGGETTI_CSV : {soggetti_csv}")
    print(f"💾 OUTPUT_DIR   : {output_dir}")

    data = load_json(input_path)
    df_csv = read_csv_flexible(soggetti_csv)
    df_soggetti = normalize_soggetti_csv(df_csv, input_path.name)
    df_reti = build_tabella_reti(data, df_soggetti)
    prospetti = build_prospetti(df_reti, df_soggetti)

    df_soggetti.to_csv(output_dir / "tabella_soggetti.csv", index=False, encoding="utf-8-sig")
    df_reti.to_csv(output_dir / "tabella_reti.csv", index=False, encoding="utf-8-sig")
    for name, df in prospetti.items():
        df.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8-sig")

    write_report_controlli(output_dir / "report_controlli_reti.txt", df_reti, df_soggetti)
    export_excel(output_dir / "reti_violenza_output.xlsx", df_soggetti, df_reti, prospetti)

    print("✅ Completato")
    print(f"   - {output_dir / 'tabella_soggetti.csv'}")
    print(f"   - {output_dir / 'tabella_reti.csv'}")
    print(f"   - {output_dir / 'report_controlli_reti.txt'}")
    print(f"   - {output_dir / 'reti_violenza_output.xlsx'}")

if __name__ == "__main__":
    main()


