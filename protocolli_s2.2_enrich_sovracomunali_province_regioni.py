# protocolli_s2.2_enrich_sovracomunali_province_regioni.py
# Arricchimento enti sovracomunali

import os
import json
import re
import unicodedata
import copy
import pandas as pd
from pathlib import Path
from collections import Counter

# ------------------------------------------------------
# CONFIG
# ------------------------------------------------------

CLASSIFICATION_FOLDER = r"classification/"
SOVRACOMUNALI_CSV = os.path.join(
    CLASSIFICATION_FOLDER,
    "cls_elenco_unioni_comuni_comunità_di_montagna_comunità_territoriali.csv"
)
PROVINCE_CSV = os.path.join(CLASSIFICATION_FOLDER, "cls_elenco_province_2026.csv")
REGIONI_CSV = os.path.join(CLASSIFICATION_FOLDER, "cls_elenco_regioni_2026.csv")
JSON_STEP1_FOLDER = r"output/json/step_1/"

try:
    from rapidfuzz import process, fuzz
    RAPIDFUZZ_OK = True
except Exception:
    RAPIDFUZZ_OK = False


# ------------------------------------------------------
# UTILITY FUNCTIONS
# ------------------------------------------------------

def read_csv_flexible(csv_path, dtype=str):
    """
    Legge in modo robusto i CSV di classificazione 2026:
    - alcuni sono separati da ;
    - altri da ,
    """
    for sep in [",", ";", None]:
        try:
            if sep is None:
                df = pd.read_csv(csv_path, dtype=dtype, sep=None, engine="python")
            else:
                df = pd.read_csv(csv_path, dtype=dtype, sep=sep)
            if len(df.columns) > 1:
                return df.fillna("")
        except Exception:
            pass
    raise ValueError(f"Impossibile leggere correttamente il CSV: {csv_path}")


def load_sovracomunali_tables(sovracomunali_csv):
    """
    Carica il file unico:
    cls_elenco_unioni_comuni_comunità_di_montagna_comunità_territoriali.csv

    Colonne attese:
    - TIPO_ENTE
    - COD
    - DENOMINAZIONE
    - COMUNE
    - PROVINCIA
    - REGIONE
    """
    df = read_csv_flexible(sovracomunali_csv, dtype=str)

    required = {"TIPO_ENTE", "COD", "DENOMINAZIONE", "COMUNE", "PROVINCIA", "REGIONE"}
    missing = [c for c in required if c not in df.columns]
    if missing:
        raise ValueError(f"Colonne mancanti nel file sovracomunali: {missing}")

    tipo_map = {
        "Unione di comuni": "Unione dei Comuni",
        "Unione montana": "Unione dei Comuni",
        "Comunità di montagna": "Comunità Montana",
        "Comunità territoriale": "Comunità Territoriale",
    }

    df["tipo_finale"] = df["TIPO_ENTE"].map(tipo_map).fillna(df["TIPO_ENTE"])
    df["nome_ente"] = df["DENOMINAZIONE"].astype(str).str.strip()
    df["comune_membro"] = df["COMUNE"].astype(str).str.strip()
    df["provincia"] = df["PROVINCIA"].astype(str).str.strip()
    df["regione"] = df["REGIONE"].astype(str).str.strip()
    df["cod"] = df["COD"].astype(str).str.strip()

    grouped = (
        df.groupby(["nome_ente", "tipo_finale"], dropna=False)
        .agg({
            "cod": "first",
            "regione": lambda x: sorted(set(v for v in x if v)),
            "provincia": lambda x: sorted(set(v for v in x if v)),
            "comune_membro": lambda x: sorted(set(v for v in x if v)),
        })
        .reset_index()
    )

    return grouped


def load_province_regioni_tables(province_csv, regioni_csv):
    df_province = read_csv_flexible(province_csv, dtype=str)
    df_regioni = read_csv_flexible(regioni_csv, dtype=str)

    required_prov = {
        "Codice Provincia/Uts", "Provincia/Uts", "Regione", "Sigla automobilistica"
    }
    required_reg = {
        "Codice Regione", "Regione"
    }

    missing_prov = [c for c in required_prov if c not in df_province.columns]
    missing_reg = [c for c in required_reg if c not in df_regioni.columns]

    if missing_prov:
        raise ValueError(f"Colonne mancanti nel file province: {missing_prov}")
    if missing_reg:
        raise ValueError(f"Colonne mancanti nel file regioni: {missing_reg}")

    return df_province.fillna(""), df_regioni.fillna("")


# ------------------------------------------------------
# TEXT NORMALIZATION
# ------------------------------------------------------

def _strip_accents(s: str) -> str:
    if not s:
        return ""
    return "".join(
        ch for ch in unicodedata.normalize("NFKD", str(s))
        if not unicodedata.combining(ch)
    )


def _norm_text(s: str) -> str:
    if not s:
        return ""
    s = str(s).strip().upper()
    s = _strip_accents(s)
    s = s.replace("\u2019", "'").replace("\u2018", "'").replace("`", "'")
    s = re.sub(r"[^A-Z0-9\s]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _compact_text(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", _norm_text(s))


def _norm_sovra_alias(s: str) -> str:
    s = _norm_text(s)

    stopwords = {
        "DEI", "DELLE", "DELLA", "DEGLI", "DEL", "DI",
        "COMUNI", "COMUNE"
    }

    tokens = [t for t in s.split() if t not in stopwords]
    return " ".join(tokens).strip()


# ------------------------------------------------------
# GEO LOOKUP
# ------------------------------------------------------

def build_geo_lookup(df_province, df_regioni):
    prov_by_name = {}
    prov_by_sigla = {}
    reg_by_name = {}

    for row in df_province.to_dict(orient="records"):
        provincia = (row.get("Provincia/Uts") or "").strip()
        regione = (row.get("Regione") or "").strip()
        sigla = (row.get("Sigla automobilistica") or "").strip()

        record = {
            "codice_provincia": (row.get("Codice Provincia/Uts") or "").strip(),
            "provincia": provincia,
            "sigla_provincia": sigla,
            "codice_regione": (row.get("Codice Regione") or "").strip(),
            "regione": regione,
            "ripartizione_geografica": (row.get("Ripartizione geografica") or "").strip(),
            "descrizione_tipologia_provincia": (row.get("Descrizione tipologia Provincia/Uts") or "").strip(),
        }

        k_prov = _norm_text(provincia)
        k_sigla = _norm_text(sigla)
        if k_prov:
            prov_by_name[k_prov] = record
        if k_sigla:
            prov_by_sigla[k_sigla] = record

    for row in df_regioni.to_dict(orient="records"):
        regione = (row.get("Regione") or "").strip()
        k_reg = _norm_text(regione)
        if k_reg:
            reg_by_name[k_reg] = {
                "codice_regione": (row.get("Codice Regione") or "").strip(),
                "regione": regione,
                "ripartizione_geografica": (row.get("Ripartizione geografica") or "").strip(),
                "tipo_regione": (row.get("Tipo regione") or "").strip(),
            }

    return prov_by_name, prov_by_sigla, reg_by_name


def lookup_provincia_record(value, prov_by_name, prov_by_sigla):
    if not value:
        return None
    q = _norm_text(value)
    if q in prov_by_name:
        return prov_by_name[q]
    if q in prov_by_sigla:
        return prov_by_sigla[q]
    return None


def lookup_regione_record(value, reg_by_name):
    if not value:
        return None
    return reg_by_name.get(_norm_text(value))


def resolve_geo_from_lists(province_list, regioni_list, prov_by_name, prov_by_sigla, reg_by_name):
    matched_province = []
    matched_regioni = []

    for prov in province_list or []:
        rec = lookup_provincia_record(prov, prov_by_name, prov_by_sigla)
        if rec:
            matched_province.append(rec)

    for reg in regioni_list or []:
        rec = lookup_regione_record(reg, reg_by_name)
        if rec:
            matched_regioni.append(rec)

    def dedup_dicts(items, key):
        seen = set()
        out = []
        for item in items:
            k = item.get(key, "")
            if k and k not in seen:
                seen.add(k)
                out.append(item)
        return out

    matched_province = dedup_dicts(matched_province, "codice_provincia")
    matched_regioni = dedup_dicts(matched_regioni, "codice_regione")

    province_codes = [r.get("codice_provincia", "") for r in matched_province if r.get("codice_provincia")]
    province_sigle = [r.get("sigla_provincia", "") for r in matched_province if r.get("sigla_provincia")]
    region_codes = [r.get("codice_regione", "") for r in matched_regioni if r.get("codice_regione")]

    # fallback: se la regione manca ma c'è la provincia, derivala dalla provincia
    if not region_codes and matched_province:
        region_codes = [r.get("codice_regione", "") for r in matched_province if r.get("codice_regione")]
        region_codes = [c for c in region_codes if c]

    return {
        "codice_provincia": province_codes[0] if len(province_codes) == 1 else "; ".join(province_codes),
        "sigla_provincia": province_sigle[0] if len(province_sigle) == 1 else "; ".join(province_sigle),
        "codice_regione": region_codes[0] if len(region_codes) == 1 else "; ".join(region_codes),
    }


# ------------------------------------------------------
# SOVRACOMUNALI INDEX & LOOKUP
# ------------------------------------------------------

def build_sovracomunali_index(df_sovra):
    idx_exact = {}
    idx_compact = {}
    idx_alias = {}
    fuzzy_names = []
    fuzzy_rows = []

    for row in df_sovra.to_dict(orient="records"):
        nome = row.get("nome_ente", "")

        k_exact = _norm_text(nome)
        k_compact = _compact_text(nome)
        k_alias = _norm_sovra_alias(nome)

        if k_exact:
            idx_exact[k_exact] = row
            fuzzy_names.append(k_exact)
            fuzzy_rows.append(row)

        if k_compact:
            idx_compact[k_compact] = row

        if k_alias:
            idx_alias[k_alias] = row

    return idx_exact, idx_compact, idx_alias, fuzzy_names, fuzzy_rows


def lookup_sovracomunale(
    nome,
    idx_exact,
    idx_compact,
    idx_alias,
    fuzzy_names,
    fuzzy_rows,
    fuzzy_threshold=95
):
    if not nome:
        return None, "none", 0

    q_exact = _norm_text(nome)
    q_compact = _compact_text(nome)
    q_alias = _norm_sovra_alias(nome)

    # 1) exact
    if q_exact in idx_exact:
        return idx_exact[q_exact], "exact", 100

    # 2) compact
    if q_compact in idx_compact:
        return idx_compact[q_compact], "compact", 100

    # 3) alias
    if q_alias in idx_alias:
        return idx_alias[q_alias], "alias", 100

    # 4) alias_contains SOLO per stringhe abbastanza lunghe
    tokens_alias = q_alias.split()
    if len(q_alias) >= 10 and len(tokens_alias) >= 2:
        for k, row in idx_alias.items():
            if q_alias and (q_alias in k or k in q_alias):
                return row, "alias_contains", 99

    # 5) contains SOLO per stringhe abbastanza lunghe
    tokens_exact = q_exact.split()
    if len(q_exact) >= 10 and len(tokens_exact) >= 2:
        for k, row in idx_exact.items():
            if q_exact and (q_exact in k or k in q_exact):
                return row, "contains", 99

    # 6) fuzzy SOLO per query non troppo corte
    if RAPIDFUZZ_OK and fuzzy_names and len(q_exact) >= 8:
        match = process.extractOne(q_exact, fuzzy_names, scorer=fuzz.token_sort_ratio)
        if match:
            _, score, idx = match
            score = int(score)
            if score >= fuzzy_threshold:
                return fuzzy_rows[idx], "fuzzy", score

    return None, "none", 0


# ------------------------------------------------------
# ENRICHMENT
# ------------------------------------------------------

def enrich_sovracomunali_con_tipo_precedente(
    input_json_path,
    output_json_path,
    idx_exact,
    idx_compact,
    idx_alias,
    fuzzy_names,
    fuzzy_rows,
    prov_by_name,
    prov_by_sigla,
    reg_by_name,
    fuzzy_threshold=95,
    overwrite_tipo=True,
    overwrite_prov_reg=False,
    debug_name=None
):
    with open(input_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    enriched = copy.deepcopy(data)

    n_match = 0
    n_match_forti = 0
    n_codici_geo = 0

    # solo questi metodi possono aggiornare davvero tipo/prov/regione
    metodi_forti = {"exact", "compact", "alias"}

    for file_item in enriched:
        soggetti = file_item.get("soggetti") or []

        for ent in soggetti:
            nome = (ent.get("nome") or "").strip()
            if not nome:
                continue

            matched_row, metodo, score = lookup_sovracomunale(
                nome,
                idx_exact,
                idx_compact,
                idx_alias,
                fuzzy_names,
                fuzzy_rows,
                fuzzy_threshold=fuzzy_threshold
            )

            if debug_name and debug_name.lower() in nome.lower():
                print("\nDEBUG")
                print("nome:", nome)
                print("norm:", _norm_text(nome))
                print("alias:", _norm_sovra_alias(nome))
                print("matched_row:", matched_row)
                print("metodo:", metodo)
                print("score:", score)

            if not matched_row:
                continue

            n_match += 1

            tipo_orig = (ent.get("tipo") or "").strip()
            tipo_finale = (matched_row.get("tipo_finale") or "").strip()

            province_list = matched_row.get("provincia", []) or []
            regioni_list = matched_row.get("regione", []) or []

            provincia_value = province_list[0] if len(province_list) == 1 else "; ".join(province_list)
            regione_value = regioni_list[0] if len(regioni_list) == 1 else "; ".join(regioni_list)

            # salva sempre metadati di debug match
            ent["match_ente_sovracomunale"] = True
            ent["match_ente_sovracomunale_metodo"] = metodo
            ent["match_ente_sovracomunale_score"] = score
            ent["match_ente_sovracomunale_nome"] = matched_row.get("nome_ente", "")

            # aggiorna i dati veri SOLO se il match è forte
            if metodo in metodi_forti:
                n_match_forti += 1

                if tipo_orig and tipo_orig != tipo_finale and not (ent.get("tipo_precedente") or "").strip():
                    ent["tipo_precedente"] = tipo_orig

                if overwrite_tipo and tipo_finale:
                    ent["tipo"] = tipo_finale

                if provincia_value and (overwrite_prov_reg or not (ent.get("provincia") or "").strip()):
                    ent["provincia"] = provincia_value

                if regione_value and (overwrite_prov_reg or not (ent.get("regione") or "").strip()):
                    ent["regione"] = regione_value

                ent["fonte_provincia_regione"] = "elenchi_sovracomunali"

                # Ente sovracomunale: NON deve avere codice comune.
                ent["codice_comune"] = ""

                geo = resolve_geo_from_lists(
                    province_list=province_list,
                    regioni_list=regioni_list,
                    prov_by_name=prov_by_name,
                    prov_by_sigla=prov_by_sigla,
                    reg_by_name=reg_by_name,
                )

                if geo.get("codice_provincia"):
                    ent["codice_provincia"] = geo["codice_provincia"]
                else:
                    ent.setdefault("codice_provincia", "")

                if geo.get("sigla_provincia"):
                    ent["sigla_provincia"] = geo["sigla_provincia"]
                else:
                    ent.setdefault("sigla_provincia", "")

                if geo.get("codice_regione"):
                    ent["codice_regione"] = geo["codice_regione"]
                else:
                    ent.setdefault("codice_regione", "")

                if ent.get("codice_provincia") or ent.get("codice_regione"):
                    n_codici_geo += 1

    with open(output_json_path, "w", encoding="utf-8") as f:
        json.dump(enriched, f, indent=2, ensure_ascii=False)

    print("✅ Enrichment completato")
    print("Match trovati (totali):", n_match)
    print("Match forti applicati:", n_match_forti)
    print("Entità con codici provincia/regione valorizzati:", n_codici_geo)
    print("Output:", output_json_path)


# ------------------------------------------------------
# REPORT HELPERS
# ------------------------------------------------------

def get_entities_list_ref(file_item: dict):
    """
    Restituisce il riferimento alla lista entità/soggetti da arricchire.
    Supporta:
    - vecchio formato: file_item["risultato"]["entities"]
    - nuovo formato:   file_item["soggetti"]
    """
    if isinstance(file_item.get("soggetti"), list):
        return file_item["soggetti"]
    risultato = file_item.get("risultato") or {}
    if isinstance(risultato.get("entities"), list):
        return risultato["entities"]
    return []


def report_enrichment(output_json_path):
    """Stampa un report rapido sull'output del processo di enrichment."""
    with open(output_json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    tot_changed = 0
    tot_flag = 0

    for file_item in data:
        entities = get_entities_list_ref(file_item)
        for ent in entities:
            if ent.get("match_ente_territoriale_tipo"):
                tot_changed += 1
            if ent.get("verifica_ente_sovracomunale") is True:
                tot_flag += 1

    print("Entità riclassificate:", tot_changed)
    print("Entità da verificare manualmente:", tot_flag)


def report_sample_entities(output_json_path):
    """Mostra un campione di entità filtrate per nome dall'output JSON."""
    with open(output_json_path, encoding="utf-8") as f:
        out_data = json.load(f)

    rows = []
    for item in out_data:
        for ent in item.get("soggetti", []):
            nome = ent.get("nome", "")
            if "Valli del Reno" in nome or "Terre d" in nome or "Appennino" in nome:
                rows.append({
                    "file": item.get("file", ""),
                    "nome": nome,
                    "tipo": ent.get("tipo", ""),
                    "tipo_precedente": ent.get("tipo_precedente", ""),
                    "provincia": ent.get("provincia", ""),
                    "regione": ent.get("regione", ""),
                    "metodo": ent.get("match_ente_sovracomunale_metodo", ""),
                    "nome_match": ent.get("match_ente_sovracomunale_nome", "")
                })

    df = pd.DataFrame(rows)
    print(df.to_string())
    return df


def debug_sovracomunali(sovracomunali_csv):
    """Stampa debug del dataset sovracomunali per entità specifiche."""
    df_sovra = load_sovracomunali_tables(sovracomunali_csv)

    mask_1 = df_sovra["nome_ente"].str.contains("Valli del Reno", case=False, na=False)
    mask_2 = df_sovra["nome_ente"].str.contains("Terre", case=False, na=False)

    print(df_sovra.loc[mask_1, ["nome_ente", "regione", "provincia", "tipo_finale"]])
    print(df_sovra.loc[mask_2, ["nome_ente", "regione", "provincia", "tipo_finale"]])

    print("\n--- DATASET COMPLETO ---")
    print("Righe totali:", len(df_sovra))
    print(df_sovra.to_string())


# ------------------------------------------------------
# MAIN RUN
# ------------------------------------------------------

def main():
    reg_code = "09"
    INPUT_JSON = Path(JSON_STEP1_FOLDER) / f"{reg_code}_risultati_enriched_2.1.2.json"
    OUTPUT_JSON = Path(JSON_STEP1_FOLDER) / f"{reg_code}_risultati_enriched_2.2.json"

    print("INPUT:", INPUT_JSON)
    print("OUTPUT:", OUTPUT_JSON)
    print("SOVRACOMUNALI_CSV:", SOVRACOMUNALI_CSV)
    print("PROVINCE_CSV:", PROVINCE_CSV)
    print("REGIONI_CSV:", REGIONI_CSV)

    df_sovra = load_sovracomunali_tables(SOVRACOMUNALI_CSV)
    df_province, df_regioni = load_province_regioni_tables(PROVINCE_CSV, REGIONI_CSV)

    idx_exact, idx_compact, idx_alias, fuzzy_names, fuzzy_rows = build_sovracomunali_index(df_sovra)
    prov_by_name, prov_by_sigla, reg_by_name = build_geo_lookup(df_province, df_regioni)

    enrich_sovracomunali_con_tipo_precedente(
        input_json_path=INPUT_JSON,
        output_json_path=OUTPUT_JSON,
        idx_exact=idx_exact,
        idx_compact=idx_compact,
        idx_alias=idx_alias,
        fuzzy_names=fuzzy_names,
        fuzzy_rows=fuzzy_rows,
        prov_by_name=prov_by_name,
        prov_by_sigla=prov_by_sigla,
        reg_by_name=reg_by_name,
        fuzzy_threshold=95,
        overwrite_tipo=True,
        overwrite_prov_reg=False,
        debug_name="UDI"
    )

    # Report
    report_enrichment(OUTPUT_JSON)
    report_sample_entities(OUTPUT_JSON)
    debug_sovracomunali(SOVRACOMUNALI_CSV)


if __name__ == "__main__":
    main()