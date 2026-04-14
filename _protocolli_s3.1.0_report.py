#!/usr/bin/env python3
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


BARE_COMUNI = {
    "BARBERINO DEL MUGELLO", "BORGO SAN LORENZO", "CAMPI BISENZIO",
    "FIGLINE E INCISA VALDARNO", "LASTRA A SIGNA", "PONTASSIEVE",
    "SCANDICCI", "SESTO FIORENTINO", "TAVARNELLE VAL DI PESA",
    "SAN CASCIANO VAL DI PESA", "BAGNO A RIPOLI", "IMPRUNETA",
    "GREVE IN CHIANTI", "RUFINA", "PELAGO", "REGGELLO",
    "FIESOLE", "CALENZANO", "SIGNA"
}

GENERIC_EXACT = {
    "COMUNI",
    "QUESTURA",
    "PREFETTURA",
    "TRIBUNALE ORDINARIO",
    "TRIBUNALE",
    "PROCURA",
    "PROCURA DELLA REPUBBLICA",
    "PROCURA MINORILE",
    "PRESIDENTE DEL TRIBUNALE",
    "FORZE DELL'ORDINE",
    "FORZE DI POLIZIA GIUDIZIARIA",
    "POLIZIA GIUDIZIARIA",
    "POLIZIA DI STATO",
    "CARABINIERI",
    "GUARDIA DI FINANZA",
    "AUTORITA GIUDIZIARIA",
    "AUTORITA' GIUDIZIARIA",
    "SERVIZI SOCIALI",
    "SERVIZI SOCIALI COMUNALI",
    "SOCIETA DELLA SALUTE",
    "ZONE SOCIO-SANITARIE",
    "ZONE SOCIO SANITARIE",
    "CENTRO ANTIVIOLENZA",
    "CENTRI ANTIVIOLENZA",
    "AMBULATORIO",
    "CONSULTORIO",
    "CONSULTORIO PRINCIPALE",
    "PRONTO SOCCORSO",
    "UNITA OPERATIVA",
    "DIRETTORE SANITARIO",
    "AZIENDE SANITARIE",
    "AZIENDE SANITARIE TOSCANE",
    "SERVIZIO SANITARIO DELLA TOSCANA",
    "REFERENTI AZIENDALI",
    "TERZO SETTORE",
}

EXCLUDE_EXACT = {
    "OMS",
    "ISTAT",
    "UNIONE EUROPEA",
    "CONSIGLIO D'EUROPA",
    "CONSIGLIO D’EUROPA",
    "ORGANIZZAZIONE DELLE NAZIONI UNITE",
    "ORGANIZZAZIONE MONDIALE DELLA SANITA",
    "ORGANIZZAZIONE MONDIALE DELLA SANITÀ",
    "PRESIDENZA DEL CONSIGLIO DEI MINISTRI",
    "CONFERENZA UNIFICATA STATO-REGIONI",
    "COMUNITA DI TIPO FAMILIARE",
    "COMUNITÀ DI TIPO FAMILIARE",
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


def clean(s: Any) -> str:
    return str(s or "").strip()


def ascii_fold(s: str) -> str:
    s = clean(s)
    s = unicodedata.normalize("NFKD", s)
    return "".join(ch for ch in s if not unicodedata.combining(ch))


def normalize_text(s: str) -> str:
    s = ascii_fold(s)
    s = s.replace("’", "'").replace("“", '"').replace("”", '"').replace("–", "-")
    s = re.sub(r"\s+", " ", s).strip()
    s = s.strip(" ,.;:-")
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


def get_entities_list_ref(file_item: dict) -> list:
    if isinstance(file_item.get("soggetti"), list):
        return file_item["soggetti"]
    risultato = file_item.get("risultato") or {}
    if isinstance(risultato.get("entities"), list):
        return risultato["entities"]
    return []


def load_json(path: Path) -> list:
    obj = json.loads(path.read_text(encoding="utf-8"))

    # formato nuovo: {"totale_file_enriched_2_4": ..., "regioni": {"07": {"files": [...]}}}
    if isinstance(obj, dict) and "regioni" in obj:
        flat = []
        for reg_code, blocco in (obj.get("regioni") or {}).items():
            reg_name = REGION_CODE_TO_NAME.get(str(reg_code).zfill(2), "")
            for file_item in blocco.get("files", []) or []:
                file_item = dict(file_item)
                file_item["_regione_code"] = str(reg_code).zfill(2)
                file_item["_regione_name"] = reg_name
                flat.append(file_item)
        return flat

    # formato vecchio: lista piatta di file
    if isinstance(obj, list):
        flat = []
        for file_item in obj:
            if isinstance(file_item, dict):
                file_item = dict(file_item)
                m = FILE_REGION_RE.search(clean(file_item.get("file")))
                if m:
                    file_item["_regione_code"] = m.group(1)
                    file_item["_regione_name"] = REGION_CODE_TO_NAME.get(m.group(1), "")
                flat.append(file_item)
        return flat

    raise ValueError("Formato JSON non supportato")


def standardize_tipo(tipo: str) -> str:
    t = titleish(tipo)
    return TIPO_MAP.get(norm_key(t), t or "Altro")


def infer_file_region(file_name: str) -> str:
    m = FILE_REGION_RE.search(file_name)
    if m:
        return REGION_CODE_TO_NAME.get(m.group(1), "")
    return ""


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
    n = re.sub(r"\bC\.?I\.?S\.?M\.?A\.?I\.?\b", "CISMAI", n, flags=re.I)
    n = re.sub(r"\bC\.?I\.?F\.?\b", "CIF", n, flags=re.I)
    n = re.sub(r"\bCENTRO ITALIANO FEMMINILE\b", "CIF", n, flags=re.I)
    n = re.sub(r"\bQuesturaQuestura\b", "Questura", n, flags=re.I)
    n = re.sub(r"\bCarabinieriCarabinieri\b", "Carabinieri", n, flags=re.I)
    n = re.sub(r"\bCentro Pari Opportunita\b", "Centro Pari Opportunità", n, flags=re.I)
    n = re.sub(r"\bConsigliera di Parita\b", "Consigliera di Parità", n, flags=re.I)
    n = re.sub(r"\bConsigliera Provinciale di Parita\b", "Consigliera Provinciale di Parità", n, flags=re.I)
    n = re.sub(r"\bComunita Montana\b", "Comunità Montana", n, flags=re.I)
    n = re.sub(r"\bUfficio delle Consigliere di Parita\b", "Ufficio delle Consigliere di Parità", n, flags=re.I)
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
    if n.startswith("CONFERENZA DEI SINDACI ASL") or n.startswith("CONFERENZA DEL SINDACI ASL"):
        return "Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)"
    if n.startswith("CONFERENZA ZONALE DEI SINDACI") or n.startswith("CONFERENZA DEI SINDACI DELLA ZONA"):
        return "Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)"
    if n.startswith("FONDAZIONE TERRITORI SOCIALI"):
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
        if "MINORENNI" in n or "MINORI" in n or "MINORILE" in n:
            return "Procura Minorile/Tribunale minorile"
        return "Procura Ordinaria/Tribunale/Corte d'appello"

    if n.startswith("COMUNE DI ") or n.startswith("QUARTIERE ") or n in BARE_COMUNI:
        return "Comuni"
    if n.startswith("POLIZIA MUNICIPALE") or n.startswith("POLIZIE MUNICIPALI") or n.startswith("COMANDO POLIZIA MUNICIPALE"):
        return "Polizia Municipale"
    if "SERVIZI SOCIALI" in n or n.startswith("SEUS") or n.startswith("UTES") or n.startswith("REFERENTE EMERGENZA SOCIALE"):
        return "Servizi sociali comunali"

    if "USL" in n or "AZIENDA SANITARIA" in n or "AZIENDA OSPEDALIERA" in n:
        return "ASL (consultori familiari e altri servizi territoriali)"
    if n.startswith("CONSULTORIO "):
        return "ASL (consultori familiari e altri servizi territoriali)"
    if n.startswith("PRONTO SOCCORSO DI ") or n.startswith("U.O PRONTO SOCCORSO") or n.startswith("OSPEDALE"):
        return "Ospedale (Pronto soccorso, ecc.)"
    if n.startswith("CENTRO PER L'IMPIEGO") or n.startswith("ARTI SERVIZI PER IL LAVORO"):
        return "Servizi per l'impiego"

    if n.startswith("CENTRO DI ASCOLTO UOMINI MALTRATTANTI") or n.startswith("CAM CENTRO UOMINI MALTRATTANTI") or n.startswith("CAM FIRENZE") or "UOMINI MALTRATTANTI" in n:
        return "Associazioni che si occupano di programmi di prevenzione, recupero e trattamento per uomini maltrattanti"
    if n.startswith("CISMAI"):
        return "Ente terzo settore - ETS (iscritto al RUNTS)"
    if n.startswith("AIED"):
        return "Ente terzo settore - ETS (iscritto al RUNTS)"
    if n.startswith("CENTRO DI ASCOLTO") or n.startswith("PUNTO DI ASCOLTO"):
        return "Ente terzo settore - ETS (iscritto al RUNTS)"
    if "CODICE ROSA" in n:
        return "ASL (consultori familiari e altri servizi territoriali)"

    return t


def macro_categoria(tipo: str) -> str:
    tipo = standardize_tipo(tipo)
    if tipo in {"CAV/Centri Antiviolenza", "Case Rifugio"}:
        return "CAV e Case Rifugio"
    if tipo in {
        "Ente terzo settore - ETS (iscritto al RUNTS)",
        "Ente terzo settore - ETS (iscritto al RUNTS) costituito da donne per le donne",
        "Associazioni che si occupano di programmi di prevenzione, recupero e trattamento per uomini maltrattanti",
        "Sindacati/Associazioni di categoria",
    }:
        return "Associazionismo"
    if tipo in {"Comuni", "Servizi sociali comunali", "Polizia Municipale"}:
        return "Enti territoriali / servizi comunali"
    if tipo in {"Province/Città metropolitane", "Polizia provinciale"}:
        return "Province/Città metropolitane"
    if tipo in {"Regioni/Province Autonome"}:
        return "Regioni/Province Autonome"
    if tipo in {"Enti territoriali sovracomunali"}:
        return "Enti territoriali sovracomunali"
    if tipo in {"Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)"}:
        return "Ambiti socio-sanitari"
    if tipo in {"ASL (consultori familiari e altri servizi territoriali)", "Ospedale (Pronto soccorso, ecc.)", "Servizi per l'impiego"}:
        return "Sanità e servizi territoriali"
    if tipo in {"Prefettura", "Questura", "Carabinieri/Polizia/altre forze dell'ordine", "Procura Minorile/Tribunale minorile", "Procura Ordinaria/Tribunale/Corte d'appello", "Ordine avvocati"}:
        return "Giustizia e forze dell'ordine"
    if tipo in {"Ordine psicologi e Ordine assistenti sociali", "Ordine medici e odontoiatri e Ordine farmacisti", "Altri ordini professionali", "Università", "Scuole/Ufficio scolastico provinciale e regionale", "Organismi di parità"}:
        return "Altri attori istituzionali / professionali"
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
            "CAV/Centri Antiviolenza",
            "Case Rifugio",
            "Servizi per l'impiego",
        }:
            return "valido_non_localizzato"
        return "generico"
    return "valido_localizzato"


def good_capofila(value: str) -> str:
    v = titleish(value)
    if not v:
        return ""
    if norm_key(v) in {"SI", "NO", "TRUE", "FALSE", "1", "0"}:
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
    if v:
        return v
    return canonicalize_name(clean(ent.get("nome")), clean(ent.get("tipo")))


def derive_records(data: list) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for i, file_item in enumerate(data, start=1):
        file_name = clean(file_item.get("file"))
        file_region = infer_file_region(file_name)
        entities = get_entities_list_ref(file_item)
        for j, ent in enumerate(entities, start=1):
            original_name = clean(ent.get("nome"))
            name = canonicalize_name(original_name, clean(ent.get("tipo")))
            tipo = standardize_tipo_from_name(name, clean(ent.get("tipo")))
            comune = clean(ent.get("comune")) or clean(ent.get("comune_matchato")) or clean(ent.get("comune_runts"))
            provincia = titleish(ent.get("provincia"))
            regione = titleish(ent.get("regione")) or file_region
            if not provincia or not regione:
                _, p2, r2 = infer_province_from_name(name)
                provincia = provincia or p2
                regione = regione or r2
            stato = classify_observation(name, tipo, comune, provincia, regione)
            roles = parse_roles(ent)
            rows.append({
                "record_id": f"{i:03d}_{j:04d}",
                "file": file_name,
                "nome_originale": original_name,
                "nome_canonico": name,
                "nome_norm_stat": norm_key(name),
                "tipo_originale": clean(ent.get("tipo")) or "Altro",
                "tipo_standard": tipo,
                "macro_categoria": macro_categoria(tipo),
                "comune_finale": titleish(comune),
                "provincia_finale": provincia,
                "regione_finale": regione,
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

    unique_rows.sort(key=lambda x: (x["macro_categoria"], x["nome_canonico"], x["provincia_finale"], x["regione_finale"]))
    return unique_rows, dup_rows



def build_attori_regionali_disaggregati(valid_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    rows = []
    for r in valid_rows:
        if not (r["ruolo_attore"] or not r["ruoli_documentali_aggregati"]):
            continue
        rows.append({
            "regione": r["regione_finale"],
            "provincia": r["provincia_finale"],
            "macro_categoria": r["macro_categoria"],
            "tipo_standard": r["tipo_standard"],
            "nome_canonico": r["nome_canonico"],
            "file": r["files"],
            "n_record_aggregati": r.get("n_record_aggregati", 1),
        })
    rows.sort(key=lambda x: (x["regione"], x["macro_categoria"], x["tipo_standard"], x["nome_canonico"]))
    return rows


def build_attori_per_regione_macro(valid_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    c = Counter()
    for r in valid_rows:
        if not (r["ruolo_attore"] or not r["ruoli_documentali_aggregati"]):
            continue
        c[(r["regione_finale"], r["macro_categoria"])] += 1
    out = [
        {"regione": reg, "macro_categoria": macro, "numerosita": n}
        for (reg, macro), n in c.items()
    ]
    out.sort(key=lambda x: (x["regione"], -x["numerosita"], x["macro_categoria"]))
    return out


def build_attori_disaggregati_macro_tipologia(valid_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    grouped = defaultdict(set)
    grouped_regions = defaultdict(set)
    grouped_files = defaultdict(set)
    for r in valid_rows:
        if not (r["ruolo_attore"] or not r["ruoli_documentali_aggregati"]):
            continue
        key = (r["macro_categoria"], r["tipo_standard"])
        grouped[key].add(r["nome_canonico"])
        if r["regione_finale"]:
            grouped_regions[key].add(r["regione_finale"])
        for f in r["files"].split(" | ") if r.get("files") else []:
            if f:
                grouped_files[key].add(f)

    out = []
    for (macro, tipo), nomi in grouped.items():
        out.append({
            "macro_categoria": macro,
            "tipo_standard": tipo,
            "numerosita_attori": len(nomi),
            "attori": " | ".join(sorted(nomi)),
            "n_regioni": len(grouped_regions[(macro, tipo)]),
            "regioni": " | ".join(sorted(grouped_regions[(macro, tipo)])),
            "n_file": len(grouped_files[(macro, tipo)]),
            "files": " | ".join(sorted(grouped_files[(macro, tipo)])),
        })
    out.sort(key=lambda x: (x["macro_categoria"], -x["numerosita_attori"], x["tipo_standard"]))
    return out
########################################################
#
# Costruzione tabella soggetti proponenti
#
# La regione di riferimento è presa da "regione_finale" 
# se presente, altrimenti da "_regione_name" (inserito in 
# fase di caricamento), altrimenti inferita dal nome del file, altrimenti "ND".#
# La tabella finale è disaggregata per regione, soggetto 
# proponente,  tipo e macro categoria.
#
##########################################################
def resolve_row_region(row: Dict[str, Any]) -> str:
    reg = clean(row.get("regione_finale"))
    if reg:
        return reg

    reg = clean(row.get("_regione_name"))
    if reg:
        return reg

    reg = infer_file_region(clean(row.get("file")))
    return reg or "ND"

def build_soggetti_gestione(data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    seen = set()

    for file_item in data:
        file_name = clean(file_item.get("file"))

        regione = (
            clean(file_item.get("_regione_name"))
            or infer_file_region(file_name)
            or "ND"
        )

        for ent in get_entities_list_ref(file_item):
            ruoli = extract_ruoli_gestione(ent)
            if not ruoli:
                continue

            soggetto = choose_soggetto_incaricato(ent)
            nome = canonicalize_name(clean(ent.get("nome")), clean(ent.get("tipo")))
            tipo = standardize_tipo_from_name(nome, clean(ent.get("tipo")))

            key = (
                regione,
                norm_key(soggetto),
                norm_key(nome),
                "|".join(sorted(ruoli)),
                file_name,
            )
            if key in seen:
                continue
            seen.add(key)

            out.append({
                "regione": regione,
                "file": file_name,
                "soggetto_incaricato": soggetto,
                "nome_entita": nome,
                "tipo_entita": tipo,
                "macro_categoria": macro_categoria(tipo),
                "ruoli": ", ".join(ruoli),
                "ente_capofila": good_capofila(ent.get("ente_capofila")),
                "note": clean(ent.get("note")),
            })

    out.sort(key=lambda x: (x["regione"], x["file"], x["soggetto_incaricato"]))
    return out

def build_soggetti_proponenti(unique_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []

    for row in unique_rows:
        if not row.get("ruolo_proponente"):
            continue

        out.append({
            "regione": resolve_row_region(row),
            "file": row.get("file", ""),
            "soggetto_proponente": row.get("nome_canonico", ""),
            "tipo": row.get("tipo_standard", ""),
            "macro_categoria": row.get("macro_categoria", ""),
        })

    out.sort(key=lambda x: (x["regione"], x["file"], x["soggetto_proponente"]))
    return out

def build_firmatari(unique_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    out = []

    for row in unique_rows:
        if not row.get("ruolo_firmatario"):
            continue

        out.append({
            "regione": resolve_row_region(row),
            "file": row.get("file", ""),
            "firmatario": row.get("nome_canonico", ""),
            "tipo": row.get("tipo_standard", ""),
            "macro_categoria": row.get("macro_categoria", ""),
        })

    out.sort(key=lambda x: (x["regione"], x["file"], x["firmatario"]))
    return out

def build_outputs(data: list) -> Dict[str, Any]:
    rows = derive_records(data)
    unique_rows, dup_rows = dedupe_unique(rows)
    valid_rows = [r for r in unique_rows if r["stato_osservazione"] == "valido_localizzato"]
    diag_rows = [r for r in unique_rows if r["stato_osservazione"] != "valido_localizzato"]

    tipi_counter = Counter(r["tipo_standard"] for r in valid_rows)
    tipologie = [{"tipo": k, "numerosita": v} for k, v in tipi_counter.most_common()]

    macro_groups = defaultdict(list)
    macro_files = defaultdict(set)
    for r in valid_rows:
        if r["ruolo_attore"] or not r["ruoli_documentali_aggregati"]:
            macro_groups[r["macro_categoria"]].append(r["nome_canonico"])
            for f in r["files"].split(" | ") if r.get("files") else []:
                if f:
                    macro_files[r["macro_categoria"]].add(f)

    attori_coinvolti = []
    for macro, nomi in macro_groups.items():
        attori_coinvolti.append({
            "macro_categoria": macro,
            "numerosita": len(sorted(set(nomi))),
            "attori": sorted(set(nomi)),
            "files": sorted(macro_files[macro]),
        })
    attori_coinvolti.sort(key=lambda x: (-x["numerosita"], x["macro_categoria"]))


    soggetti_gestione= []
    soggetti_gestione = build_soggetti_gestione(data)

    proponenti_rows, firmatari_rows = [], []
    for file_item in data:
        file_name = clean(file_item.get("file"))
        for p in file_item.get("soggetti_proponenti", []) or []:
            p = canonicalize_name(clean(p), "Altro")
            if p:
                proponenti_rows.append({"file": file_name, "soggetto_proponente": p})
        for f in file_item.get("firmatari", []) or []:
            f = canonicalize_name(clean(f), "Altro")
            if f:
                firmatari_rows.append({"file": file_name, "firmatario": f})

    qc_rows = [
        {"indicatore": "totale_record_soggetti", "valore": len(rows)},
        {"indicatore": "totale_soggetti_unici", "valore": len(unique_rows)},
        {"indicatore": "soggetti_validi_localizzati", "valore": sum(1 for r in unique_rows if r["stato_osservazione"] == "valido_localizzato")},
        {"indicatore": "soggetti_validi_non_localizzati", "valore": sum(1 for r in unique_rows if r["stato_osservazione"] == "valido_non_localizzato")},
        {"indicatore": "soggetti_generici", "valore": sum(1 for r in unique_rows if r["stato_osservazione"] == "generico")},
        {"indicatore": "soggetti_esclusi", "valore": sum(1 for r in unique_rows if r["stato_osservazione"] == "da_escludere")},
        {"indicatore": "potenziali_duplicati_record", "valore": len(dup_rows)},
    ]

    attori_regionali_disaggregati = build_attori_regionali_disaggregati(valid_rows)
    attori_per_regione_macro = build_attori_per_regione_macro(valid_rows)
    attori_disaggregati_macro_tipologia = build_attori_disaggregati_macro_tipologia(valid_rows)

    #soggetti_gestione = build_soggetti_gestione(soggetti_gestione_rows)
    soggetti_proponenti = build_soggetti_proponenti(unique_rows)
    firmatari = build_firmatari(unique_rows)



    return {
        "record_rows": rows,
        "unique_rows": unique_rows,
        "diag_rows": diag_rows,
        "dup_rows": dup_rows,
        "tipologie_numerosita": tipologie,
        "attori_coinvolti": attori_coinvolti,
        "soggetti_gestione": soggetti_gestione,
        "soggetti_proponenti": soggetti_proponenti,
        "firmatari": firmatari,
        "report_controlli_qualita": qc_rows,
        "attori_regionali_disaggregati": attori_regionali_disaggregati,
        "attori_per_regione_macro": attori_per_regione_macro,
        "attori_disaggregati_macro_tipologia": attori_disaggregati_macro_tipologia,
    }


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
        if r["ruolo_attore"] or not r["ruoli_documentali_aggregati"]:
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



def write_txt_report(outputs: Dict[str, Any], out_txt: Path, input_json: Path):
    from collections import defaultdict, Counter

    qc_map = {r["indicatore"]: r["valore"] for r in outputs["report_controlli_qualita"]}

    lines = []
    lines.append("REPORT SOGGETTI V5\n")
    lines.append(f"Input JSON: {input_json}")
    lines.append(f"Totale record soggetti: {qc_map.get('totale_record_soggetti', 0)}")
    lines.append(f"Totale soggetti unici: {qc_map.get('totale_soggetti_unici', 0)}")
    lines.append("")

    # =====================================================
    # 1) CONTROLLI QUALITÀ
    # =====================================================
    lines.append("1) CONTROLLI QUALITÀ")
    for r in outputs["report_controlli_qualita"]:
        lines.append(f"- {r['indicatore']}: {r['valore']}")
    lines.append("")

    # =====================================================
    # 2) RAGGRUPPAMENTO REGIONALE
    # =====================================================
    lines.append("2) RAGGRUPPAMENTO REGIONALE")

    per_reg_macro = defaultdict(list)
    for row in outputs.get("attori_per_regione_macro", []):
        reg = row.get("regione", "") or "ND"
        per_reg_macro[reg].append(row)

    if not per_reg_macro:
        lines.append("- Nessun dato regionale disponibile.")
    else:
        for reg in sorted(per_reg_macro.keys()):
            righe_reg = per_reg_macro[reg]
            totale_reg = sum(x.get("numerosita", 0) for x in righe_reg)

            lines.append("")
            lines.append(f"REGIONE: {reg}")
            lines.append(f"Totale attori: {totale_reg}")

            for row in sorted(righe_reg, key=lambda x: (-x.get("numerosita", 0), x.get("macro_categoria", ""))):
                lines.append(f"  - {row['macro_categoria']}: {row['numerosita']}")
    lines.append("")

    # =====================================================
    # 3) TIPOLOGIE PULITE PER REGIONE
    # =====================================================
    lines.append("3) TIPOLOGIE PULITE PER REGIONE")

    tipologie_reg = defaultdict(Counter)
    for row in outputs.get("unique_rows", []):
        reg = row.get("regione_finale", "") or "ND"
        tipo = row.get("tipo_standard", "") or "ND"
        tipologie_reg[reg][tipo] += 1

    if not tipologie_reg:
        lines.append("- Nessun dato disponibile.")
    else:
        for reg in sorted(tipologie_reg.keys()):
            lines.append("")
            lines.append(f"REGIONE: {reg}")
            for tipo, n in tipologie_reg[reg].most_common():
                lines.append(f"- {tipo}: {n}")
    lines.append("")

    # =====================================================
    # 4) ATTORI COINVOLTI PULITI PER REGIONE
    # =====================================================
    lines.append("4) ATTORI COINVOLTI PULITI PER REGIONE")

    attori_reg = defaultdict(lambda: defaultdict(lambda: {"attori": set(), "files": set()}))
    for row in outputs.get("unique_rows", []):
        reg = row.get("regione_finale", "") or "ND"
        macro = row.get("macro_categoria", "") or "ND"
        nome = row.get("nome_canonico", "") or "ND"

        attori_reg[reg][macro]["attori"].add(nome)

        for f in (row.get("files", "") or "").split(" | "):
            f = f.strip()
            if f:
                attori_reg[reg][macro]["files"].add(f)

    if not attori_reg:
        lines.append("- Nessun dato disponibile.")
    else:
        for reg in sorted(attori_reg.keys()):
            lines.append("")
            lines.append(f"REGIONE: {reg}")

            macro_rows = []
            for macro, payload in attori_reg[reg].items():
                macro_rows.append({
                    "macro": macro,
                    "n": len(payload["attori"]),
                    "attori": sorted(payload["attori"]),
                    "files": sorted(payload["files"]),
                })

            macro_rows.sort(key=lambda x: (-x["n"], x["macro"]))

            for row in macro_rows:
                lines.append(f"\n{row['macro']} ({row['n']}):")
                if row["files"]:
                    lines.append("  file: " + ", ".join(row["files"]))
                for nome in row["attori"]:
                    lines.append(f"  - {nome}")
    lines.append("")

    # =====================================================
    # 5) ATTORI DISAGGREGATI PER MACRO-TIPOLOGIA E REGIONE
    # =====================================================
    lines.append("5) ATTORI DISAGGREGATI PER MACRO-TIPOLOGIA E REGIONE")

    macro_tipo_reg = defaultdict(list)
    for row in outputs.get("attori_regionali_disaggregati", []):
        reg = row.get("regione", "") or "ND"
        macro_tipo_reg[reg].append(row)

    if not macro_tipo_reg:
        lines.append("- Nessun dato disponibile.")
    else:
        for reg in sorted(macro_tipo_reg.keys()):
            lines.append("")
            lines.append(f"REGIONE: {reg}")

            counter = Counter()
            tipi_per_macro = defaultdict(Counter)

            for row in macro_tipo_reg[reg]:
                macro = row.get("macro_categoria", "") or "ND"
                tipo = row.get("tipo_standard", "") or "ND"
                counter[macro] += 1
                tipi_per_macro[macro][tipo] += 1

            for macro, n in counter.most_common():
                lines.append(f"- {macro}: {n}")
                for tipo, nt in tipi_per_macro[macro].most_common():
                    lines.append(f"    • {tipo}: {nt}")
    lines.append("")

    # =====================================================
    # 6) SOGGETTI INCARICATI DI GESTIRE / MONITORARE / COORDINARE PER REGIONE
    # =====================================================
    lines.append("6) SOGGETTI INCARICATI DI GESTIRE / MONITORARE / COORDINARE PER REGIONE")

    gestione_reg = defaultdict(lambda: defaultdict(list))

    for row in outputs.get("soggetti_gestione", []):
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

                for row in sorted(
                    gestione_reg[reg][file_name],
                    key=lambda x: (x.get("macro_categoria", ""), x.get("soggetto_incaricato", ""))
                ):
                    lines.append(f"    - {row.get('soggetto_incaricato', '')}")
                    lines.append(f"      entità: {row.get('nome_entita', '')}")
                    lines.append(f"      tipo: {row.get('tipo_entita', '')}")
                    lines.append(f"      macro: {row.get('macro_categoria', '')}")
                    lines.append(f"      ruoli: {row.get('ruoli', '')}")

                    ente_capofila = row.get("ente_capofila", "")
                    note = row.get("note", "")

                    if ente_capofila:
                        lines.append(f"      ente_capofila: {ente_capofila}")
                    if note:
                        lines.append(f"      note: {note}")

    lines.append("")

    # =====================================================
    # 7) SOGGETTI PROPONENTI PER REGIONE
    # =====================================================
    lines.append("7) SOGGETTI PROPONENTI PER REGIONE")

    proponenti_reg = defaultdict(lambda: defaultdict(list))

    for row in outputs.get("soggetti_proponenti", []):
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


    # =====================================================
    # 8) FIRMATARI PER REGIONE
    # =====================================================
    lines.append("8) FIRMATARI PER REGIONE")

    firmatari_reg = defaultdict(lambda: defaultdict(list))

    for row in outputs.get("firmatari", []):
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
    # =====================================================
    # 9) RIEPILOGO GLOBALE PER MACRO-TIPOLOGIA
    # =====================================================
    lines.append("9) RIEPILOGO GLOBALE PER MACRO-TIPOLOGIA")

    macro_global = Counter()
    for row in outputs.get("attori_per_regione_macro", []):
        macro_global[row["macro_categoria"]] += row["numerosita"]

    if not macro_global:
        lines.append("- Nessun dato disponibile.")
    else:
        for macro, n in macro_global.most_common():
            lines.append(f"- {macro}: {n}")
    lines.append("")

    out_txt.write_text("\n".join(lines), encoding="utf-8")

def main():
    output_dir = r"output\reports"
    input_json = r"output\json\merged\all_risultati_enriched_2.4.json"

    input_json = Path(input_json)
    if not input_json.exists():
        raise FileNotFoundError(f"File non trovato: {input_json}")

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    data = load_json(input_json)
    outputs = build_outputs(data)

    write_csv(outputs["record_rows"], out_dir / "soggetti_puliti_per_record.csv")
    write_csv(outputs["unique_rows"], out_dir / "soggetti_unici_puliti.csv")
    write_csv(outputs["diag_rows"], out_dir / "soggetti_generici_non_localizzati.csv")
    write_csv(outputs["dup_rows"], out_dir / "soggetti_duplicati_potenziali.csv")
    write_csv(outputs["tipologie_numerosita"], out_dir / "tipologie_numerosita_pulite.csv")
    write_csv(outputs["soggetti_gestione"], out_dir / "soggetti_gestione_monitoraggio_puliti.csv")
    write_csv(outputs["soggetti_proponenti"], out_dir / "soggetti_proponenti_puliti.csv")
    write_csv(outputs["firmatari"], out_dir / "firmatari_per_file_puliti.csv")
    write_csv(outputs["report_controlli_qualita"], out_dir / "report_controlli_qualita.csv")

    attori_flat = []
    for row in outputs["attori_coinvolti"]:
        attori_flat.append({
            "macro_categoria": row["macro_categoria"],
            "numerosita": row["numerosita"],
            "attori": " | ".join(row["attori"]),
            "files": " | ".join(row["files"]),
        })
    write_csv(attori_flat, out_dir / "attori_coinvolti_puliti.csv")

    # Nuove uscite disaggregate
    write_csv(outputs["attori_regionali_disaggregati"], out_dir / "attori_disaggregati_regione.csv")
    write_csv(outputs["attori_per_regione_macro"], out_dir / "attori_disaggregati_regione_macro.csv")
    write_csv(outputs["attori_disaggregati_macro_tipologia"], out_dir / "attori_disaggregati_macro_tipologia.csv")

    write_graphml(outputs["unique_rows"], out_dir / "rete_attori_protocollo_pulita.csv", out_dir / "network_attori_pulito.graphml")

    report_struct = {
        "input_json": str(input_json),
        "report_controlli_qualita": outputs["report_controlli_qualita"],
        "tipologia_numerosita": outputs["tipologie_numerosita"],
        "attori_coinvolti": outputs["attori_coinvolti"],
        "attori_regionali_disaggregati": outputs["attori_regionali_disaggregati"],
        "attori_per_regione_macro": outputs["attori_per_regione_macro"],
        "attori_disaggregati_macro_tipologia": outputs["attori_disaggregati_macro_tipologia"],
        "soggetti_incaricati_gestione_monitoraggio_coordinamento": outputs["soggetti_gestione"],
        "soggetti_proponenti": outputs["soggetti_proponenti"],
        "firmatari": outputs["firmatari"],
    }
    (out_dir / "report_strutturato_v4.json").write_text(
        json.dumps(report_struct, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    write_txt_report(outputs, out_dir / "report_sintetico_v4.txt", input_json)

    print(f"OK: report V4 creati in {out_dir}")


if __name__ == "__main__":
    main()
