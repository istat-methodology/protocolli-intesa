#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

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

GESTIONE_PATTERNS = [
    r"\bgestion",
    r"\bgestor",
    r"\bpresa in carico\b",
    r"\bcarico dei casi\b",
    r"\bcase management\b",
    r"\bente gestore\b",
    r"\bsoggetto gestore\b",
    r"\bservizio incaricato\b",
    r"\bservizio responsabile\b",
]

MONITORAGGIO_PATTERNS = [
    r"\bmonitor",
    r"\bmonitoraggio\b",
    r"\bverifica\b",
    r"\bverificare\b",
    r"\bvalutazione\b",
    r"\bcontrollo\b",
    r"\bcontrolli\b",
    r"\bosservatorio\b",
    r"\breporting\b",
    r"\braccolta dati\b",
    r"\bflussi informativi\b",
    r"\bflusso informativo\b",
    r"\btracciamento\b",
    r"\bindicatori\b",
]

COORDINAMENTO_PATTERNS = [
    r"\bcoordin",
    r"\bcapofila\b",
    r"\bcabina di regia\b",
    r"\btavolo tecnico\b",
    r"\bregia\b",
    r"\breferente\b",
    r"\breferenti\b",
    r"\bgovernance\b",
    r"\bcomitato di coordinamento\b",
    r"\bgruppo di coordinamento\b",
    r"\bente capofila\b",
    r"\bsoggetto capofila\b",
]

TIPO10_ORDER = [
    "CAV",
    "Settore giudiziario",
    "Servizi comunali",
    "settore sanitario",
    "Regioni/province Autonome",
    "Territorio",
    "Settore Educativo",
    "associazionismo",
    "altro",
    "Province/Città metropolitane",
    "NON CLASSIFICATO",
]


def clean(s: Any) -> str:
    return str(s or "").strip()


def norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", clean(s)).strip()


def safe_int(v: Any) -> int:
    try:
        if pd.isna(v):
            return 0
        return int(float(v))
    except Exception:
        return 0


def normalize_regione(value: Any) -> str:
    s = norm_spaces(str(value or ""))
    mapping = {
        "Valle d'Aosta/Vallee d'Aoste": "Valle d'Aosta/Vallée d'Aoste",
        "Valle d'Aosta/Vallée d'Aoste": "Valle d'Aosta/Vallée d'Aoste",
        "Valle d’Aosta/Vallee d’Aoste": "Valle d'Aosta/Vallée d'Aoste",
        "Valle d’Aosta/Vallée d’Aoste": "Valle d'Aosta/Vallée d'Aoste",
        "Friuli Venezia Giulia": "Friuli-Venezia Giulia",
        "Emilia Romagna": "Emilia-Romagna",
        "Provincia Autonoma di Trento": "Trento",
        "Provincia autonoma di Trento": "Trento",
        "Provincia Autonoma di Bolzano": "Bolzano/Bozen",
        "Provincia autonoma di Bolzano": "Bolzano/Bozen",
    }
    return mapping.get(s, s)


def normalize_tipo10(value: Any) -> str:
    s = norm_spaces(str(value or ""))
    if not s:
        return "NON CLASSIFICATO"
    mapping = {
        "Regioni/province autonome": "Regioni/province Autonome",
        "Regioni/Province Autonome": "Regioni/province Autonome",
        "Province/Citta metropolitane": "Province/Città metropolitane",
        "Settore sanitario": "settore sanitario",
        "Associazionismo": "associazionismo",
        "Altro": "altro",
    }
    return mapping.get(s, s)


def sort_region_df(df: pd.DataFrame, col: str = "regione") -> pd.DataFrame:
    if df.empty or col not in df.columns:
        return df
    order_map = {r: i for i, r in enumerate(REGIONI_ORDINE)}
    out = df.copy()
    out[col] = out[col].astype(str).map(normalize_regione)
    out["_ord"] = out[col].map(order_map).fillna(9999)
    out = out.sort_values(["_ord", col]).drop(columns=["_ord"])
    return out.reset_index(drop=True)


def sort_tipo10_series(series: pd.Series) -> pd.Series:
    if series.empty:
        return series
    order_map = {k: i for i, k in enumerate(TIPO10_ORDER)}
    df = series.reset_index()
    df.columns = ["label", "value"]
    df["label"] = df["label"].astype(str).map(lambda x: normalize_tipo10(x) if x.strip() else "NON CLASSIFICATO")
    df = df.groupby("label", as_index=False)["value"].sum()
    df["_ord"] = df["label"].map(order_map).fillna(9999)
    df = df.sort_values(["_ord", "label"]).drop(columns="_ord")
    return pd.Series(df["value"].values, index=df["label"].values)


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
    vals = [normalize_regione(x) for x in df_soggetti_file.get("regione", pd.Series(dtype=str)).tolist() if clean(x)]
    if vals:
        return Counter(vals).most_common(1)[0][0]
    reg = normalize_regione(file_item.get("_regione_name"))
    if reg:
        return reg
    for ent in get_soggetti_list(file_item):
        reg = normalize_regione(ent.get("regione"))
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
    if "Regioni/Province Autonome" in tipi30 or "Regioni/province Autonome" in tipi30:
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
        return "NON CLASSIFICATO"
    attori = df_file_valid.loc[df_file_valid["ruolo_attore"] == 1].copy()
    if attori.empty:
        attori = df_file_valid.copy()
    vals = attori["tipo_aggregato_10"].fillna("").astype(str).map(norm_spaces)
    vals = vals[vals != ""].map(normalize_tipo10)
    if vals.empty:
        return "NON CLASSIFICATO"
    return str(vals.value_counts().index[0])


def build_text_series(df: pd.DataFrame, colnames: List[str]) -> pd.Series:
    parts = []
    for col in colnames:
        if col in df.columns:
            parts.append(df[col].fillna("").astype(str))
        else:
            parts.append(pd.Series([""] * len(df), index=df.index))
    out = parts[0].copy()
    for s in parts[1:]:
        out = out + " " + s
    return out.str.lower()


def infer_role_from_patterns(df: pd.DataFrame, patterns: List[str]) -> pd.Series:
    hay = build_text_series(
        df,
        [
            "ruoli", "ruolo", "funzione", "funzioni", "note", "ente_capofila",
            "tipo_dettaglio", "denominazione_soggetti_questionari",
            "descrizione_aggregazione_2", "nome_soggetto", "nome_canonico", "nome",
        ],
    )
    mask = pd.Series(False, index=df.index)
    for p in patterns:
        mask = mask | hay.str.contains(p, regex=True, na=False)
    return mask.astype(int)


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

    out["ruolo_gestione"] = infer_role_from_patterns(out, GESTIONE_PATTERNS)
    out["ruolo_monitoraggio"] = infer_role_from_patterns(out, MONITORAGGIO_PATTERNS)
    out["ruolo_coordinamento"] = infer_role_from_patterns(out, COORDINAMENTO_PATTERNS)
    out["ruolo_governance_totale"] = (
        (out["ruolo_gestione"] == 1)
        | (out["ruolo_monitoraggio"] == 1)
        | (out["ruolo_coordinamento"] == 1)
    ).astype(int)

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
    out["tipo_dettaglio"] = out["tipo_dettaglio"].astype(str).map(norm_spaces)
    out["tipo_aggregato_10"] = out["tipo_aggregato_10"].astype(str).map(normalize_tipo10)
    out["macro_tipologia"] = out["tipo_aggregato_10"]

    keep = [
        "id_rete", "input_json", "titolo_rete", "file",
        "regione", "provincia", "comune_soggetto",
        "nome_soggetto", "tipo_dettaglio", "tipo_aggregato_10", "macro_tipologia",
        "ruolo_attore", "ruolo_firmatario", "ruolo_proponente",
        "ruolo_gestione", "ruolo_monitoraggio", "ruolo_coordinamento", "ruolo_governance_totale",
        "stato_osservazione"
    ]
    for c in keep:
        if c not in out.columns:
            out[c] = ""
    return out[keep].copy()


def build_tabella_reti(data: List[dict], df_soggetti: pd.DataFrame) -> pd.DataFrame:
    rows = []
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
            "n_gestione": int(df_file["ruolo_gestione"].sum()) if not df_file.empty else 0,
            "n_monitoraggio": int(df_file["ruolo_monitoraggio"].sum()) if not df_file.empty else 0,
            "n_coordinamento": int(df_file["ruolo_coordinamento"].sum()) if not df_file.empty else 0,
            "n_governance": int(df_file["ruolo_governance_totale"].sum()) if not df_file.empty else 0,
        })
    df_reti = pd.DataFrame(rows)
    if not df_reti.empty:
        df_reti["regione"] = df_reti["regione"].map(normalize_regione)
        df_reti["tipologia_dominante_10"] = df_reti["tipologia_dominante_10"].map(normalize_tipo10)
        df_reti = sort_region_df(df_reti, "regione")
    return df_reti


def build_prospetti(df_reti: pd.DataFrame, df_soggetti: pd.DataFrame) -> Dict[str, pd.DataFrame]:
    prospetti = {}

    p1 = (
        df_reti.groupby("regione", dropna=False)
        .agg(
            reti=("id_rete", "nunique"),
            soggetti=("n_soggetti", "sum"),
            attori=("n_attori", "sum"),
            firmatari=("n_firmatari", "sum"),
            proponenti=("n_proponenti", "sum"),
            governance=("n_governance", "sum"),
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

    def pivot_counts(df_in: pd.DataFrame, sheet_name: str) -> None:
        if df_in.empty:
            prospetti[sheet_name] = pd.DataFrame(columns=["regione"] + TIPO10_ORDER)
            return
        tmp = df_in.copy()
        tmp["tipo_aggregato_10"] = tmp["tipo_aggregato_10"].map(normalize_tipo10)
        p = pd.pivot_table(
            tmp,
            index="regione",
            columns="tipo_aggregato_10",
            values="nome_soggetto",
            aggfunc="count",
            fill_value=0,
        ).reset_index()
        for c in TIPO10_ORDER:
            if c not in p.columns:
                p[c] = 0
        p = p[["regione"] + [c for c in TIPO10_ORDER if c in p.columns]]
        prospetti[sheet_name] = sort_region_df(p, "regione")

    pivot_counts(df_soggetti, "prospetto_soggetti_tipo10_per_regione")
    pivot_counts(df_soggetti.loc[df_soggetti["ruolo_attore"] == 1], "prospetto_attori_tipo10_per_regione")
    pivot_counts(df_soggetti.loc[df_soggetti["ruolo_firmatario"] == 1], "prospetto_firmatari_tipo10_per_regione")
    pivot_counts(df_soggetti.loc[df_soggetti["ruolo_proponente"] == 1], "prospetto_proponenti_tipo10_per_regione")
    pivot_counts(df_soggetti.loc[df_soggetti["ruolo_governance_totale"] == 1], "prospetto_governance_tipo10_per_regione")

    p3 = pd.pivot_table(
        df_soggetti,
        index="regione",
        columns="tipo_dettaglio",
        values="nome_soggetto",
        aggfunc="count",
        fill_value=0,
    ).reset_index()
    prospetti["prospetto_soggetti_tipo30_per_regione"] = sort_region_df(p3, "regione")

    return prospetti


def write_report_controlli(path: Path, df_reti: pd.DataFrame, df_soggetti: pd.DataFrame) -> None:
    lines = []

    def add_breakdown(title: str, series: pd.Series, normalize_tipo: bool = False) -> None:
        lines.append(title)
        if series.empty:
            lines.append("- nessun dato")
            lines.append("")
            return
        s = series.copy()
        if normalize_tipo:
            s = sort_tipo10_series(s)
        else:
            labels, values = [], []
            for k, v in s.items():
                label = normalize_regione(k) if title.endswith("regione") else str(k).strip()
                labels.append(label if label else "NON CLASSIFICATO")
                values.append(int(v))
            s = pd.Series(values, index=labels).groupby(level=0).sum()
            if "regione" in title:
                order_map = {r: i for i, r in enumerate(REGIONI_ORDINE)}
                tmp = s.reset_index()
                tmp.columns = ["label", "value"]
                tmp["_ord"] = tmp["label"].map(order_map).fillna(9999)
                tmp = tmp.sort_values(["_ord", "label"]).drop(columns="_ord")
                s = pd.Series(tmp["value"].values, index=tmp["label"].values)
        for k, v in s.items():
            lines.append(f"- {k}: {int(v)}")
        lines.append("")

    def count_by_region(df: pd.DataFrame) -> pd.Series:
        return df.groupby("regione").size()

    def count_by_tipo10(df: pd.DataFrame) -> pd.Series:
        return df.groupby("tipo_aggregato_10").size()

    subsets = {
        "soggetti": df_soggetti,
        "attori": df_soggetti.loc[df_soggetti["ruolo_attore"] == 1],
        "firmatari": df_soggetti.loc[df_soggetti["ruolo_firmatario"] == 1],
        "proponenti": df_soggetti.loc[df_soggetti["ruolo_proponente"] == 1],
        "governance": df_soggetti.loc[df_soggetti["ruolo_governance_totale"] == 1],
    }

    lines.append("REPORT CONTROLLI RETI VIOLENZA")
    lines.append("")
    lines.append(f"Totale reti: {df_reti['id_rete'].nunique() if not df_reti.empty else 0}")
    add_breakdown("di cui per regione", df_reti.groupby("regione")["id_rete"].nunique())
    add_breakdown("di cui per 10 classi", df_reti.groupby("tipologia_dominante_10")["id_rete"].nunique(), normalize_tipo=True)

    for label, df_sub in subsets.items():
        lines.append(f"Totale {label}: {len(df_sub)}")
        add_breakdown("di cui per regione", count_by_region(df_sub))
        add_breakdown("di cui per 10 classi", count_by_tipo10(df_sub), normalize_tipo=True)

    path.write_text("\n".join(lines), encoding="utf-8")


def export_excel(path: Path, df_soggetti: pd.DataFrame, df_reti: pd.DataFrame, prospetti: Dict[str, pd.DataFrame]) -> None:
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df_soggetti.to_excel(writer, index=False, sheet_name="tabella_soggetti")
        df_reti.to_excel(writer, index=False, sheet_name="tabella_reti")
        for name, df in prospetti.items():
            df.to_excel(writer, index=False, sheet_name=name[:31])


def safe_write_csv(df: pd.DataFrame, out_file: Path) -> Path:
    try:
        if out_file.exists():
            out_file.unlink()
        df.to_csv(out_file, index=False, encoding="utf-8-sig")
        return out_file
    except PermissionError:
        alt_file = out_file.with_name(f"{out_file.stem}_NEW{out_file.suffix}")
        df.to_csv(alt_file, index=False, encoding="utf-8-sig")
        return alt_file
    except Exception:
        alt_file = out_file.with_name(f"{out_file.stem}_{pd.Timestamp.now():%H%M%S}{out_file.suffix}")
        df.to_csv(alt_file, index=False, encoding="utf-8-sig")
        return alt_file




def suggest_tipo10(nome: str, tipo_dettaglio: str) -> str:
    txt = f"{str(nome)} {str(tipo_dettaglio)}".lower()
    rules = [
        ("CAV", ["centro antiviolenza", "cav"]),
        ("Settore giudiziario", ["procura", "tribunale", "questura", "prefettura", "carabinieri", "polizia"]),
        ("Servizi comunali", ["comune", "servizi sociali", "municipio"]),
        ("settore sanitario", ["asl", "ausl", "osped", "consultorio", "sanitario"]),
        ("Regioni/province Autonome", ["regione", "provincia autonoma"]),
        ("Province/Città metropolitane", ["provincia", "città metropolitana", "citta metropolitana"]),
        ("Settore Educativo", ["scuola", "istituto", "università", "universita"]),
        ("associazionismo", ["associazione", "onlus", "cooperativa", "fondazione", "aps", "odv"]),
        ("Territorio", ["unione dei comuni", "comunità montana", "comunita montana", "distretto"]),
    ]
    for label, keys in rules:
        if any(k in txt for k in keys):
            return label
    return "altro"


def build_report_non_classificati(df_soggetti: pd.DataFrame, output_dir: Path) -> None:
    df_nc = df_soggetti.loc[df_soggetti["tipo_aggregato_10"] == "NON CLASSIFICATO"].copy()

    if df_nc.empty:
        (output_dir / "report_non_classificati.txt").write_text(
            "REPORT NON CLASSIFICATI\\n\\nNessun record non classificato.",
            encoding="utf-8"
        )
        return

    df_nc["suggerimento_tipo10"] = [
        suggest_tipo10(n, t) for n, t in zip(df_nc["nome_soggetto"], df_nc["tipo_dettaglio"])
    ]

    per_regione = (
        df_nc.groupby("regione")
        .size()
        .reset_index(name="totale")
    )
    if "regione" in per_regione.columns:
        per_regione = sort_region_df(per_regione, "regione")

    per_nome = (
        df_nc.groupby("nome_soggetto")
        .size()
        .reset_index(name="totale")
        .sort_values(["totale", "nome_soggetto"], ascending=[False, True])
    )

    per_tipo_orig = (
        df_nc.groupby("tipo_dettaglio")
        .size()
        .reset_index(name="totale")
        .sort_values(["totale", "tipo_dettaglio"], ascending=[False, True])
    )

    safe_write_csv(df_nc, output_dir / "non_classificati_dettaglio.csv")
    safe_write_csv(per_regione, output_dir / "non_classificati_per_regione.csv")
    safe_write_csv(per_nome, output_dir / "non_classificati_per_nome.csv")
    safe_write_csv(per_tipo_orig, output_dir / "non_classificati_per_tipo_orig.csv")

    lines = []
    lines.append("REPORT NON CLASSIFICATI")
    lines.append("")
    lines.append(f"Totale non classificati: {len(df_nc)}")
    lines.append(f"Percentuale sul totale soggetti: {round(len(df_nc) / max(len(df_soggetti),1) * 100, 2)}%")
    lines.append("")
    lines.append("Per regione")
    for _, r in per_regione.iterrows():
        lines.append(f"- {r['regione']}: {int(r['totale'])}")
    lines.append("")
    lines.append("Top soggetti non classificati")
    for _, r in per_nome.head(20).iterrows():
        lines.append(f"- {r['nome_soggetto']}: {int(r['totale'])}")
    lines.append("")
    lines.append("Top classi originali")
    for _, r in per_tipo_orig.head(20).iterrows():
        lines.append(f"- {r['tipo_dettaglio']}: {int(r['totale'])}")

    (output_dir / "report_non_classificati.txt").write_text(
        "\\n".join(lines),
        encoding="utf-8"
    )

input_path = Path(r"G:\develpment\protocolli-intesa\output\data\step_3.0\3.0_risultati_enriched_merged.json")
soggetti_csv = Path(r"G:\develpment\protocolli-intesa\output\data\step_3.1\soggetti_unici_puliti.csv")
output_dir = Path(r"G:\develpment\protocolli-intesa\output\data\step_3.2")


def main() -> None:
    if not input_path.exists():
        raise FileNotFoundError(f"JSON input non trovato: {input_path}")
    if not soggetti_csv.exists():
        raise FileNotFoundError(f"CSV soggetti puliti non trovato: {soggetti_csv}")

    output_dir.mkdir(parents=True, exist_ok=True)

    print("📂 INPUT_JSON   :", input_path)
    print("📄 SOGGETTI_CSV :", soggetti_csv)
    print("💾 OUTPUT_DIR   :", output_dir)

    data = load_json(input_path)
    df_csv = read_csv_flexible(soggetti_csv)
    df_soggetti = normalize_soggetti_csv(df_csv, input_path.name)
    df_reti = build_tabella_reti(data, df_soggetti)
    prospetti = build_prospetti(df_reti, df_soggetti)

    written = []
    written.append(safe_write_csv(df_soggetti, output_dir / "tabella_soggetti.csv"))
    written.append(safe_write_csv(df_reti, output_dir / "tabella_reti.csv"))
    for name, df in prospetti.items():
        written.append(safe_write_csv(df, output_dir / f"{name}.csv"))

        
    write_report_controlli(output_dir / "report_controlli_reti.txt", df_reti, df_soggetti)
    build_report_non_classificati(df_soggetti, output_dir)
    export_excel(output_dir / "reti_violenza_output.xlsx", df_soggetti, df_reti, prospetti)

    print("✅ Completato")
    for p in written:
        print(f"   - {p}")
    print(f"   - {output_dir / 'report_controlli_reti.txt'}")
    print(f"   - {output_dir / 'reti_violenza_output.xlsx'}")


if __name__ == "__main__":
    main()
