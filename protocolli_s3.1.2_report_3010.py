#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import csv
import json
import re
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import networkx as nx  # optional
except Exception:
    nx = None

import pandas as pd

INPUT_JSON = Path(r"output\json\merged\all_risultati_enriched_2.4.json")
AGGREGATION_FILE = Path(r"aggregazioni\load_reference_table_30_to_10.json")
OUTPUT_DIR = Path(r"output\reports_integrati")

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

PROVINCE = {
    "AREZZO": ("Arezzo", "Toscana"),
    "FIRENZE": ("Firenze", "Toscana"),
    "GROSSETO": ("Grosseto", "Toscana"),
    "LIVORNO": ("Livorno", "Toscana"),
    "LUCCA": ("Lucca", "Toscana"),
    "MASSA CARRARA": ("Massa-Carrara", "Toscana"),
    "MASSA-CARRARA": ("Massa-Carrara", "Toscana"),
    "PISA": ("Pisa", "Toscana"),
    "PISTOIA": ("Pistoia", "Toscana"),
    "PRATO": ("Prato", "Toscana"),
    "SIENA": ("Siena", "Toscana"),
}

FILE_REGION_RE = re.compile(r"^(\d{2})[_ ]")

BARE_COMUNI = {
    "BARBERINO DEL MUGELLO", "BORGO SAN LORENZO", "CAMPI BISENZIO",
    "FIGLINE E INCISA VALDARNO", "LASTRA A SIGNA", "PONTASSIEVE",
    "SCANDICCI", "SESTO FIORENTINO", "TAVARNELLE VAL DI PESA",
    "SAN CASCIANO VAL DI PESA", "BAGNO A RIPOLI", "IMPRUNETA",
    "GREVE IN CHIANTI", "RUFINA", "PELAGO", "REGGELLO",
    "FIESOLE", "CALENZANO", "SIGNA"
}

GENERIC_EXACT = {
    "COMUNI", "QUESTURA", "PREFETTURA", "TRIBUNALE ORDINARIO", "TRIBUNALE",
    "PROCURA", "PROCURA DELLA REPUBBLICA", "PROCURA MINORILE", "PRESIDENTE DEL TRIBUNALE",
    "FORZE DELL'ORDINE", "FORZE DI POLIZIA GIUDIZIARIA", "POLIZIA GIUDIZIARIA",
    "POLIZIA DI STATO", "CARABINIERI", "GUARDIA DI FINANZA", "AUTORITA GIUDIZIARIA",
    "AUTORITA' GIUDIZIARIA", "SERVIZI SOCIALI", "SERVIZI SOCIALI COMUNALI", "SOCIETA DELLA SALUTE",
    "ZONE SOCIO-SANITARIE", "ZONE SOCIO SANITARIE", "CENTRO ANTIVIOLENZA", "CENTRI ANTIVIOLENZA",
    "AMBULATORIO", "CONSULTORIO", "CONSULTORIO PRINCIPALE", "PRONTO SOCCORSO", "UNITA OPERATIVA",
    "DIRETTORE SANITARIO", "AZIENDE SANITARIE", "AZIENDE SANITARIE TOSCANE", "SERVIZIO SANITARIO DELLA TOSCANA",
    "REFERENTI AZIENDALI", "TERZO SETTORE",
}

EXCLUDE_EXACT = {
    "OMS", "ISTAT", "UNIONE EUROPEA", "CONSIGLIO D'EUROPA", "CONSIGLIO D’EUROPA",
    "ORGANIZZAZIONE DELLE NAZIONI UNITE", "ORGANIZZAZIONE MONDIALE DELLA SANITA",
    "ORGANIZZAZIONE MONDIALE DELLA SANITÀ", "PRESIDENZA DEL CONSIGLIO DEI MINISTRI",
    "CONFERENZA UNIFICATA STATO-REGIONI", "COMUNITA DI TIPO FAMILIARE", "COMUNITÀ DI TIPO FAMILIARE",
}

TIPO_MAP = {
    "ASSOCIAZIONI DI PROMOZIONE SOCIALE": "Ente terzo settore - ETS (iscritto al RUNTS)",
    "ORGANIZZAZIONI DI VOLONTARIATO": "Ente terzo settore - ETS (iscritto al RUNTS)",
    "IMPRESE SOCIALI": "Ente terzo settore - ETS (iscritto al RUNTS)",
    "CAV/CENTRI ANTIVIOLENZA": "CAV/Centri Antiviolenza",
    "ALTRI ORDINI PROFESSIONALI": "Altri ordini professionali",
    "UNIONE DEI COMUNI": "Enti territoriali sovracomunali",
    "COMUNITA MONTANA": "Enti territoriali sovracomunali",
    "COMUNITÀ MONTANA": "Enti territoriali sovracomunali",
    "PROVINCE/CITTA METROPOLITANE": "Province/Città metropolitane",
    "PROVINCE/CITTÀ METROPOLITANE": "Province/Città metropolitane",
    "ORGANISMI DI PARITA": "Organismi di parità",
    "ORGANISMI DI PARITÀ": "Organismi di parità",
    "UNIVERSITA": "Università",
    "UNIVERSITÀ": "Università",
    "AMBITI DELLA PROGRAMMAZIONE SOCIALE E SOCIO-SANITARIA (AMBITI SOCIALI, PIANI DI ZONA, DISTRETTI SOCIO-SANITARI, SOCIETA DELLA SALUTE)": "Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)",
    "AMBITI DELLA PROGRAMMAZIONE SOCIALE E SOCIO-SANITARIA": "Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)",
}

REFERENCE_TABLE_30_TO_10 = [
  {
    "codice_soggetti_questionari": "1",
    "denominazione_soggetti_questionari": "CAV",
    "codice_aggregazione_2": "1",
    "descrizione_aggregazione_2": "CAV"
  },
  {
    "codice_soggetti_questionari": "2",
    "denominazione_soggetti_questionari": "Case Rifugio",
    "codice_aggregazione_2": "1",
    "descrizione_aggregazione_2": "CAV"
  },
  {
    "codice_soggetti_questionari": "3",
    "denominazione_soggetti_questionari": "Comuni",
    "codice_aggregazione_2": "3",
    "descrizione_aggregazione_2": "Servizi comunali"
  },
  {
    "codice_soggetti_questionari": "4",
    "denominazione_soggetti_questionari": "Polizia Municipale",
    "codice_aggregazione_2": "3",
    "descrizione_aggregazione_2": "Servizi comunali"
  },
  {
    "codice_soggetti_questionari": "5",
    "denominazione_soggetti_questionari": "Settore educativo comunale",
    "codice_aggregazione_2": "7",
    "descrizione_aggregazione_2": "Settore Educativo"
  },
  {
    "codice_soggetti_questionari": "6",
    "denominazione_soggetti_questionari": "Servizi sociali comunali",
    "codice_aggregazione_2": "3",
    "descrizione_aggregazione_2": "Servizi comunali"
  },
  {
    "codice_soggetti_questionari": "7",
    "denominazione_soggetti_questionari": "Servizio abusi e maltrattamenti comunale",
    "codice_aggregazione_2": "3",
    "descrizione_aggregazione_2": "Servizi comunali"
  },
  {
    "codice_soggetti_questionari": "8",
    "denominazione_soggetti_questionari": "Province/Città metropolitane",
    "codice_aggregazione_2": "10",
    "descrizione_aggregazione_2": "Province/Città metropolitane"
  },
  {
    "codice_soggetti_questionari": "9",
    "denominazione_soggetti_questionari": "Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)",
    "codice_aggregazione_2": "6",
    "descrizione_aggregazione_2": "Territorio"
  },
  {
    "codice_soggetti_questionari": "10",
    "denominazione_soggetti_questionari": "Regioni/province Autonome",
    "codice_aggregazione_2": "5",
    "descrizione_aggregazione_2": "Regioni/province Autonome"
  },
  {
    "codice_soggetti_questionari": "11",
    "denominazione_soggetti_questionari": "Ospedale (Pronto soccorso, ecc.)",
    "codice_aggregazione_2": "4",
    "descrizione_aggregazione_2": "settore sanitario"
  },
  {
    "codice_soggetti_questionari": "12",
    "denominazione_soggetti_questionari": "ASL (consultori familiari e altri servizi territoriali)",
    "codice_aggregazione_2": "4",
    "descrizione_aggregazione_2": "settore sanitario"
  },
  {
    "codice_soggetti_questionari": "13",
    "denominazione_soggetti_questionari": "Prefettura",
    "codice_aggregazione_2": "2",
    "descrizione_aggregazione_2": "Settore giudiziario"
  },
  {
    "codice_soggetti_questionari": "14",
    "denominazione_soggetti_questionari": "Questura",
    "codice_aggregazione_2": "2",
    "descrizione_aggregazione_2": "Settore giudiziario"
  },
  {
    "codice_soggetti_questionari": "15",
    "denominazione_soggetti_questionari": "Carabinieri/Polizia/altre forze dell'ordine",
    "codice_aggregazione_2": "2",
    "descrizione_aggregazione_2": "Settore giudiziario"
  },
  {
    "codice_soggetti_questionari": "16",
    "denominazione_soggetti_questionari": "Scuole/Ufficio scolastico provinciale e regionale",
    "codice_aggregazione_2": "7",
    "descrizione_aggregazione_2": "Settore Educativo"
  },
  {
    "codice_soggetti_questionari": "17",
    "denominazione_soggetti_questionari": "Procura Minorile/ Tribunale minorile",
    "codice_aggregazione_2": "2",
    "descrizione_aggregazione_2": "Settore giudiziario"
  },
  {
    "codice_soggetti_questionari": "18",
    "denominazione_soggetti_questionari": "Procura Ordinaria/Tribunale/Corte d'appello",
    "codice_aggregazione_2": "2",
    "descrizione_aggregazione_2": "Settore giudiziario"
  },
  {
    "codice_soggetti_questionari": "19",
    "denominazione_soggetti_questionari": "Ordine avvocati",
    "codice_aggregazione_2": "8",
    "descrizione_aggregazione_2": "associazionismo"
  },
  {
    "codice_soggetti_questionari": "20",
    "denominazione_soggetti_questionari": "Ordine psicologi e Ordine assistenti sociali",
    "codice_aggregazione_2": "8",
    "descrizione_aggregazione_2": "associazionismo"
  },
  {
    "codice_soggetti_questionari": "21",
    "denominazione_soggetti_questionari": "Ordine medici e odontoiatri e Ordine farmacisti",
    "codice_aggregazione_2": "8",
    "descrizione_aggregazione_2": "associazionismo"
  },
  {
    "codice_soggetti_questionari": "22",
    "denominazione_soggetti_questionari": "Altri ordini professionali (infermieri, ostetriche, giornalisti, commercialisti, ecc.)",
    "codice_aggregazione_2": "8",
    "descrizione_aggregazione_2": "associazionismo"
  },
  {
    "codice_soggetti_questionari": "23",
    "denominazione_soggetti_questionari": "Organismi di parità",
    "codice_aggregazione_2": "6",
    "descrizione_aggregazione_2": "Territorio"
  },
  {
    "codice_soggetti_questionari": "24",
    "denominazione_soggetti_questionari": "Ente terzo settore - ETS (iscritto al RUNTS)[1]",
    "codice_aggregazione_2": "8",
    "descrizione_aggregazione_2": "associazionismo"
  },
  {
    "codice_soggetti_questionari": "25",
    "denominazione_soggetti_questionari": "Ente terzo settore - ETS (iscritto al RUNTS) costituito da donne per le donne",
    "codice_aggregazione_2": "8",
    "descrizione_aggregazione_2": "associazionismo"
  },
  {
    "codice_soggetti_questionari": "26",
    "denominazione_soggetti_questionari": "Servizi per l'impiego",
    "codice_aggregazione_2": "6",
    "descrizione_aggregazione_2": "Territorio"
  },
  {
    "codice_soggetti_questionari": "27",
    "denominazione_soggetti_questionari": "Sindacati/Associazioni di categoria",
    "codice_aggregazione_2": "8",
    "descrizione_aggregazione_2": "associazionismo"
  },
  {
    "codice_soggetti_questionari": "28",
    "denominazione_soggetti_questionari": "Università",
    "codice_aggregazione_2": "7",
    "descrizione_aggregazione_2": "Settore Educativo"
  },
  {
    "codice_soggetti_questionari": "29",
    "denominazione_soggetti_questionari": "Associazioni che si occupano di programmi di prevenzione, recupero e trattamento per uomini maltrattanti",
    "codice_aggregazione_2": "8",
    "descrizione_aggregazione_2": "associazionismo"
  },
  {
    "codice_soggetti_questionari": "30",
    "denominazione_soggetti_questionari": "Altro",
    "codice_aggregazione_2": "9",
    "descrizione_aggregazione_2": "altro"
  }
]


def clean(s: Any) -> str:
    return str(s or "").strip()


def ascii_fold(s: str) -> str:
    s = clean(s)
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def normalize_text(s: Any) -> str:
    s = ascii_fold(clean(s))
    s = s.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-").replace("—", "-")
    s = re.sub(r"\[[^\]]+\]", "", s)
    s = re.sub(r"\(infermieri, ostetriche, giornalisti, commercialisti, ecc\.\)", "", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" ,.;:-")
    return s


def dedupe_adjacent_repeat_token(s: str) -> str:
    for token in ["Carabinieri", "Questura", "Prefettura", "Tribunale", "Procura", "Consultorio", "Ambulatorio", "Societa", "Società"]:
        s = re.sub(rf"\b({token})\1\b", r"\1", s, flags=re.I)
    return s


def norm_key(s: str) -> str:
    s = normalize_text(s)
    s = dedupe_adjacent_repeat_token(s)
    s = re.sub(r"\s+", " ", s).strip().upper()
    return s


def titleish(s: str) -> str:
    s = normalize_text(s)
    s = re.sub(r"\bParita\b", "Parità", s, flags=re.I)
    s = re.sub(r"\bCitta\b", "Città", s, flags=re.I)
    s = re.sub(r"\bSocieta\b", "Società", s, flags=re.I)
    s = re.sub(r"\bUniversita\b", "Università", s, flags=re.I)
    s = re.sub(r"\bUnita\b", "Unità", s, flags=re.I)
    s = re.sub(r"\s+", " ", s).strip(" -")
    return s


def get_entities_list_ref(file_item: dict) -> List[dict]:
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


def load_json(path: Path) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"JSON input non trovato: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(obj, dict) and "regioni" in obj:
        flat = []
        for reg_code, blocco in (obj.get("regioni") or {}).items():
            reg_code = str(reg_code).zfill(2)
            reg_name = REGION_CODE_TO_NAME.get(reg_code, "")
            for file_item in blocco.get("files", []) or []:
                item = dict(file_item)
                item["_regione_code"] = reg_code
                item["_regione_name"] = reg_name
                flat.append(item)
        return flat
    if isinstance(obj, list):
        flat = []
        for file_item in obj:
            if isinstance(file_item, dict):
                item = dict(file_item)
                m = FILE_REGION_RE.search(clean(item.get("file")))
                if m:
                    item["_regione_code"] = m.group(1)
                    item["_regione_name"] = REGION_CODE_TO_NAME.get(m.group(1), "")
                flat.append(item)
        return flat
    raise ValueError("Formato JSON non supportato")


def load_reference_table_from_embedded() -> pd.DataFrame:
    return pd.DataFrame(REFERENCE_TABLE_30_TO_10).fillna("")


def load_reference_table(path: Path) -> pd.DataFrame:
    if path.exists():
        suffix = path.suffix.lower()
        if suffix == ".csv":
            df = pd.read_csv(path, sep=";", encoding="utf-8-sig", dtype=str).fillna("")
        elif suffix in {".xlsx", ".xls"}:
            df = pd.read_excel(path, sheet_name="nuova aggregazione", dtype=str).fillna("")
        elif suffix == ".json":
            obj = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(obj, list):
                raise RuntimeError(f"Il file JSON di aggregazione deve contenere una lista di record: {path}")
            df = pd.DataFrame(obj).fillna("")
        else:
            raise RuntimeError(f"Formato tabella aggregazione non supportato: {path}")
    #else:
    #  df = load_reference_table_from_embedded()

    df.columns = [c.strip() for c in df.columns]
    required = {
        "codice_soggetti_questionari",
        "denominazione_soggetti_questionari",
        "codice_aggregazione_2",
        "descrizione_aggregazione_2",
    }
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"Colonne mancanti nella tabella aggregazione: {sorted(missing)}")

    df["tipo_norm"] = df["denominazione_soggetti_questionari"].map(normalize_text).map(str.lower)
    for col in [
        "codice_soggetti_questionari", "denominazione_soggetti_questionari",
        "codice_aggregazione_2", "descrizione_aggregazione_2"
    ]:
        df[col] = df[col].astype(str).str.strip()
    return df


def build_mapping_dict(df_map: pd.DataFrame) -> dict:
    mapping = {}
    for _, row in df_map.iterrows():
        mapping[clean(row["tipo_norm"]).lower()] = {
            "codice_soggetti_questionari": clean(row["codice_soggetti_questionari"]),
            "denominazione_soggetti_questionari": clean(row["denominazione_soggetti_questionari"]),
            "codice_aggregazione_2": clean(row["codice_aggregazione_2"]),
            "descrizione_aggregazione_2": clean(row["descrizione_aggregazione_2"]),
        }
    return mapping


def standardize_tipo(tipo: str) -> str:
    t = titleish(tipo)
    return TIPO_MAP.get(norm_key(t), t or "Altro")


def infer_file_region(file_name: str) -> str:
    m = FILE_REGION_RE.search(file_name)
    return REGION_CODE_TO_NAME.get(m.group(1), "") if m else ""


def parse_roles(ent: dict) -> List[str]:
    ruoli = ent.get("ruolo") or []
    if isinstance(ruoli, list):
        return [clean(x) for x in ruoli if clean(x)]
    if isinstance(ruoli, str) and clean(ruoli):
        return [clean(ruoli)]
    return []


def infer_province_from_name(name: str) -> Tuple[str, str, str]:
    n = norm_key(name)
    for p_norm, (prov, reg) in PROVINCE.items():
        patterns = [
            rf"\b(DI|DELLA|DEL)\s+{re.escape(p_norm)}\b",
            rf"\bPROVINCIA\s+DI\s+{re.escape(p_norm)}\b",
            rf"\bCITTA METROPOLITANA\s+DI\s+{re.escape(p_norm)}\b",
            rf"\bQUESTURA\s+DI\s+{re.escape(p_norm)}\b",
            rf"\bPREFETTURA\b.*\b{re.escape(p_norm)}\b",
            rf"\bTRIBUNALE\s+DI\s+{re.escape(p_norm)}\b",
            rf"\bPROCURA\b.*\b{re.escape(p_norm)}\b",
            rf"\bUSL\b.*\b{re.escape(p_norm)}\b",
            rf"\bSOCIETA DELLA SALUTE\b.*\b{re.escape(p_norm)}\b",
            rf"\bCENTRO DI ASCOLTO\b.*\b{re.escape(p_norm)}\b",
            rf"\bPUNTO DI ASCOLTO\b.*\b{re.escape(p_norm)}\b",
        ]
        if any(re.search(p, n) for p in patterns):
            return "", prov, reg
    return "", "", ""


def normalize_ocr_name(name: str) -> str:
    n = titleish(name)
    n = n.strip(" ,.;:-")
    n = dedupe_adjacent_repeat_token(n)
    n = re.sub(r"^\W+|\W+$", "", n)
    replacements = {
        r"\bC\.?I\.?S\.?M\.?A\.?I\.?\b": "CISMAI",
        r"\bC\.?I\.?F\.?\b": "CIF",
        r"\bCENTRO ITALIANO FEMMINILE\b": "CIF",
        r"\bQuesturaQuestura\b": "Questura",
        r"\bCarabinieriCarabinieri\b": "Carabinieri",
        r"\bCentro Pari Opportunita\b": "Centro Pari Opportunità",
        r"\bConsigliera di Parita\b": "Consigliera di Parità",
        r"\bConsigliera Provinciale di Parita\b": "Consigliera Provinciale di Parità",
        r"\bComunita Montana\b": "Comunità Montana",
        r"\bUfficio delle Consigliere di Parita\b": "Ufficio delle Consigliere di Parità",
    }
    for pat, repl in replacements.items():
        n = re.sub(pat, repl, n, flags=re.I)
    n = re.sub(r"\s+", " ", n).strip(" ,.;:-")
    return n


def canonicalize_name(name: str, tipo: str) -> str:
    n = normalize_ocr_name(name)
    nk = norm_key(n)
    aliases = {
        "CENTRO DI ASCOLTO C I F DI CARRARA": "Centro di Ascolto CIF di Carrara",
        "CENTRO DI ASCOLTO CIF DI CARRARA": "Centro di Ascolto CIF di Carrara",
        "CENTRO DI ASCOLTO CIF. DI CARRARA": "Centro di Ascolto CIF di Carrara",
        "CENTRO DI ASCOLTO CENTRO ITALIANO FEMMINILE DI CARRARA": "Centro di Ascolto CIF di Carrara",
        "CENTRO DI ASCOLTO SABINE DI MONTIGNOSO": "Centro di Ascolto Sabine di Montignoso",
        "CENTRO SABINE": "Centro di Ascolto Sabine di Montignoso",
        "CISMAI": "CISMAI – Coordinamento Italiano dei Servizi contro il Maltrattamento e l'Abuso all'Infanzia",
        "FF.OO": "Forze dell'ordine",
        "FFOO": "Forze dell'ordine",
        "FF OO": "Forze dell'ordine",
    }
    if nk in aliases:
        return aliases[nk]
    if nk in {"CENTRO ANTIVIOLENZA", "CENTRI ANTIVIOLENZA", "CENTRI ANTIVIOLENZA RICONOSCIUTI DALLA REGIONE TOSCANA"}:
        return "Centri Antiviolenza"
    if nk in {"SERVIZI SOCIALI", "SERVIZI SOCIALI COMUNALI"}:
        return "Servizi sociali"
    if nk in {"FORZE DELL'ORDINE", "FORZE DELL’ORDINE"}:
        return "Forze dell'ordine"
    if nk in {"SOCIETA DELLA SALUTE", "SOCIETÀ DELLA SALUTE"}:
        return "Società della Salute"
    if nk in {"ZONE SOCIO-SANITARIE", "ZONE SOCIO SANITARIE"}:
        return "Zone Socio-Sanitarie"
    if nk in {"AMBULATORIO", "CONSULTORIO", "CONSULTORIO PRINCIPALE", "PRONTO SOCCORSO", "UNITA OPERATIVA", "DIRETTORE SANITARIO"}:
        return titleish(n)
    if nk in BARE_COMUNI and not nk.startswith("COMUNE DI "):
        return f"Comune di {titleish(n)}"
    return n


def standardize_tipo_from_name(name: str, tipo: str) -> str:
    n = norm_key(name)
    t = standardize_tipo(tipo)

    if any(k in n for k in ["COMUNITA MONTANA", "COMUNITÀ MONTANA", "UNIONE DEI COMUNI", "UNIONE MONTANA", "COMUNITA COLLINARE", "COMUNITÀ COLLINARE"]):
        return "Enti territoriali sovracomunali"
    if n.startswith("PROVINCIA DI ") or n.startswith("CITTA METROPOLITANA DI ") or n == "CITTA METROPOLITANA DI FIRENZE":
        return "Province/Città metropolitane"
    if n.startswith("REGIONE ") or n.startswith("GIUNTA DELLA REGIONE "):
        return "Regioni/Province Autonome"
    if n.startswith("POLIZIA PROVINCIALE"):
        return "Polizia provinciale"
    if "SOCIETA DELLA SALUTE" in n or "ZONE SOCIO-SANITARIE" in n or "ZONE SOCIO SANITARIE" in n:
        return "Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)"
    if n.startswith("CONFERENZA DEI SINDACI ASL") or n.startswith("CONFERENZA DEL SINDACI ASL") or n.startswith("CONFERENZA ZONALE DEI SINDACI") or n.startswith("CONFERENZA DEI SINDACI DELLA ZONA") or n.startswith("FONDAZIONE TERRITORI SOCIALI"):
        return "Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)"
    if n.startswith("CENTRO PARI OPPORTUNITA") or n.startswith("CENTRO PARI OPPORTUNITÀ") or "CONSIGLIERA DI PARITA" in n or "CONSIGLIERA DI PARITÀ" in n or "UFFICIO DELLE CONSIGLIERE DI PARITA" in n or "UFFICIO DELLE CONSIGLIERE DI PARITÀ" in n:
        return "Organismi di parità"
    if n.startswith("ORDINE DEGLI AVVOCATI") or n.startswith("CPO DELL'ORDINE DEGLI AVVOCATI"):
        return "Ordine avvocati"
    if n.startswith("ORDINE DEI MEDICI") or n.startswith("ORDINE DEI FARMACISTI"):
        return "Ordine medici e odontoiatri e Ordine farmacisti"
    if n.startswith("ORDINE DEGLI PSICOLOGI") or n.startswith("ORDINE ASSISTENTI SOCIALI"):
        return "Ordine psicologi e Ordine assistenti sociali"
    if n.startswith("UNIVERSITA DEGLI STUDI") or n.startswith("UNIVERSITÀ DEGLI STUDI"):
        return "Università"
    if n.startswith("UFFICIO SCOLASTICO") or n.startswith("MIUR UFFICIO SCOLASTICO") or n == "SCUOLE":
        return "Scuole/Ufficio scolastico provinciale e regionale"
    if n.startswith("QUESTURA"):
        return "Questura"
    if n.startswith("PREFETTURA"):
        return "Prefettura"
    if "CARABINIERI" in n or "GUARDIA DI FINANZA" in n or n.startswith("POLIZIA DI STATO") or n == "FORZE DELL'ORDINE":
        return "Carabinieri/Polizia/altre forze dell'ordine"
    if n.startswith("PROCURA") or n.startswith("TRIBUNALE") or "CORTE D'APPELLO" in n or "CORTE D APPELLO" in n:
        return "Procura Minorile/ Tribunale minorile" if ("MINORENNI" in n or "MINORI" in n or "MINORILE" in n) else "Procura Ordinaria/Tribunale/Corte d'appello"
    if n.startswith("COMUNE DI ") or n.startswith("QUARTIERE ") or n in BARE_COMUNI:
        return "Comuni"
    if n.startswith("POLIZIA MUNICIPALE") or n.startswith("POLIZIE MUNICIPALI") or n.startswith("COMANDO POLIZIA MUNICIPALE"):
        return "Polizia Municipale"
    if "SERVIZI SOCIALI" in n or n.startswith("SEUS") or n.startswith("UTES") or n.startswith("REFERENTE EMERGENZA SOCIALE"):
        return "Servizi sociali comunali"
    if "USL" in n or "AZIENDA SANITARIA" in n or "AZIENDA OSPEDALIERA" in n or n.startswith("CONSULTORIO "):
        return "ASL (consultori familiari e altri servizi territoriali)"
    if n.startswith("PRONTO SOCCORSO DI ") or n.startswith("U.O PRONTO SOCCORSO") or n.startswith("OSPEDALE"):
        return "Ospedale (Pronto soccorso, ecc.)"
    if n.startswith("CENTRO PER L'IMPIEGO") or n.startswith("ARTI SERVIZI PER IL LAVORO"):
        return "Servizi per l'impiego"
    if n.startswith("CENTRO DI ASCOLTO UOMINI MALTRATTANTI") or n.startswith("CAM CENTRO UOMINI MALTRATTANTI") or n.startswith("CAM FIRENZE") or "UOMINI MALTRATTANTI" in n:
        return "Associazioni che si occupano di programmi di prevenzione, recupero e trattamento per uomini maltrattanti"
    if "CAV" in n or "ANTIVIOLENZA" in n:
        return "CAV"
    return t or "Altro"


def macro_categoria(tipo: str) -> str:
    t = norm_key(tipo)
    if t in {"CAV", "CASE RIFUGIO", "CAV/CENTRI ANTIVIOLENZA"}:
        return "CAV e protezione"
    if t in {"COMUNI", "POLIZIA MUNICIPALE", "SERVIZI SOCIALI COMUNALI", "SERVIZIO ABUSI E MALTRATTAMENTI COMUNALE"}:
        return "Servizi comunali"
    if t in {"PREFETTURA", "QUESTURA", "CARABINIERI/POLIZIA/ALTRE FORZE DELL'ORDINE", "PROCURA MINORILE/ TRIBUNALE MINORILE", "PROCURA ORDINARIA/TRIBUNALE/CORTE D'APPELLO"}:
        return "Settore giudiziario"
    if t in {"OSPEDALE (PRONTO SOCCORSO, ECC.)", "ASL (CONSULTORI FAMILIARI E ALTRI SERVIZI TERRITORIALI)"}:
        return "Settore sanitario"
    if t in {"SCUOLE/UFFICIO SCOLASTICO PROVINCIALE E REGIONALE", "SETTORE EDUCATIVO COMUNALE", "UNIVERSITÀ"}:
        return "Settore educativo"
    if t in {"ORDINE AVVOCATI", "ORDINE PSICOLOGI E ORDINE ASSISTENTI SOCIALI", "ORDINE MEDICI E ODONTOIATRI E ORDINE FARMACISTI", "ALTRI ORDINI PROFESSIONALI", "ENTE TERZO SETTORE - ETS (ISCRITTO AL RUNTS)", "ENTE TERZO SETTORE - ETS (ISCRITTO AL RUNTS) COSTITUITO DA DONNE PER LE DONNE", "SINDACATI/ASSOCIAZIONI DI CATEGORIA", "ASSOCIAZIONI CHE SI OCCUPANO DI PROGRAMMI DI PREVENZIONE, RECUPERO E TRATTAMENTO PER UOMINI MALTRATTANTI"}:
        return "Associazionismo e ordini"
    if t in {"AMBITI DELLA PROGRAMMAZIONE SOCIALE E SOCIO-SANITARIA (AMBITI SOCIALI, PIANI DI ZONA, DISTRETTI SOCIO-SANITARI, SOCIETÀ DELLA SALUTE)", "ORGANISMI DI PARITÀ", "SERVIZI PER L'IMPIEGO"}:
        return "Territorio"
    if t in {"REGIONI/PROVINCE AUTONOME", "PROVINCE/CITTÀ METROPOLITANE"}:
        return "Istituzioni territoriali"
    return "Altro"


def classify_observation(name: str, tipo: str, comune: str, provincia: str, regione: str) -> str:
    nk = norm_key(name)
    if nk in EXCLUDE_EXACT:
        return "da_escludere"
    if nk in GENERIC_EXACT:
        return "generico"
    generic_patterns = [
        r"^QUESTURA$", r"^PREFETTURA$", r"^PROCURA( DELLA REPUBBLICA)?$", r"^TRIBUNALE( ORDINARIO)?$",
        r"^AMBULATORIO$", r"^CONSULTORIO$", r"^PRONTO SOCCORSO$", r"^UNITA OPERATIVA$",
        r"^ZONE SOCIO[- ]SANITARIE$", r"^SERVIZI SOCIALI$", r"^CENTRI? ANTIVIOLENZA$",
        r"^CARABINIERI$", r"^GUARDIA DI FINANZA$", r"^POLIZIA DI STATO$",
    ]
    if any(re.fullmatch(p, nk) for p in generic_patterns):
        return "generico"
    if not (comune or provincia or regione):
        if tipo in {
            "ASL (consultori familiari e altri servizi territoriali)",
            "Ospedale (Pronto soccorso, ecc.)",
            "Ente terzo settore - ETS (iscritto al RUNTS)",
            "CAV", "Case Rifugio", "Servizi per l'impiego",
        }:
            return "valido_non_localizzato"
        return "generico"
    return "valido_localizzato"


def good_capofila(value: str) -> str:
    v = titleish(value)
    if not v or norm_key(v) in {"SI", "NO", "TRUE", "FALSE", "1", "0"}:
        return ""
    return v if len(v) >= 3 else ""


def extract_ruoli_gestione(ent: dict) -> List[str]:
    note = titleish(ent.get("note"))
    capofila = titleish(ent.get("ente_capofila"))
    text = f"{capofila} {note}".upper()
    ruoli = set()
    if any(x in text for x in ["GESTORE", "GESTISCE", "GESTIONE", "ENTE GESTORE", "SOGGETTO GESTORE", "SERVIZIO GESTITO", "INCARICATO DELLA GESTIONE"]):
        ruoli.add("gestione")
    if any(x in text for x in ["COORDINA", "COORDINAMENTO", "TAVOLO DI COORDINAMENTO", "COORDINARE", "PRESIEDE IL TAVOLO", "ENTE CAPOFILA", "CAPOFILA", "CABINA DI REGIA", "GOVERNANCE"]):
        ruoli.add("coordinamento")
    if any(x in text for x in ["MONITORA", "MONITORAGGIO", "VERIFICA", "OSSERVATORIO"]):
        ruoli.add("monitoraggio")
    return sorted(ruoli)


def choose_soggetto_incaricato(ent: dict) -> str:
    v = good_capofila(ent.get("ente_capofila"))
    return v or canonicalize_name(clean(ent.get("nome")), clean(ent.get("tipo")))


def map_tipo(tipo: str, mapping: dict) -> dict:
    tipo_norm = normalize_text(tipo).lower()
    if tipo_norm in mapping:
        return mapping[tipo_norm]
    aliases = {
        "cav/centri antiviolenza": "cav",
        "cav/centri antiviolenza": "cav",
        "cav/centri antiviolenza": "cav",
        "cav/centri antiviolenza": "cav",
        "cav/centri antiviolenza": "cav",
        "regioni/province autonome": "regioni/province autonome",
        "regioni/province autonome": "regioni/province autonome",
        "province/citta metropolitane": "province/citta metropolitane",
        "province/città metropolitane": "province/citta metropolitane",
        "procura minorile/tribunale minorile": "procura minorile/ tribunale minorile",
        "altri ordini professionali": "altri ordini professionali",
        "enti territoriali sovracomunali": "province/citta metropolitane",
        "organismi di parità": "organismi di parita",
        "università": "universita",
        "regioni/province autonome": "regioni/province autonome",
    }
    alias = aliases.get(tipo_norm)
    if alias and alias in mapping:
        return mapping[alias]
    return {
        "codice_soggetti_questionari": "30",
        "denominazione_soggetti_questionari": "Altro",
        "codice_aggregazione_2": "9",
        "descrizione_aggregazione_2": "altro",
    }


def derive_records(data: list, mapping: dict) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for i, file_item in enumerate(data, start=1):
        file_name = clean(file_item.get("file"))
        file_region = infer_file_region(file_name)
        reg_code_file = clean(file_item.get("_regione_code"))
        reg_name_file = clean(file_item.get("_regione_name")) or file_region
        entities = get_entities_list_ref(file_item)
        for j, ent in enumerate(entities, start=1):
            original_name = clean(ent.get("nome"))
            if not original_name:
                continue
            name = canonicalize_name(original_name, clean(ent.get("tipo")))
            tipo = standardize_tipo_from_name(name, clean(ent.get("tipo")))
            comune = clean(ent.get("comune")) or clean(ent.get("comune_matchato")) or clean(ent.get("comune_runts"))
            provincia = titleish(ent.get("provincia"))
            regione = titleish(ent.get("regione")) or reg_name_file
            if not provincia or not regione:
                _, p2, r2 = infer_province_from_name(name)
                provincia = provincia or p2
                regione = regione or r2
            stato = classify_observation(name, tipo, comune, provincia, regione)
            roles = parse_roles(ent)
            mapped = map_tipo(tipo, mapping)
            rows.append({
                "record_id": f"{i:03d}_{j:04d}",
                "file": file_name,
                "regione_codice": clean(ent.get("codice_regione")) or reg_code_file,
                "regione_finale": regione,
                "provincia_finale": provincia,
                "comune_finale": titleish(comune),
                "nome_originale": original_name,
                "nome_canonico": name,
                "nome_norm_stat": norm_key(name),
                "tipo_originale": clean(ent.get("tipo")) or "Altro",
                "tipo_standard": tipo,
                "macro_categoria": macro_categoria(tipo),
                "fonte_territorializzazione": (
                    "json" if clean(ent.get("provincia")) or clean(ent.get("regione")) or clean(ent.get("comune")) else
                    "runts" if clean(ent.get("comune_runts")) else
                    "nome" if provincia or regione else
                    "file" if file_region else
                    "none"
                ),
                "stato_osservazione": stato,
                "ruoli_documentali": "|".join(roles),
                "ruolo_attore": 1 if "attore" in roles else 0,
                "ruolo_firmatario": 1 if "firmatario" in roles else 0,
                "ruolo_proponente": 1 if "soggetto_proponente" in roles else 0,
                "ente_capofila": good_capofila(ent.get("ente_capofila")),
                "note": clean(ent.get("note")),
                "cf": clean(ent.get("cf")),
                "codice_soggetti_questionari": clean(mapped["codice_soggetti_questionari"]),
                "denominazione_soggetti_questionari": clean(mapped["denominazione_soggetti_questionari"]),
                "codice_aggregazione_2": clean(mapped["codice_aggregazione_2"]),
                "descrizione_aggregazione_2": clean(mapped["descrizione_aggregazione_2"]),
            })
    return rows


def dedupe_unique(rows: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    grouped: Dict[Tuple[str, str, str, str], List[Dict[str, Any]]] = defaultdict(list)
    for r in rows:
        key = (r["nome_norm_stat"], r["tipo_standard"], r["provincia_finale"], r["regione_finale"])
        grouped[key].append(r)

    unique_rows, dup_rows = [], []
    for key, group in grouped.items():
        base = dict(group[0])
        base["n_record_aggregati"] = len(group)
        base["files"] = " | ".join(sorted({g["file"] for g in group if g["file"]}))
        base["ruoli_documentali_aggregati"] = "|".join(sorted({x for g in group for x in g["ruoli_documentali"].split("|") if x}))
        base["ruolo_attore"] = max(g["ruolo_attore"] for g in group)
        base["ruolo_firmatario"] = max(g["ruolo_firmatario"] for g in group)
        base["ruolo_proponente"] = max(g["ruolo_proponente"] for g in group)
        unique_rows.append(base)
        if len(group) > 1:
            for g in group:
                dup_rows.append({"chiave": "||".join(key), **g})

    unique_rows.sort(key=lambda x: (x["macro_categoria"], x["tipo_standard"], x["nome_canonico"], x["provincia_finale"], x["regione_finale"]))
    return unique_rows, dup_rows


def build_attori_regionali_disaggregati(valid_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for r in valid_rows:
        if not (r["ruolo_attore"] or not r.get("ruoli_documentali_aggregati")):
            continue
        rows.append({
            "regione_codice": r.get("regione_codice", ""),
            "regione": r["regione_finale"],
            "provincia": r["provincia_finale"],
            "macro_categoria": r["macro_categoria"],
            "tipo_standard": r["tipo_standard"],
            "nome_canonico": r["nome_canonico"],
            "file": r.get("files", r.get("file", "")),
            "n_record_aggregati": r.get("n_record_aggregati", 1),
        })
    rows.sort(key=lambda x: (x["regione"], x["macro_categoria"], x["tipo_standard"], x["nome_canonico"]))
    return rows


def aggregate_classification_30(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["regione_codice", "regione", "codice_soggetti_questionari", "denominazione_soggetti_questionari", "n_attori", "attori", "n_file", "files"])
    grouped = (
        df.groupby(["regione_codice", "regione_finale", "codice_soggetti_questionari", "denominazione_soggetti_questionari"], dropna=False)
        .agg(
            n_attori=("nome_canonico", lambda s: s.astype(str).str.strip().nunique()),
            attori=("nome_canonico", lambda s: " | ".join(sorted(set(x for x in s.astype(str) if x.strip())))),
            n_file=("file", lambda s: s.astype(str).str.strip().nunique()),
            files=("file", lambda s: " | ".join(sorted(set(x for x in s.astype(str) if x.strip())))),
        )
        .reset_index()
        .rename(columns={"regione_finale": "regione"})
    )
    grouped["codice_soggetti_questionari_num"] = pd.to_numeric(grouped["codice_soggetti_questionari"], errors="coerce")
    grouped = grouped.sort_values(["regione_codice", "codice_soggetti_questionari_num", "denominazione_soggetti_questionari"], kind="stable").drop(columns=["codice_soggetti_questionari_num"])
    return grouped


def aggregate_classification_10(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["regione_codice", "regione", "codice_aggregazione_2", "descrizione_aggregazione_2", "n_attori", "attori", "n_file", "files"])
    grouped = (
        df.groupby(["regione_codice", "regione_finale", "codice_aggregazione_2", "descrizione_aggregazione_2"], dropna=False)
        .agg(
            n_attori=("nome_canonico", lambda s: s.astype(str).str.strip().nunique()),
            attori=("nome_canonico", lambda s: " | ".join(sorted(set(x for x in s.astype(str) if x.strip())))),
            n_file=("file", lambda s: s.astype(str).str.strip().nunique()),
            files=("file", lambda s: " | ".join(sorted(set(x for x in s.astype(str) if x.strip())))),
        )
        .reset_index()
        .rename(columns={"regione_finale": "regione"})
    )
    grouped["codice_aggregazione_2_num"] = pd.to_numeric(grouped["codice_aggregazione_2"], errors="coerce")
    grouped = grouped.sort_values(["regione_codice", "codice_aggregazione_2_num", "descrizione_aggregazione_2"], kind="stable").drop(columns=["codice_aggregazione_2_num"])
    return grouped


def aggregate_macro_30(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["codice_soggetti_questionari", "denominazione_soggetti_questionari", "n_attori", "attori", "n_regioni", "regioni", "n_file", "files"])
    grouped = (
        df.groupby(["codice_soggetti_questionari", "denominazione_soggetti_questionari"], dropna=False)
        .agg(
            n_attori=("nome_canonico", lambda s: s.astype(str).str.strip().nunique()),
            attori=("nome_canonico", lambda s: " | ".join(sorted(set(x for x in s.astype(str) if x.strip())))),
            n_regioni=("regione_finale", lambda s: s.astype(str).str.strip().nunique()),
            regioni=("regione_finale", lambda s: " | ".join(sorted(set(x for x in s.astype(str) if x.strip())))),
            n_file=("file", lambda s: s.astype(str).str.strip().nunique()),
            files=("file", lambda s: " | ".join(sorted(set(x for x in s.astype(str) if x.strip())))),
        )
        .reset_index()
    )
    grouped["codice_soggetti_questionari_num"] = pd.to_numeric(grouped["codice_soggetti_questionari"], errors="coerce")
    grouped = grouped.sort_values(["codice_soggetti_questionari_num", "denominazione_soggetti_questionari"], kind="stable").drop(columns=["codice_soggetti_questionari_num"])
    return grouped


def aggregate_macro_10(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=["codice_aggregazione_2", "descrizione_aggregazione_2", "n_attori", "attori", "n_regioni", "regioni", "n_file", "files"])
    grouped = (
        df.groupby(["codice_aggregazione_2", "descrizione_aggregazione_2"], dropna=False)
        .agg(
            n_attori=("nome_canonico", lambda s: s.astype(str).str.strip().nunique()),
            attori=("nome_canonico", lambda s: " | ".join(sorted(set(x for x in s.astype(str) if x.strip())))),
            n_regioni=("regione_finale", lambda s: s.astype(str).str.strip().nunique()),
            regioni=("regione_finale", lambda s: " | ".join(sorted(set(x for x in s.astype(str) if x.strip())))),
            n_file=("file", lambda s: s.astype(str).str.strip().nunique()),
            files=("file", lambda s: " | ".join(sorted(set(x for x in s.astype(str) if x.strip())))),
        )
        .reset_index()
    )
    grouped["codice_aggregazione_2_num"] = pd.to_numeric(grouped["codice_aggregazione_2"], errors="coerce")
    grouped = grouped.sort_values(["codice_aggregazione_2_num", "descrizione_aggregazione_2"], kind="stable").drop(columns=["codice_aggregazione_2_num"])
    return grouped


def write_csv(rows: List[Dict[str, Any]], path: Path):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


def write_graphml(valid_rows: List[Dict[str, Any]], output_csv: Path, output_graphml: Path):
    edge_rows = []
    if nx is None:
        write_csv(edge_rows, output_csv)
        return
    edge_counter = Counter()
    node_counter = Counter()
    by_file = defaultdict(list)
    for r in valid_rows:
        if r["ruolo_attore"] or not r.get("ruoli_documentali_aggregati"):
            by_file[r["file"]].append(r["nome_canonico"])
    for file_name, names in by_file.items():
        names = sorted(set(names))
        for a in names:
            node_counter[a] += 1
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                a1, a2 = names[i], names[j]
                edge_rows.append({"file": file_name, "attore_1": a1, "attore_2": a2})
                edge_counter[(a1, a2)] += 1
    write_csv(edge_rows, output_csv)
    G = nx.Graph()
    for attore, n_files in node_counter.items():
        G.add_node(attore, label=attore, n_files=n_files)
    for (a1, a2), w in edge_counter.items():
        G.add_edge(a1, a2, weight=w)
    nx.write_graphml(G, output_graphml)


def write_readme(out_dir: Path, input_json: Path, ref_path: Path, df_ref: pd.DataFrame, rows: List[Dict[str, Any]], unique_rows: List[Dict[str, Any]], valid_rows: List[Dict[str, Any]]):
    lines = [
        "SCRIPT INTEGRATO: PULIZIA + CLASSIFICAZIONE 30 + AGGREGAZIONE 10",
        f"Input JSON: {input_json}",
        f"Tabella aggregazione: {ref_path if ref_path.exists() else 'embedded'}",
        f"Numero classi sorgente (30): {df_ref['denominazione_soggetti_questionari'].nunique()}",
        f"Numero classi aggregate finali (10): {df_ref['descrizione_aggregazione_2'].nunique()}",
        f"Record elaborati: {len(rows)}",
        f"Soggetti unici: {len(unique_rows)}",
        f"Soggetti validi localizzati: {len(valid_rows)}",
        "",
        "Output principali:",
        "- soggetti_puliti_per_record.csv",
        "- soggetti_unici_puliti.csv",
        "- soggetti_unici_classificazione_30.csv",
        "- soggetti_unici_classificazione_10.csv",
        "- attori_regionali_classificazione_30.csv",
        "- attori_regionali_classificazione_10.csv",
        "- attori_macro_classificazione_30.csv",
        "- attori_macro_classificazione_10.csv",
        "- report_sintetico.txt",
        "- report_strutturato.json",
    ]
    (out_dir / "README_integrato.txt").write_text("\n".join(lines), encoding="utf-8")



def write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")


def export_json_outputs(out_dir: Path, rows: List[Dict[str, Any]], unique_rows: List[Dict[str, Any]], valid_rows: List[Dict[str, Any]], df_ref: pd.DataFrame) -> None:
    ref_records = df_ref[[
        "codice_soggetti_questionari",
        "denominazione_soggetti_questionari",
        "codice_aggregazione_2",
        "descrizione_aggregazione_2",
    ]].fillna("").to_dict(orient="records")

    payload_30 = {
        "totale_record_soggetti": len(rows),
        "totale_soggetti_unici": len(unique_rows),
        "totale_soggetti_validi_localizzati": len(valid_rows),
        "classificazione": "30_classi",
        "records": [
            {
                "regione_codice": r.get("regione_codice", ""),
                "regione": r.get("regione_finale", ""),
                "provincia": r.get("provincia_finale", ""),
                "comune": r.get("comune_finale", ""),
                "nome_canonico": r.get("nome_canonico", ""),
                "tipo_standard": r.get("tipo_standard", ""),
                "codice_soggetti_questionari": r.get("codice_soggetti_questionari", ""),
                "denominazione_soggetti_questionari": r.get("denominazione_soggetti_questionari", ""),
                "macro_categoria": r.get("macro_categoria", ""),
                "stato_osservazione": r.get("stato_osservazione", ""),
                "files": r.get("files", []),
                "n_record_aggregati": r.get("n_record_aggregati", 0),
            }
            for r in unique_rows
        ],
    }

    payload_10 = {
        "totale_record_soggetti": len(rows),
        "totale_soggetti_unici": len(unique_rows),
        "totale_soggetti_validi_localizzati": len(valid_rows),
        "classificazione": "10_classi_aggregate",
        "records": [
            {
                "regione_codice": r.get("regione_codice", ""),
                "regione": r.get("regione_finale", ""),
                "provincia": r.get("provincia_finale", ""),
                "comune": r.get("comune_finale", ""),
                "nome_canonico": r.get("nome_canonico", ""),
                "tipo_standard": r.get("tipo_standard", ""),
                "codice_aggregazione_2": r.get("codice_aggregazione_2", ""),
                "descrizione_aggregazione_2": r.get("descrizione_aggregazione_2", ""),
                "macro_categoria": r.get("macro_categoria", ""),
                "stato_osservazione": r.get("stato_osservazione", ""),
                "files": r.get("files", []),
                "n_record_aggregati": r.get("n_record_aggregati", 0),
            }
            for r in unique_rows
        ],
    }

    write_json(out_dir / "classificazione_30.json", payload_30)
    write_json(out_dir / "aggregazione_10.json", payload_10)





def build_tipologie_numerosita_30(unique_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    counts = Counter(clean(r.get("denominazione_soggetti_questionari") or r.get("tipo_standard")) for r in unique_rows if clean(r.get("denominazione_soggetti_questionari") or r.get("tipo_standard")))
    return [{"tipo": k, "numerosita": v} for k, v in counts.most_common()]


def build_soggetti_gestione_monitoraggio(unique_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    keys = ["capofila", "coordin", "monitor", "gest", "referent", "segreteria tecnica"]
    for r in unique_rows:
        hay = " ".join([
            clean(r.get("ente_capofila")),
            clean(r.get("note")),
            clean(r.get("ruoli_documentali_aggregati")),
        ]).lower()
        if any(k in hay for k in keys):
            rows.append({
                "file": clean(r.get("files") or r.get("file")),
                "files": clean(r.get("files") or r.get("file")),
                "regione": clean(r.get("regione_finale")),
                "provincia": clean(r.get("provincia_finale")),
                "comune": clean(r.get("comune_finale")),
                "soggetto_incaricato": clean(r.get("nome_canonico")),
                "nome_canonico": clean(r.get("nome_canonico")),
                "tipo_30": clean(r.get("denominazione_soggetti_questionari") or r.get("tipo_standard")),
                "tipo_10": clean(r.get("descrizione_aggregazione_2")),
                "ente_capofila": clean(r.get("ente_capofila")),
                "note": clean(r.get("note")),
            })
    return rows


def build_soggetti_proponenti_rows(unique_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for r in unique_rows:
        if int(r.get("ruolo_proponente", 0) or 0) == 1:
            rows.append({
                "file": clean(r.get("files") or r.get("file")),
                "files": clean(r.get("files") or r.get("file")),
                "regione": clean(r.get("regione_finale")),
                "soggetto_proponente": clean(r.get("nome_canonico")),
                "nome_canonico": clean(r.get("nome_canonico")),
                "tipo_30": clean(r.get("denominazione_soggetti_questionari") or r.get("tipo_standard")),
                "tipo_10": clean(r.get("descrizione_aggregazione_2")),
            })
    return rows


def build_firmatari_rows(unique_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for r in unique_rows:
        if int(r.get("ruolo_firmatario", 0) or 0) == 1:
            rows.append({
                "file": clean(r.get("files") or r.get("file")),
                "files": clean(r.get("files") or r.get("file")),
                "regione": clean(r.get("regione_finale")),
                "firmatario": clean(r.get("nome_canonico")),
                "tipo_30": clean(r.get("denominazione_soggetti_questionari") or r.get("tipo_standard")),
                "tipo_10": clean(r.get("descrizione_aggregazione_2")),
            })
    return rows


def build_attori_coinvolti_10(valid_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    groups = defaultdict(list)
    files = defaultdict(set)
    for r in valid_rows:
        if r.get("ruolo_attore") or not clean(r.get("ruoli_documentali_aggregati")):
            agg10 = clean(r.get("descrizione_aggregazione_2")) or "ND"
            groups[agg10].append(clean(r.get("nome_canonico")))
            for f in str(r.get("files", "")).split(" | "):
                f = clean(f)
                if f:
                    files[agg10].add(f)
    out = []
    for agg10, nomi in groups.items():
        out.append({
            "aggregazione_10": agg10,
            "numerosita": len(sorted(set([n for n in nomi if n]))),
            "attori": sorted(set([n for n in nomi if n])),
            "files": sorted(files[agg10]),
        })
    out.sort(key=lambda x: (-x["numerosita"], x["aggregazione_10"]))
    return out


def build_attori_per_regione_aggregazione_10_rows(valid_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    reg_agg10_attori = defaultdict(lambda: defaultdict(set))
    reg_agg10_files = defaultdict(lambda: defaultdict(set))
    for r in valid_rows:
        reg = clean(r.get("regione_finale")) or "ND"
        agg10 = clean(r.get("descrizione_aggregazione_2")) or "ND"
        nome = clean(r.get("nome_canonico"))
        if nome:
            reg_agg10_attori[reg][agg10].add(nome)
        for f in str(r.get("files", "")).split(" | "):
            f = clean(f)
            if f:
                reg_agg10_files[reg][agg10].add(f)
    rows = []
    for reg in sorted(reg_agg10_attori.keys()):
        for agg10 in sorted(reg_agg10_attori[reg].keys()):
            rows.append({
                "regione": reg,
                "aggregazione_10": agg10,
                "numerosita": len(reg_agg10_attori[reg][agg10]),
                "attori": sorted(reg_agg10_attori[reg][agg10]),
                "files": sorted(reg_agg10_files[reg][agg10]),
            })
    return rows


def build_attori_disaggregati_10_30_rows(valid_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for r in valid_rows:
        rows.append({
            "regione": clean(r.get("regione_finale")),
            "provincia": clean(r.get("provincia_finale")),
            "comune": clean(r.get("comune_finale")),
            "nome_canonico": clean(r.get("nome_canonico")),
            "tipo_30": clean(r.get("denominazione_soggetti_questionari") or r.get("tipo_standard")),
            "tipo_10": clean(r.get("descrizione_aggregazione_2")),
            "files": clean(r.get("files")),
            "n_record_aggregati": r.get("n_record_aggregati", 1),
        })
    return rows


def build_order_maps(df_ref: pd.DataFrame):
    df_tmp = df_ref[["codice_soggetti_questionari", "denominazione_soggetti_questionari", "codice_aggregazione_2", "descrizione_aggregazione_2"]].copy()
    df_tmp["codice_soggetti_questionari"] = pd.to_numeric(df_tmp["codice_soggetti_questionari"], errors="coerce")
    df_tmp["codice_aggregazione_2"] = pd.to_numeric(df_tmp["codice_aggregazione_2"], errors="coerce")
    order30 = [str(x) for x in df_tmp.sort_values(["codice_soggetti_questionari", "denominazione_soggetti_questionari"])["denominazione_soggetti_questionari"].drop_duplicates().tolist()]
    order10 = [str(x) for x in df_tmp.sort_values(["codice_aggregazione_2", "descrizione_aggregazione_2"])["descrizione_aggregazione_2"].drop_duplicates().tolist()]
    return order30, order10

def build_report_struct(input_json: Path, aggregation_file: Path, qc_rows: List[Dict[str, Any]], unique_rows: List[Dict[str, Any]], valid_rows: List[Dict[str, Any]], dup_rows: List[Dict[str, Any]], df_ref: pd.DataFrame) -> Dict[str, Any]:
    order30, order10 = build_order_maps(df_ref)
    aggregazioni_10 = Counter(clean(r.get("descrizione_aggregazione_2")) for r in unique_rows if clean(r.get("descrizione_aggregazione_2")))
    tipologie_30 = Counter(clean(r.get("denominazione_soggetti_questionari") or r.get("tipo_standard")) for r in unique_rows if clean(r.get("denominazione_soggetti_questionari") or r.get("tipo_standard")))

    raggr_regionale = []
    tipologie_per_regione = []
    aggregazioni_10_per_regione = []
    attori_per_regione_aggregazione_10 = []

    reg_agg10 = defaultdict(Counter)
    reg_tipo30 = defaultdict(Counter)
    reg_agg10_attori = defaultdict(lambda: defaultdict(set))
    reg_agg10_files = defaultdict(lambda: defaultdict(set))

    for r in valid_rows:
        reg = clean(r.get("regione_finale")) or "ND"
        agg10 = clean(r.get("descrizione_aggregazione_2")) or "ND"
        tipo30 = clean(r.get("denominazione_soggetti_questionari") or r.get("tipo_standard")) or "ND"
        nome = clean(r.get("nome_canonico"))
        reg_agg10[reg][agg10] += 1
        reg_tipo30[reg][tipo30] += 1
        if nome:
            reg_agg10_attori[reg][agg10].add(nome)
        for f in str(r.get("files", "")).split(" | "):
            f = clean(f)
            if f:
                reg_agg10_files[reg][agg10].add(f)

    for reg in sorted(reg_agg10.keys()):
        totale = sum(reg_agg10[reg].values())
        raggr_regionale.append({
            "regione": reg,
            "totale_attori": totale,
            "aggregazioni_10": [
                {"aggregazione_10": agg, "numerosita": reg_agg10[reg].get(agg, 0)}
                for agg in order10
            ],
        })

    for reg in sorted(reg_tipo30.keys()):
        tipologie_per_regione.append({
            "regione": reg,
            "tipologie_30": [
                {"tipo": t, "numerosita": reg_tipo30[reg].get(t, 0)}
                for t in order30
            ]
        })

    for reg in sorted(reg_agg10.keys()):
        aggregazioni_10_per_regione.append({
            "regione": reg,
            "aggregazioni_10": [
                {"aggregazione_10": a, "numerosita": reg_agg10[reg].get(a, 0)}
                for a in order10
            ]
        })

    for reg in sorted(reg_agg10_attori.keys()):
        for agg10 in order10:
            attori_per_regione_aggregazione_10.append({
                "regione": reg,
                "aggregazione_10": agg10,
                "numerosita": len(reg_agg10_attori[reg].get(agg10, set())),
                "attori": sorted(reg_agg10_attori[reg].get(agg10, set())),
                "files": sorted(reg_agg10_files[reg].get(agg10, set())),
            })

    return {
        "input_json": str(input_json),
        "tabella_aggregazione": str(aggregation_file),
        "report_controlli_qualita": qc_rows,
        "aggregazione_10_numerosita": [
            {"aggregazione_10": k, "numerosita": aggregazioni_10.get(k, 0)}
            for k in order10
        ],
        "tipologia_30_numerosita": [
            {"tipo": k, "numerosita": tipologie_30.get(k, 0)}
            for k in order30
        ],
        "raggruppamento_regionale": raggr_regionale,
        "aggregazioni_10_per_regione": aggregazioni_10_per_regione,
        "tipologie_30_per_regione": tipologie_per_regione,
        "attori_per_regione_aggregazione_10": attori_per_regione_aggregazione_10,
        "attori_coinvolti": build_attori_coinvolti_10(valid_rows),
        "soggetti_incaricati_gestione_monitoraggio_coordinamento": build_soggetti_gestione_monitoraggio(unique_rows),
        "soggetti_proponenti": build_soggetti_proponenti_rows(unique_rows),
        "firmatari": build_firmatari_rows(unique_rows),
        "attori_disaggregati_10_30": build_attori_disaggregati_10_30_rows(valid_rows),
        "potenziali_duplicati_record": len(dup_rows),
    }



def write_report_sintetico(report: Dict[str, Any], out_txt: Path) -> None:
    qc_map = {r["indicatore"]: r["valore"] for r in report.get("report_controlli_qualita", [])}
    lines = []
    lines.append("REPORT SOGGETTI INTEGRATO")
    lines.append(f"Input JSON: {report.get('input_json', '')}")
    lines.append(f"Tabella aggregazione: {report.get('tabella_aggregazione', '')}")
    lines.append(f"Totale record soggetti: {qc_map.get('totale_record_soggetti', 0)}")
    lines.append(f"Totale soggetti unici: {qc_map.get('totale_soggetti_unici', 0)}")
    lines.append("")

    lines.append("0.1) CLASSIFICAZIONE 10 - NUMEROSITÀ COMPLESSIVA")
    for r in report.get("aggregazione_10_numerosita", []):
        lines.append(f"- {r['aggregazione_10']}: {r['numerosita']}")
    lines.append("")

    lines.append("0.2) CLASSIFICAZIONE 30 - NUMEROSITÀ COMPLESSIVA")
    for r in report.get("tipologia_30_numerosita", []):
        lines.append(f"- {r['tipo']}: {r['numerosita']}")
    lines.append("")

    lines.append("1) CONTROLLI QUALITÀ")
    for r in report.get("report_controlli_qualita", []):
        lines.append(f"- {r['indicatore']}: {r['valore']}")
    lines.append("")

    lines.append("2) RAGGRUPPAMENTO REGIONALE (10 CLASSI)")
    for blocco in report.get("raggruppamento_regionale", []):
        lines.append("")
        lines.append(f"REGIONE: {blocco['regione']}")
        lines.append(f"Totale attori: {blocco['totale_attori']}")
        for r in blocco.get("aggregazioni_10", []):
            lines.append(f"  - {r['aggregazione_10']}: {r['numerosita']}")
    lines.append("")

    lines.append("3) TIPOLOGIE PULITE PER REGIONE (30 CLASSI)")
    for blocco in report.get("tipologie_30_per_regione", []):
        lines.append("")
        lines.append(f"REGIONE: {blocco['regione']}")
        for r in blocco.get("tipologie_30", []):
            lines.append(f"- {r['tipo']}: {r['numerosita']}")
    lines.append("")

    lines.append("4) ATTORI COINVOLTI PULITI PER REGIONE (10 CLASSI)")
    current_reg = None
    for blocco in report.get("attori_per_regione_aggregazione_10", []):
        reg = blocco["regione"]
        if reg != current_reg:
            lines.append("")
            lines.append(f"REGIONE: {reg}")
            current_reg = reg
        lines.append("")
        lines.append(f"{blocco['aggregazione_10']} ({blocco['numerosita']}):")
        if blocco.get("files"):
            lines.append(f"  file: {', '.join(blocco['files'])}")
        for attore in blocco.get("attori", []):
            lines.append(f"  - {attore}")
    lines.append("")

    lines.append("5) ATTORI COINVOLTI - RIEPILOGO COMPLESSIVO")
    attori_coinvolti = report.get("attori_coinvolti", [])
    if not attori_coinvolti:
        lines.append("- Nessun dato disponibile.")
    else:
        for row in attori_coinvolti:
            label = row.get("aggregazione_10") or row.get("macro_categoria") or row.get("tipo") or "ND"
            lines.append(f"- {label}: {row.get('numerosita', 0)}")
            if row.get("files"):
                lines.append(f"  file: {', '.join(row.get('files', []))}")
            for attore in row.get("attori", []):
                lines.append(f"  - {attore}")
    lines.append("")

    lines.append("6) SOGGETTI INCARICATI GESTIONE / MONITORAGGIO / COORDINAMENTO")
    gestione_rows = report.get("soggetti_incaricati_gestione_monitoraggio_coordinamento", []) or report.get("soggetti_gestione", [])
    gestione_reg = defaultdict(lambda: defaultdict(list))
    for row in gestione_rows:
        reg = row.get("regione", "") or "ND"
        file_name = row.get("file", "") or "ND"
        gestione_reg[reg][file_name].append(row)
    if not gestione_reg:
        lines.append("- Nessun soggetto rilevato.")
    else:
        for reg in sorted(gestione_reg.keys()):
            lines.append("")
            lines.append(f"REGIONE: {reg}")
            for file_name in sorted(gestione_reg[reg].keys()):
                lines.append("")
                lines.append(f"  FILE: {file_name}")
                for row in sorted(gestione_reg[reg][file_name], key=lambda x: (x.get("descrizione_aggregazione_2", ""), x.get("soggetto_incaricato", ""))):
                    sogg = row.get("soggetto_incaricato", "") or row.get("nome_entita", "") or row.get("nome_canonico", "")
                    lines.append(f"    - {sogg}")
                    if row.get("nome_entita"):
                        lines.append(f"      entità: {row.get('nome_entita', '')}")
                    tipo = row.get("denominazione_soggetti_questionari") or row.get("tipo_entita") or row.get("tipo_standard") or ""
                    if tipo:
                        lines.append(f"      tipo: {tipo}")
                    agg10 = row.get("descrizione_aggregazione_2", "")
                    if agg10:
                        lines.append(f"      aggregazione_10: {agg10}")
                    ruoli = row.get("ruoli", "") or row.get("ruoli_documentali_aggregati", "")
                    if ruoli:
                        lines.append(f"      ruoli: {ruoli}")
                    ente_capofila = row.get("ente_capofila", "")
                    note = row.get("note", "")
                    if ente_capofila:
                        lines.append(f"      ente_capofila: {ente_capofila}")
                    if note:
                        lines.append(f"      note: {note}")
    lines.append("")

    lines.append("7) SOGGETTI PROPONENTI PER REGIONE")
    proponenti_rows = report.get("soggetti_proponenti", [])
    proponenti_reg = defaultdict(lambda: defaultdict(list))
    for row in proponenti_rows:
        reg = row.get("regione", "") or "ND"
        file_name = row.get("file", "") or "ND"
        proponenti_reg[reg][file_name].append(row)
    if not proponenti_reg:
        lines.append("- Nessun soggetto proponente rilevato.")
    else:
        for reg in sorted(proponenti_reg.keys()):
            lines.append("")
            lines.append(f"REGIONE: {reg}")
            for file_name in sorted(proponenti_reg[reg].keys()):
                lines.append("")
                lines.append(f"  FILE: {file_name}")
                soggetti = sorted({r.get("soggetto_proponente", "") for r in proponenti_reg[reg][file_name] if r.get("soggetto_proponente")})
                for soggetto in soggetti:
                    lines.append(f"    - {soggetto}")
    lines.append("")

    lines.append("8) FIRMATARI PER REGIONE")
    firmatari_rows = report.get("firmatari", [])
    firmatari_reg = defaultdict(lambda: defaultdict(list))
    for row in firmatari_rows:
        reg = row.get("regione", "") or "ND"
        file_name = row.get("file", "") or "ND"
        firmatari_reg[reg][file_name].append(row)
    if not firmatari_reg:
        lines.append("- Nessun firmatario rilevato.")
    else:
        for reg in sorted(firmatari_reg.keys()):
            lines.append("")
            lines.append(f"REGIONE: {reg}")
            for file_name in sorted(firmatari_reg[reg].keys()):
                lines.append("")
                lines.append(f"  FILE: {file_name}")
                soggetti = sorted({r.get("firmatario", "") for r in firmatari_reg[reg][file_name] if r.get("firmatario")})
                for soggetto in soggetti:
                    lines.append(f"    - {soggetto}")
    lines.append("")

    lines.append("9) RIEPILOGO GLOBALE PER AGGREGAZIONE 10")
    riepilogo_10 = report.get("aggregazione_10_numerosita", [])
    if not riepilogo_10:
        lines.append("- Nessun dato disponibile.")
    else:
        for row in riepilogo_10:
            lines.append(f"- {row.get('aggregazione_10', 'ND')}: {row.get('numerosita', 0)}")
    lines.append("")

    out_txt.write_text("\n".join(lines), encoding="utf-8")



def main() -> None:
    parser = argparse.ArgumentParser(description="Integra pulizia soggetti, classificazione 30 classi e aggregazione 10 classi.")
    parser.add_argument("--input-json", default=str(INPUT_JSON))
    parser.add_argument("--aggregation-file", default=str(AGGREGATION_FILE))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()

    input_json = Path(args.input_json)
    aggregation_file = Path(args.aggregation_file)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    df_ref = load_reference_table(aggregation_file)
    mapping = build_mapping_dict(df_ref)
    data = load_json(input_json)

    rows = derive_records(data, mapping)
    unique_rows, dup_rows = dedupe_unique(rows)
    valid_rows = [r for r in unique_rows if r["stato_osservazione"] == "valido_localizzato"]
    diag_rows = [r for r in unique_rows if r["stato_osservazione"] != "valido_localizzato"]

    write_csv(rows, out_dir / "soggetti_puliti_per_record.csv")
    write_csv(unique_rows, out_dir / "soggetti_unici_puliti.csv")
    write_csv(diag_rows, out_dir / "soggetti_generici_non_localizzati.csv")
    write_csv(dup_rows, out_dir / "soggetti_duplicati_potenziali.csv")

    df_valid = pd.DataFrame(valid_rows)
    df_unique = pd.DataFrame(unique_rows)

    df_ref[[
        "codice_soggetti_questionari",
        "denominazione_soggetti_questionari",
        "codice_aggregazione_2",
        "descrizione_aggregazione_2",
    ]].to_csv(out_dir / "tabella_riferimento_classi_30_to_10.csv", index=False, encoding="utf-8-sig")

    if not df_unique.empty:
        df_unique[[
            "regione_codice", "regione_finale", "provincia_finale", "comune_finale",
            "nome_canonico", "tipo_standard",
            "codice_soggetti_questionari", "denominazione_soggetti_questionari",
            "codice_aggregazione_2", "descrizione_aggregazione_2",
            "stato_osservazione", "files", "n_record_aggregati"
        ]].rename(columns={"regione_finale": "regione"}).to_csv(out_dir / "soggetti_unici_classificazione_30_e_10.csv", index=False, encoding="utf-8-sig")

        df_unique[[
            "regione_codice", "regione_finale", "provincia_finale", "comune_finale",
            "nome_canonico", "tipo_standard",
            "codice_soggetti_questionari", "denominazione_soggetti_questionari",
            "stato_osservazione", "files", "n_record_aggregati"
        ]].rename(columns={"regione_finale": "regione"}).to_csv(out_dir / "soggetti_unici_classificazione_30.csv", index=False, encoding="utf-8-sig")

        df_unique[[
            "regione_codice", "regione_finale", "provincia_finale", "comune_finale",
            "nome_canonico", "tipo_standard",
            "codice_aggregazione_2", "descrizione_aggregazione_2",
            "stato_osservazione", "files", "n_record_aggregati"
        ]].rename(columns={"regione_finale": "regione"}).to_csv(out_dir / "soggetti_unici_classificazione_10.csv", index=False, encoding="utf-8-sig")

    # output legacy utili, riallineati a 30 e 10
    write_csv(build_tipologie_numerosita_30(unique_rows), out_dir / "tipologie_numerosita_pulite.csv")
    write_csv(build_soggetti_gestione_monitoraggio(unique_rows), out_dir / "soggetti_gestione_monitoraggio_puliti.csv")
    write_csv(build_soggetti_proponenti_rows(unique_rows), out_dir / "soggetti_proponenti_puliti.csv")
    write_csv(build_firmatari_rows(unique_rows), out_dir / "firmatari_per_file_puliti.csv")

    attori_coinvolti_10 = build_attori_coinvolti_10(valid_rows)
    attori_flat = []
    for row in attori_coinvolti_10:
        attori_flat.append({
            "aggregazione_10": row["aggregazione_10"],
            "numerosita": row["numerosita"],
            "attori": " | ".join(row["attori"]),
            "files": " | ".join(row["files"]),
        })
    write_csv(attori_flat, out_dir / "attori_coinvolti_puliti.csv")

    aggregate_classification_30(df_valid).to_csv(out_dir / "attori_regionali_classificazione_30.csv", index=False, encoding="utf-8-sig")
    aggregate_classification_10(df_valid).to_csv(out_dir / "attori_regionali_classificazione_10.csv", index=False, encoding="utf-8-sig")
    aggregate_macro_30(df_valid).to_csv(out_dir / "attori_macro_classificazione_30.csv", index=False, encoding="utf-8-sig")
    aggregate_macro_10(df_valid).to_csv(out_dir / "attori_macro_classificazione_10.csv", index=False, encoding="utf-8-sig")

    pd.DataFrame(build_attori_regionali_disaggregati(valid_rows)).to_csv(out_dir / "attori_disaggregati_regione.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(build_attori_per_regione_aggregazione_10_rows(valid_rows)).to_csv(out_dir / "attori_disaggregati_regione_aggregazione_10.csv", index=False, encoding="utf-8-sig")
    pd.DataFrame(build_attori_disaggregati_10_30_rows(valid_rows)).to_csv(out_dir / "attori_disaggregati_10_30.csv", index=False, encoding="utf-8-sig")

    write_graphml(unique_rows, out_dir / "rete_attori_protocollo_pulita.csv", out_dir / "network_attori_pulito.graphml")

    qc_rows = [
        {"indicatore": "totale_record_soggetti", "valore": len(rows)},
        {"indicatore": "totale_soggetti_unici", "valore": len(unique_rows)},
        {"indicatore": "soggetti_validi_localizzati", "valore": sum(1 for r in unique_rows if r["stato_osservazione"] == "valido_localizzato")},
        {"indicatore": "soggetti_validi_non_localizzati", "valore": sum(1 for r in unique_rows if r["stato_osservazione"] == "valido_non_localizzato")},
        {"indicatore": "soggetti_generici", "valore": sum(1 for r in unique_rows if r["stato_osservazione"] == "generico")},
        {"indicatore": "soggetti_esclusi", "valore": sum(1 for r in unique_rows if r["stato_osservazione"] == "da_escludere")},
        {"indicatore": "potenziali_duplicati_record", "valore": len(dup_rows)},
    ]
    pd.DataFrame(qc_rows).to_csv(out_dir / "report_controlli_qualita.csv", index=False, encoding="utf-8-sig")

    export_json_outputs(out_dir, rows, unique_rows, valid_rows, df_ref)

    report = build_report_struct(input_json, aggregation_file if aggregation_file.exists() else Path("aggregazioni/load_reference_table_30_to_10.json"), qc_rows, unique_rows, valid_rows, dup_rows, df_ref)
    (out_dir / "report_integrato.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / "report_strutturato.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    write_report_sintetico(report, out_dir / "report_sintetico.txt")
    write_readme(out_dir, input_json, aggregation_file, df_ref, rows, unique_rows, valid_rows)

    print("OK: script integrato completato")
    print(f"Output: {out_dir}")


if __name__ == "__main__":
    main()
