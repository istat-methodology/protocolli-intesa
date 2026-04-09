# Arricchimento ruoli soggetti

import os
import json
import csv
import re
import unicodedata
from pathlib import Path
import copy
import pandas as pd
from collections import Counter

try:
    from rapidfuzz import fuzz, process
    RAPIDFUZZ_OK = True
except Exception:
    RAPIDFUZZ_OK = False

# ------------------------------------------------------
# CONFIG
# ------------------------------------------------------

JSON_STEP1_FOLDER = r"output/json/step_1/"
ROLE_ORDER = ["firmatario", "soggetto_proponente", "attore"]

# ------------------------------------------------------
# TEXT NORMALIZATION
# ------------------------------------------------------

def _strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", s)
        if not unicodedata.combining(ch)
    )


def _norm_nome_ruolo(s: str) -> str:
    """
    Normalizzazione più robusta per confronto nomi:
    - uppercase
    - rimozione accenti
    - punteggiatura/spazi uniformati
    - rimozione forme societarie/qualificatori frequenti
    """
    if not s:
        return ""

    s = str(s).strip().upper()
    s = _strip_accents(s)

    repl = {
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
        "`": "'",
        "\u2018": "'",
        "&": " E ",
    }
    for a, b in repl.items():
        s = s.replace(a, b)

    s = re.sub(r"\bS\.?\s*R\.?\s*L\.?\b", " SRL ", s)
    s = re.sub(r"\bS\.?\s*P\.?\s*A\.?\b", " SPA ", s)
    s = re.sub(r"\bSOCIETA'\b", " SOCIETA ", s)
    s = re.sub(r"\bCOOP\.?\b", " COOPERATIVA ", s)
    s = re.sub(r"\bASS\.?\b", " ASSOCIAZIONE ", s)
    s = re.sub(r"\bA\.?\s*P\.?\s*S\.?\b", " APS ", s)
    s = re.sub(r"\bO\.?\s*D\.?\s*V\.?\b", " ODV ", s)
    s = re.sub(r"\bO\.?\s*N\.?\s*L\.?\s*U\.?\s*S\.?\b", " ONLUS ", s)
    s = re.sub(r"\bE\.?\s*T\.?\s*S\.?\b", " ETS ", s)

    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()

    stop_tokens = {
        "APS", "ODV", "ETS", "ONLUS", "SRL", "SPA",
        "ASSOCIAZIONE", "COOPERATIVA", "SOCIALE", "SOCIETA"
    }
    tokens = s.split()

    while tokens and tokens[-1] in stop_tokens:
        tokens.pop()

    return " ".join(tokens).strip()


def _name_variants_ruolo(nome: str):
    """Varianti conservative per il confronto dei ruoli."""
    base = _norm_nome_ruolo(nome)
    if not base:
        return []

    variants = [base]

    v = re.sub(r"^(ASSOCIAZIONE|COMUNE DI|COMUNE|UNIONE DEI COMUNI|UNIONE|AZIENDA)\s+", "", base).strip()
    if v and v not in variants:
        variants.append(v)

    v2 = re.sub(r"\s+", "", base)
    if v2 and v2 not in variants:
        variants.append(v2)

    return variants


# ------------------------------------------------------
# ALIAS MAP
# ------------------------------------------------------

def _build_alias_map_from_lists(*liste):
    """
    Costruisce una mappa alias normalizzati -> set di forme normalizzate compatibili.
    """
    raw_names = []

    for lista in liste:
        for x in (lista or []):
            if isinstance(x, dict):
                nome = x.get("nome", "")
            else:
                nome = str(x)
            if nome:
                raw_names.append(nome)

    norm_names = []
    for n in raw_names:
        nn = _norm_nome_ruolo(n)
        if nn:
            norm_names.append(nn)

    alias_map = {}

    for nn in norm_names:
        alias_map.setdefault(nn, set()).add(nn)

        stripped = re.sub(
            r"^(ASSOCIAZIONE|COMUNE DI|COMUNE|UNIONE DEI COMUNI|UNIONE|AZIENDA)\s+", "", nn
        ).strip()
        if stripped:
            alias_map.setdefault(nn, set()).add(stripped)
            alias_map.setdefault(stripped, set()).add(nn)
            alias_map.setdefault(stripped, set()).add(stripped)

        compact = re.sub(r"\s+", "", nn)
        if compact:
            alias_map.setdefault(nn, set()).add(compact)
            alias_map.setdefault(compact, set()).add(nn)
            alias_map.setdefault(compact, set()).add(compact)

    return alias_map


# ------------------------------------------------------
# MATCHING
# ------------------------------------------------------

def _best_role_match(nome_soggetto, candidate_list, alias_map=None, fuzzy_threshold=93):
    """
    Restituisce True se trova match del soggetto in candidate_list.
    Strategia:
    1) exact su varianti
    2) contains bidirezionale
    3) fuzzy opzionale
    """
    if not nome_soggetto:
        return False

    subject_vars = _name_variants_ruolo(nome_soggetto)
    if not subject_vars:
        return False

    candidate_norms = []
    for x in (candidate_list or []):
        if isinstance(x, dict):
            nome = x.get("nome", "")
        else:
            nome = str(x)
        nn = _norm_nome_ruolo(nome)
        if nn:
            candidate_norms.append(nn)

    candidate_set = set(candidate_norms)

    if alias_map:
        expanded = set(candidate_set)
        for c in list(candidate_set):
            expanded |= alias_map.get(c, set())
        candidate_set = expanded

    # 1) exact sulle varianti
    for sv in subject_vars:
        if sv in candidate_set:
            return True
        if alias_map:
            for a in alias_map.get(sv, set()):
                if a in candidate_set:
                    return True

    # 2) contains bidirezionale conservativo
    for sv in subject_vars:
        for c in candidate_set:
            if not sv or not c:
                continue
            if len(sv) >= 4 and len(c) >= 4:
                if sv in c or c in sv:
                    return True

    # 3) fuzzy opzionale
    if RAPIDFUZZ_OK and candidate_set:
        candidate_list_norm = list(candidate_set)

        best_score = 0
        for sv in subject_vars:
            match = process.extractOne(sv, candidate_list_norm, scorer=fuzz.token_sort_ratio)
            if match:
                _, score, _ = match
                best_score = max(best_score, int(score))

        if best_score >= fuzzy_threshold:
            return True

    return False


# ------------------------------------------------------
# ENRICHMENT
# ------------------------------------------------------

def assegna_ruoli_soggetti_avanzato(
    input_json_path,
    output_json_path,
    fuzzy_threshold=93,
    aggiorna_note=False
):
    """
    Aggiunge/aggiorna 'ruolo' dentro ogni soggetto basandosi su:
    - firmatari
    - soggetti_proponenti
    - attori_coinvolti

    Parametri:
    - fuzzy_threshold: soglia fuzzy
    - aggiorna_note: se True, aggiunge i ruoli anche in note
    """
    with open(input_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    enriched = copy.deepcopy(data)

    total_subjects = 0
    assigned_any = 0
    by_role = {r: 0 for r in ROLE_ORDER}

    for file_item in enriched:
        firmatari = file_item.get("firmatari") or []
        proponenti = file_item.get("soggetti_proponenti") or []
        attori = file_item.get("attori_coinvolti") or []
        soggetti = file_item.get("soggetti") or []

        alias_map = _build_alias_map_from_lists(firmatari, proponenti, attori, soggetti)

        for ent in soggetti:
            total_subjects += 1
            nome = ent.get("nome", "")

            ruoli = []

            if _best_role_match(nome, firmatari, alias_map=alias_map, fuzzy_threshold=fuzzy_threshold):
                ruoli.append("firmatario")

            if _best_role_match(nome, proponenti, alias_map=alias_map, fuzzy_threshold=fuzzy_threshold):
                ruoli.append("soggetto_proponente")

            if _best_role_match(nome, attori, alias_map=alias_map, fuzzy_threshold=fuzzy_threshold):
                ruoli.append("attore")

            ruoli = sorted(set(ruoli), key=lambda x: ROLE_ORDER.index(x))

            ent["ruolo"] = ruoli

            if ruoli:
                assigned_any += 1
                for r in ruoli:
                    by_role[r] += 1

            if aggiorna_note:
                note = (ent.get("note") or "").strip()
                ruolo_txt = ", ".join(ruoli)
                if ruolo_txt:
                    if note:
                        if "ruolo:" not in note.lower():
                            ent["note"] = f"{note}; ruolo: {ruolo_txt}"
                    else:
                        ent["note"] = f"ruolo: {ruolo_txt}"

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)

    print("✅ Ruoli assegnati ai soggetti")
    print("   soggetti totali:", total_subjects)
    print("   soggetti con almeno un ruolo:", assigned_any)
    for r in ROLE_ORDER:
        print(f"   {r}: {by_role[r]}")
    print("📄 Output:", output_json_path)


# ------------------------------------------------------
# MAIN
# ------------------------------------------------------

def main():
    reg_code = "09"

    INPUT_JSON = Path(JSON_STEP1_FOLDER) / f"{reg_code}_risultati_enriched_2.3.json"
    OUTPUT_JSON = Path(JSON_STEP1_FOLDER) / f"{reg_code}_risultati_enriched_2.4.json"

    print("INPUT_JSON:", INPUT_JSON)
    print("OUTPUT_JSON:", OUTPUT_JSON)

    assegna_ruoli_soggetti_avanzato(
        input_json_path=INPUT_JSON,
        output_json_path=OUTPUT_JSON,
        fuzzy_threshold=93,
        aggiorna_note=False
    )


if __name__ == "__main__":
    main()