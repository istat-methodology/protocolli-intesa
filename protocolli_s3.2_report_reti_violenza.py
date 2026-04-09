#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Pipeline S4 aggiornata per le reti territoriali contro la violenza sulle donne.

Questa versione:
- legge il JSON arricchito dei protocolli/reti
- legge i soggetti puliti prodotti da protocolli_s3.1_report_regcod_v4.py
- costruisce tabella_soggetti e tabella_reti coerenti con la V4
- genera prospetti/figure in formato tabellare
- esporta CSV, XLSX, report controlli e PNG

Uso consigliato:
    python protocolli_s4.1_reti_violenza_v4.py \
        --input-json 09_risultati_enriched_2.4.json \
        --soggetti-csv report_output_v4/soggetti_unici_puliti.csv \
        -o reti_output_v4

Figura 7 e Figura 8 non sono incluse: richiedono il dataset separato dei CAV 2024.
"""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt


REGIONI_ORDINE = [
    "Abruzzo", "Basilicata", "Bolzano/Bozen", "Calabria", "Campania",
    "Emilia-Romagna", "Friuli-Venezia Giulia", "Lazio", "Liguria",
    "Lombardia", "Marche", "Molise", "Piemonte", "Puglia", "Sardegna",
    "Sicilia", "Toscana", "Trento", "Umbria",
    "Valle d'Aosta/Vallée d'Aoste", "Veneto"
]

REGIONI_MAP = {
    "valle d'aosta": "Valle d'Aosta/Vallée d'Aoste",
    "valle d’aosta": "Valle d'Aosta/Vallée d'Aoste",
    "valle d'aosta/vallée d'aoste": "Valle d'Aosta/Vallée d'Aoste",
    "valle d’aosta/vallée d’aoste": "Valle d'Aosta/Vallée d'Aoste",
    "p.a. bolzano": "Bolzano/Bozen",
    "provincia autonoma di bolzano": "Bolzano/Bozen",
    "bolzano": "Bolzano/Bozen",
    "bozen": "Bolzano/Bozen",
    "p.a. trento": "Trento",
    "provincia autonoma di trento": "Trento",
    "trento": "Trento",
}

MACRO_ORDER = [
    "Enti territoriali / servizi comunali",
    "Province/Città metropolitane",
    "Regioni/Province Autonome",
    "Enti territoriali sovracomunali",
    "Ambiti socio-sanitari",
    "Sanità e servizi territoriali",
    "Giustizia e forze dell'ordine",
    "CAV e Case Rifugio",
    "Associazionismo",
    "Altri attori istituzionali / professionali",
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


def clean(s: Any) -> str:
    return str(s or "").strip()


def norm_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", clean(s)).strip()


def normalize_regione(value: Any) -> str:
    s = norm_spaces(str(value or ""))
    if not s:
        return ""
    k = s.lower()
    return REGIONI_MAP.get(k, s)


def safe_int(v: Any) -> int:
    try:
        if pd.isna(v):
            return 0
        return int(v)
    except Exception:
        return 0


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
    if not isinstance(data, list):
        raise ValueError("Il JSON di input deve contenere una lista di record")
    return data


def get_soggetti_list(file_item: dict) -> List[dict]:
    if isinstance(file_item.get("soggetti"), list):
        return file_item["soggetti"]
    risultato = file_item.get("risultato") or {}
    if isinstance(risultato.get("entities"), list):
        return risultato["entities"]
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
    candidates = []
    for _, row in df_soggetti_file.iterrows():
        reg = clean(row.get("regione"))
        if reg:
            candidates.append(normalize_regione(reg))
    if candidates:
        return Counter(candidates).most_common(1)[0][0]

    for ent in get_soggetti_list(file_item):
        reg = clean(ent.get("regione"))
        if reg:
            return normalize_regione(reg)

    file_name = clean(file_item.get("file")).lower()
    if file_name.startswith("09_"):
        return "Toscana"
    return ""


def infer_rete_provincia(file_item: dict, df_soggetti_file: pd.DataFrame) -> str:
    candidates = []
    for _, row in df_soggetti_file.iterrows():
        prov = clean(row.get("provincia"))
        if prov:
            candidates.append(prov)
    if candidates:
        return Counter(candidates).most_common(1)[0][0]

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

    if any(x in hay for x in ["regione ", "regionale", "provincia autonoma", "regione toscana", "giunta della regione"]):
        return "Ambito regionale/Prov. Autonome"
    if any(x in hay for x in ["città metropolitana", "citta metropolitana", "provincia di ", "provinciale", "area vasta"]):
        return "Area metropolitana/provinciale"
    if any(x in hay for x in ["distretto giudiziario", "corte d'appello", "corte d appello"]):
        return "Ambito distrettuale - legale"
    if any(x in hay for x in ["ats", "distretto sanitario", "casa della salute", "case della salute"]):
        return "Ambito sanitario coincidente con articolazioni locali delle Aziende Sanitarie Locali e/o Case della Salute e/o ATS"
    if any(x in hay for x in ["società della salute", "societa della salute", "piano di zona", "ambito sociale", "distretto socio-sanitario", "distretto sociosanitario", "conferenza dei sindaci asl", "conferenza zonale dei sindaci"]):
        return "Ambito sociale"
    if any(x in hay for x in ["unione dei comuni", "unione dei comuni montani", "unione montana", "comunità montana", "comunita montana"]):
        return "Ambito intercomunale (Unione comuni etc.)"

    if not df_soggetti_file.empty:
        tipi = set(df_soggetti_file["tipo_dettaglio"].dropna().astype(str))
        if "Ambiti della programmazione sociale e socio-sanitaria (Ambiti Sociali, Piani di Zona, Distretti socio-sanitari, Società della Salute)" in tipi:
            return "Ambito sociale"
        if "Enti territoriali sovracomunali" in tipi:
            return "Ambito intercomunale (Unione comuni etc.)"
        if "Province/Città metropolitane" in tipi or "Polizia provinciale" in tipi:
            return "Area metropolitana/provinciale"
        if "Regioni/Province Autonome" in tipi:
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


def compute_dominant_macro(df_file_valid: pd.DataFrame) -> str:
    if df_file_valid.empty:
        return ""
    attori = df_file_valid.loc[df_file_valid["ruolo_attore"] == 1].copy()
    if attori.empty:
        attori = df_file_valid.copy()
    counts = attori["macro_tipologia"].value_counts()
    return counts.index[0] if not counts.empty else ""


def build_tabella_soggetti_from_v4(df_soggetti_v4: pd.DataFrame, input_json_name: str) -> pd.DataFrame:
    df = df_soggetti_v4.copy()

    required = {
        "file", "nome_canonico", "tipo_standard", "macro_categoria",
        "regione_finale", "provincia_finale", "comune_finale",
        "stato_osservazione", "ruolo_attore", "ruolo_firmatario", "ruolo_proponente"
    }
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"Mancano colonne nel CSV V4: {sorted(missing)}")

    df = df.loc[df["stato_osservazione"].isin(["valido_localizzato", "valido_non_localizzato"])].copy()

    df["id_rete"] = df["file"].astype(str)
    df["input_json"] = input_json_name
    df["titolo_rete"] = df["file"].astype(str).map(lambda x: re.sub(r"^\d{2}[_ ]+", "", Path(x).stem))
    df["regione"] = df["regione_finale"].astype(str).map(normalize_regione)
    df["provincia"] = df["provincia_finale"].astype(str)
    df["comune_soggetto"] = df["comune_finale"].astype(str)
    df["nome_soggetto"] = df["nome_canonico"].astype(str)
    df["tipo_dettaglio"] = df["tipo_standard"].astype(str)
    df["macro_tipologia"] = df["macro_categoria"].astype(str)
    if "ruoli_documentali_aggregati" in df.columns:
        df["ruolo_testo"] = df["ruoli_documentali_aggregati"].astype(str)
    elif "ruoli_documentali" in df.columns:
        df["ruolo_testo"] = df["ruoli_documentali"].astype(str)
    else:
        df["ruolo_testo"] = ""
    df["ruolo_proponente"] = df["ruolo_proponente"].apply(safe_int)
    df["ruolo_attore"] = df["ruolo_attore"].apply(safe_int)
    df["ruolo_firmatario"] = df["ruolo_firmatario"].apply(safe_int)

    cols = [
        "id_rete", "input_json", "file", "titolo_rete", "regione", "provincia",
        "nome_soggetto", "tipo_dettaglio", "macro_tipologia",
        "ruolo_proponente", "ruolo_attore", "ruolo_firmatario", "ruolo_testo",
        "comune_soggetto", "stato_osservazione", "fonte_territorializzazione",
    ]
    for c in cols:
        if c not in df.columns:
            df[c] = ""

    out = df[cols].copy()
    out = out.sort_values(["file", "macro_tipologia", "tipo_dettaglio", "nome_soggetto"]).reset_index(drop=True)
    return out


def build_tabella_reti_from_json(data: List[dict], tab_soggetti: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []
    for file_item in data:
        file_name = clean(file_item.get("file"))
        df_file = tab_soggetti.loc[tab_soggetti["file"] == file_name].copy()
        regione = infer_rete_region(file_item, df_file)
        provincia = infer_rete_provincia(file_item, df_file)
        ambito = infer_ambito_territoriale(file_item, df_file)
        dominant_macro = compute_dominant_macro(df_file)

        n_prop = int(df_file["ruolo_proponente"].sum()) if not df_file.empty else 0
        n_att = int(df_file["ruolo_attore"].sum()) if not df_file.empty else 0
        n_tot = int(df_file["nome_soggetto"].nunique()) if not df_file.empty else 0
        cluster = f"{dominant_macro} - {ambito}" if dominant_macro and ambito else ""

        rows.append({
            "id_rete": file_name,
            "file": file_name,
            "titolo_rete": get_file_title(file_item),
            "regione": regione,
            "provincia": provincia,
            "atto_formale": infer_atto_formale(file_item),
            "tipo_atto": "Atto formale" if infer_atto_formale(file_item) == 1 else "",
            "ambito_territoriale": ambito,
            "n_soggetti_proponenti": n_prop,
            "n_attori_coinvolti": n_att,
            "n_totale_soggetti": n_tot,
            "macro_tipologia_dominante_attori": dominant_macro,
            "cluster_figura6": cluster,
            "ambito_note": ambito,
        })

    out = pd.DataFrame(rows)
    if not out.empty:
        out["regione"] = out["regione"].map(normalize_regione)
        out = sort_region_df(out, "regione")
    return out


def prospetto1(tab_reti: pd.DataFrame) -> pd.DataFrame:
    df = tab_reti.loc[tab_reti["atto_formale"] == 1].groupby("regione", dropna=False).agg(
        numero_reti_avviate_da_atto_formale=("id_rete", "nunique")
    ).reset_index()
    return sort_region_df(df, "regione")


def figura1(tab_soggetti: pd.DataFrame, by_macro: bool = False) -> pd.DataFrame:
    col = "macro_tipologia" if by_macro else "tipo_dettaglio"
    df = tab_soggetti.loc[tab_soggetti["ruolo_proponente"] == 1].groupby(col, dropna=False).agg(
        numero=("nome_soggetto", "size")
    ).reset_index().rename(columns={col: "tipologia"})
    return df.sort_values(["numero", "tipologia"], ascending=[False, True]).reset_index(drop=True)


def figura2(tab_soggetti: pd.DataFrame) -> pd.DataFrame:
    df = tab_soggetti.loc[tab_soggetti["ruolo_proponente"] == 1].groupby("regione", dropna=False).agg(
        soggetti_proponenti=("nome_soggetto", "size")
    ).reset_index()
    return sort_region_df(df, "regione")


def prospetto2(tab_soggetti: pd.DataFrame) -> pd.DataFrame:
    base = tab_soggetti.loc[tab_soggetti["ruolo_proponente"] == 1].copy()
    agg = base.groupby(["regione", "macro_tipologia"], dropna=False).agg(n=("nome_soggetto", "size")).reset_index()
    tot = agg.groupby("regione", dropna=False)["n"].sum().reset_index(name="tot_regione")
    out = agg.merge(tot, on="regione", how="left")
    out["percentuale"] = (out["n"] / out["tot_regione"] * 100).round(1)
    out = out.rename(columns={"macro_tipologia": "tipologia_dei_soggetti"})[
        ["regione", "tipologia_dei_soggetti", "percentuale", "n", "tot_regione"]
    ]
    return sort_region_df(out, "regione")


def figura3(tab_soggetti: pd.DataFrame) -> pd.DataFrame:
    df = tab_soggetti.loc[tab_soggetti["ruolo_attore"] == 1].groupby("macro_tipologia", dropna=False).agg(
        numero=("nome_soggetto", "size")
    ).reset_index().rename(columns={"macro_tipologia": "tipologia"})
    order_map = {k: i for i, k in enumerate(MACRO_ORDER)}
    df["_ord"] = df["tipologia"].map(order_map).fillna(999)
    return df.sort_values(["numero", "_ord", "tipologia"], ascending=[False, True, True]).drop(columns=["_ord"]).reset_index(drop=True)


def figura4(tab_soggetti: pd.DataFrame) -> pd.DataFrame:
    prop = tab_soggetti.loc[tab_soggetti["ruolo_proponente"] == 1].groupby("regione", dropna=False).agg(
        soggetti_proponenti=("nome_soggetto", "size")
    ).reset_index()
    att = tab_soggetti.loc[tab_soggetti["ruolo_attore"] == 1].groupby("regione", dropna=False).agg(
        attori_coinvolti=("nome_soggetto", "size")
    ).reset_index()
    df = prop.merge(att, on="regione", how="outer").fillna(0)
    for c in ["soggetti_proponenti", "attori_coinvolti"]:
        df[c] = df[c].astype(int)
    return sort_region_df(df, "regione")


def figura5(tab_reti: pd.DataFrame) -> pd.DataFrame:
    df = tab_reti.groupby("ambito_territoriale", dropna=False).agg(numero=("id_rete", "nunique")).reset_index()
    df = df.rename(columns={"ambito_territoriale": "ambito"})
    order_map = {k: i for i, k in enumerate(AMBITO_ORDER)}
    df["_ord"] = df["ambito"].map(order_map).fillna(999)
    return df.sort_values(["numero", "_ord", "ambito"], ascending=[False, True, True]).drop(columns=["_ord"]).reset_index(drop=True)


def figura6(tab_reti: pd.DataFrame) -> pd.DataFrame:
    base = tab_reti.loc[tab_reti["cluster_figura6"].astype(str) != ""].copy()
    if base.empty:
        return pd.DataFrame(columns=["cluster", "n_reti", "percentuale_reti", "n_regioni_pa"])

    tot_reti = base["id_rete"].nunique()
    agg = base.groupby("cluster_figura6", dropna=False).agg(
        n_reti=("id_rete", "nunique"),
        n_regioni_pa=("regione", "nunique"),
    ).reset_index().rename(columns={"cluster_figura6": "cluster"})
    agg["percentuale_reti"] = (agg["n_reti"] / tot_reti * 100).round(1)
    return agg.sort_values(["percentuale_reti", "n_regioni_pa", "cluster"], ascending=[False, False, True]).reset_index(drop=True)


def export_outputs(output_dir: Path, tables: Dict[str, pd.DataFrame], report_text: str) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, df in tables.items():
        df.to_csv(output_dir / f"{name}.csv", index=False, encoding="utf-8")

    xlsx_path = output_dir / "output_completo_reti_violenza.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        for name, df in tables.items():
            df.to_excel(writer, index=False, sheet_name=name[:31])

    (output_dir / "report_controlli.txt").write_text(report_text, encoding="utf-8")


def autosize_width(n_rows: int, base: float = 10.0, scale: float = 0.25, max_size: float = 18.0) -> float:
    return min(base + n_rows * scale, max_size)


def save_barh(df: pd.DataFrame, y_col: str, x_col: str, title: str, out_path: Path) -> None:
    if df.empty:
        return
    plot_df = df.copy().sort_values(x_col, ascending=True)
    h = autosize_width(len(plot_df), base=4.0, scale=0.20, max_size=16.0)
    plt.figure(figsize=(12, h))
    plt.barh(plot_df[y_col].astype(str), plot_df[x_col])
    plt.title(title)
    plt.xlabel("")
    plt.ylabel("")
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()


def save_figura4_grouped(df: pd.DataFrame, out_path: Path) -> None:
    if df.empty:
        return
    plot_df = df.copy()
    x = range(len(plot_df))
    width = 0.42
    plt.figure(figsize=(12, autosize_width(len(plot_df), base=4.0, scale=0.15, max_size=10.0)))
    plt.barh([i - width / 2 for i in x], plot_df["soggetti_proponenti"], height=width, label="Soggetti proponenti")
    plt.barh([i + width / 2 for i in x], plot_df["attori_coinvolti"], height=width, label="Attori coinvolti")
    plt.yticks(list(x), plot_df["regione"].astype(str))
    plt.title("Figura 4. Soggetti proponenti e attori coinvolti nelle reti territoriali per regione/provincia autonoma")
    plt.xlabel("Numero")
    plt.ylabel("")
    plt.legend()
    plt.tight_layout()
    plt.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close()


def save_figura6_dual_axis(df: pd.DataFrame, out_path: Path) -> None:
    if df.empty:
        return
    plot_df = df.copy().sort_values(["percentuale_reti", "n_regioni_pa"], ascending=[False, False]).head(20)
    x = range(len(plot_df))
    fig, ax1 = plt.subplots(figsize=(14, autosize_width(len(plot_df), base=6.0, scale=0.18, max_size=10.0)))
    ax1.bar(x, plot_df["percentuale_reti"])
    ax1.set_ylabel("Percentuale reti")
    ax1.set_title("Figura 6. Attori dominanti e ambiti territoriali per cluster")
    ax1.set_xticks(list(x))
    ax1.set_xticklabels(plot_df["cluster"].astype(str), rotation=45, ha="right")

    ax2 = ax1.twinx()
    ax2.plot(x, plot_df["n_regioni_pa"], marker="o")
    ax2.set_ylabel("Numero regioni/PA")

    fig.tight_layout()
    fig.savefig(out_path, dpi=200, bbox_inches="tight")
    plt.close(fig)


def export_png_charts(output_dir: Path, tables: Dict[str, pd.DataFrame], figura1_by_macro: bool) -> None:
    png_dir = output_dir / "png"
    png_dir.mkdir(parents=True, exist_ok=True)

    save_barh(tables["figura1_soggetti_promotori_per_tipo"], "tipologia", "numero", "Figura 1. Soggetti promotori per tipo", png_dir / "figura1_soggetti_promotori_per_tipo.png")
    save_barh(tables["figura2_soggetti_proponenti_per_regione"], "regione", "soggetti_proponenti", "Figura 2. Soggetti proponenti per regione/provincia autonoma", png_dir / "figura2_soggetti_proponenti_per_regione.png")
    save_barh(tables["figura3_attori_coinvolti_per_tipo"], "tipologia", "numero", "Figura 3. Attori coinvolti nei protocolli/accordi territoriali per tipo", png_dir / "figura3_attori_coinvolti_per_tipo.png")
    save_figura4_grouped(tables["figura4_proponenti_vs_attori_per_regione"], png_dir / "figura4_proponenti_vs_attori_per_regione.png")
    save_barh(tables["figura5_ambiti_territoriali"], "ambito", "numero", "Figura 5. Ambiti territoriali coinvolti dai protocolli/accordi", png_dir / "figura5_ambiti_territoriali.png")
    save_figura6_dual_axis(tables["figura6_cluster"], png_dir / "figura6_cluster.png")

    legenda = [
        "PNG generati:",
        "- figura1_soggetti_promotori_per_tipo.png",
        "- figura2_soggetti_proponenti_per_regione.png",
        "- figura3_attori_coinvolti_per_tipo.png",
        "- figura4_proponenti_vs_attori_per_regione.png",
        "- figura5_ambiti_territoriali.png",
        "- figura6_cluster.png",
        f"- Figura 1 aggregata per {'macro_tipologia' if figura1_by_macro else 'tipo_dettaglio'}",
    ]
    (png_dir / "README_png.txt").write_text("\n".join(legenda), encoding="utf-8")


def build_quality_report(tab_soggetti: pd.DataFrame, tab_reti: pd.DataFrame, prospetto2_df: pd.DataFrame, soggetti_csv_path: Path) -> str:
    lines = []
    lines.append("REPORT CONTROLLI S4")
    lines.append("")
    lines.append(f"Sorgente soggetti puliti V4: {soggetti_csv_path}")
    lines.append(f"Numero righe tabella_soggetti: {len(tab_soggetti)}")
    lines.append(f"Numero reti/protocolli: {len(tab_reti)}")
    lines.append(f"Numero regioni/PA tabella_reti: {tab_reti['regione'].nunique(dropna=True) if not tab_reti.empty else 0}")
    lines.append("")

    if not tab_soggetti.empty:
        lines.append("Macro-tipologie in tabella_soggetti:")
        for k, v in tab_soggetti["macro_tipologia"].value_counts().items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    if not tab_reti.empty:
        lines.append("Ambiti territoriali in tabella_reti:")
        for k, v in tab_reti["ambito_territoriale"].value_counts().items():
            lines.append(f"- {k}: {v}")
        lines.append("")

    if not prospetto2_df.empty:
        check = prospetto2_df.groupby("regione", dropna=False)["percentuale"].sum().reset_index()
        lines.append("Controllo somme percentuali Prospetto 2:")
        for _, row in check.iterrows():
            lines.append(f"- {row['regione']}: {row['percentuale']}")
        lines.append("")

    return "\n".join(lines)


def _main() -> None:


    input_path = Path(r"\output\json\merged\all_risultati_enriched_2.4.json")
    soggetti_csv_path = Path(r"\output\reports\soggetti_unici_puliti.csv")
    output_dir= Path(r"output\reti_violenza")   


    if not input_path.exists():
        raise FileNotFoundError(f"File input JSON non trovato: {input_path}")
    if not soggetti_csv_path.exists():
        raise FileNotFoundError(f"CSV soggetti puliti non trovato: {soggetti_csv_path}")

    data = load_json(input_path)
    df_soggetti_v4 = read_csv_flexible(soggetti_csv_path)

    tab_soggetti = build_tabella_soggetti_from_v4(df_soggetti_v4, input_path.name)
    tab_reti = build_tabella_reti_from_json(data, tab_soggetti)

    tables = {
        "tabella_soggetti": tab_soggetti,
        "tabella_reti": tab_reti,
        "prospetto1_reti_per_regione": prospetto1(tab_reti),
        "figura1_soggetti_promotori_per_tipo": figura1(tab_soggetti, by_macro=args.figura1_by_macro),
        "figura2_soggetti_proponenti_per_regione": figura2(tab_soggetti),
        "prospetto2_soggetti_promotori_percentuali": prospetto2(tab_soggetti),
        "figura3_attori_coinvolti_per_tipo": figura3(tab_soggetti),
        "figura4_proponenti_vs_attori_per_regione": figura4(tab_soggetti),
        "figura5_ambiti_territoriali": figura5(tab_reti),
        "figura6_cluster": figura6(tab_reti),
    }

    report_text = build_quality_report(tab_soggetti, tab_reti, tables["prospetto2_soggetti_promotori_percentuali"], soggetti_csv_path)
    
    export_outputs(output_dir, tables, report_text)

    if not args.no_png:
        export_png_charts(output_dir, tables, args.figura1_by_macro)

    print("Pipeline S4 aggiornata completata.")
    print(f"Input JSON: {input_path}")
    print(f"Soggetti CSV V4: {soggetti_csv_path}")
    print(f"Output dir: {output_dir.resolve()}")
    print("File principali generati:")
    print("- tabella_soggetti.csv")
    print("- tabella_reti.csv")
    print("- output_completo_reti_violenza.xlsx")
    print("- report_controlli.txt")
    if not args.no_png:
        print("- cartella png/ con i grafici delle Figure 1-6")

# =========================================================
# CONFIG FISSA
# =========================================================
INPUT_JSON = Path(r"G:\develpment\protocolli-intesa\output\json\merged\all_risultati_enriched_2.4.json")
SOGGETTI_CSV = Path(r"G:\develpment\protocolli-intesa\output\reports\soggetti_unici_puliti.csv")
OUTPUT_DIR = Path(r"G:\develpment\protocolli-intesa\output\reti_violenza")


# =========================================================
# MAIN
# =========================================================
def main():
    input_path = INPUT_JSON
    soggetti_csv_path = SOGGETTI_CSV
    output_dir = OUTPUT_DIR

    if not input_path.exists():
        raise FileNotFoundError(f"JSON input non trovato: {input_path}")

    if not soggetti_csv_path.exists():
        raise FileNotFoundError(f"CSV soggetti puliti non trovato: {soggetti_csv_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    print("📂 INPUT_JSON   :", input_path)
    print("📄 SOGGETTI_CSV :", soggetti_csv_path)
    print("💾 OUTPUT_DIR   :", output_dir)

    data = load_json(input_path)
    df_soggetti_v4 = read_csv_flexible(soggetti_csv_path)

    print(f"📚 Record protocolli caricati: {len(data)}")
    print(f"📄 Righe CSV soggetti: {len(df_soggetti_v4)}")

    tab_soggetti = build_tabella_soggetti_from_v4(df_soggetti_v4, input_path.name)
    tab_reti = build_tabella_reti_from_json(data, tab_soggetti)

    print(f"📊 Tabella soggetti: {len(tab_soggetti)} righe")
    print(f"📊 Tabella reti: {len(tab_reti)} righe")

    tables = {
        "tabella_soggetti": tab_soggetti,
        "tabella_reti": tab_reti,
        "prospetto1_reti_per_regione": prospetto1(tab_reti),
        "figura1_soggetti_promotori_per_tipo": figura1(tab_soggetti, by_macro=False),
        "figura2_soggetti_proponenti_per_regione": figura2(tab_soggetti),
        "prospetto2_soggetti_promotori_percentuali": prospetto2(tab_soggetti),
        "figura3_attori_coinvolti_per_tipo": figura3(tab_soggetti),
        "figura4_proponenti_vs_attori_per_regione": figura4(tab_soggetti),
        "figura5_ambiti_territoriali": figura5(tab_reti),
        "figura6_cluster": figura6(tab_reti),
    }

    report_text = build_quality_report(
        tab_soggetti,
        tab_reti,
        tables["prospetto2_soggetti_promotori_percentuali"],
        soggetti_csv_path
    )

    export_outputs(output_dir, tables, report_text)
    export_png_charts(output_dir, tables, False)

    print("\n✅ Export completato")
    print(" -", output_dir)
    

if __name__ == "__main__":
    main()

