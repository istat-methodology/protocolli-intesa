#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Iterable, List

import pandas as pd

INPUT_JSON = Path(r"output\data\step_3.0\3.0_risultati_enriched_merged_geo.json")
OUTPUT_DIR = Path(r"output\data\step_3.0.2")


REGIONI_ORDINE = [
    "Abruzzo", "Basilicata", "Bolzano/Bozen", "Calabria", "Campania",
    "Emilia-Romagna", "Friuli-Venezia Giulia", "Lazio", "Liguria",
    "Lombardia", "Marche", "Molise", "Piemonte", "Puglia", "Sardegna",
    "Sicilia", "Toscana", "Trento", "Umbria",
    "Valle d'Aosta/Vallée d'Aoste", "Veneto"
]

EXCLUDED_REASON_ORDER = [
    "manca_riferimento_territoriale",
    "territorio_non_riconosciuto",
    "soggetto_non_territoriale",
    "coordinate_non_generate",
    "altro",
]


def clean_text(x: Any) -> str:
    if x is None:
        return ""
    s = str(x).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def normalize_name(s: str) -> str:
    if not isinstance(s, str):
        return ""
    s0 = s.strip().casefold()
    s1 = "".join(
        c for c in unicodedata.normalize("NFKD", s0)
        if not unicodedata.combining(c)
    )
    s1 = s1.replace("\u2019", "'").replace("`", "'").replace("\u00b4", "'")
    s1 = re.sub(r"\s+", " ", s1).strip()
    return s1


def normalize_regione(value: Any) -> str:
    s = clean_text(value)
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


def sort_region_df(df: pd.DataFrame, col: str = "regione") -> pd.DataFrame:
    if df.empty or col not in df.columns:
        return df
    order_map = {r: i for i, r in enumerate(REGIONI_ORDINE)}
    out = df.copy()
    out[col] = out[col].astype(str).map(normalize_regione)
    out["_ord"] = out[col].map(order_map).fillna(9999)
    out = out.sort_values(["_ord", col]).drop(columns=["_ord"])
    return out.reset_index(drop=True)


def to_bool(x: Any) -> int:
    if isinstance(x, bool):
        return int(x)
    if isinstance(x, (int, float)):
        return int(x == 1)
    if isinstance(x, str):
        return int(x.strip().lower() in {"1", "true", "yes", "si", "sì", "x"})
    return 0


def to_float_or_none(x: Any):
    try:
        return float(x)
    except Exception:
        return None


def has_valid_coords(ent: dict) -> bool:
    lat = to_float_or_none(ent.get("lat"))
    lon = to_float_or_none(ent.get("lon"))
    return lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180


def iter_items(obj: Any):
    if isinstance(obj, dict):
        if "soggetti" in obj or "entities" in obj:
            yield obj
        for v in obj.values():
            yield from iter_items(v)
    elif isinstance(obj, list):
        for item in obj:
            yield from iter_items(item)


def iter_entities(item: dict) -> list[dict]:
    if not isinstance(item, dict):
        return []
    if isinstance(item.get("soggetti"), list):
        return [x for x in item["soggetti"] if isinstance(x, dict)]
    if isinstance(item.get("entities"), list):
        return [x for x in item["entities"] if isinstance(x, dict)]
    return []


def guess_exclusion_reason(ent: dict) -> str:
    comune = clean_text(ent.get("comune") or ent.get("comune_matchato"))
    provincia = clean_text(ent.get("provincia") or ent.get("sigla_provincia"))
    regione = clean_text(ent.get("regione"))
    livello = clean_text(ent.get("livello_territoriale")).lower()
    nome = clean_text(ent.get("nome")).lower()
    tipo = clean_text(ent.get("tipo")).lower()

    if not comune and not provincia and not regione:
        if any(k in f"{nome} | {tipo}" for k in ["tavolo", "cabina", "gruppo", "direzione", "servizio", "sportello", "cav n."]):
            return "soggetto_non_territoriale"
        return "manca_riferimento_territoriale"

    if livello in {"comune", "provincia", "regione"}:
        return "coordinate_non_generate"

    return "territorio_non_riconosciuto"


def load_records(input_json: Path) -> pd.DataFrame:
    data = json.loads(input_json.read_text(encoding="utf-8"))
    rows: list[dict] = []

    for item in iter_items(data):
        file_name = clean_text(item.get("file") or item.get("files") or "")
        for ent in iter_entities(item):
            lat = to_float_or_none(ent.get("lat"))
            lon = to_float_or_none(ent.get("lon"))
            ruolo_raw = ent.get("ruolo", [])
            if isinstance(ruolo_raw, list):
                ruolo_txt = ", ".join(clean_text(x) for x in ruolo_raw if clean_text(x))
            else:
                ruolo_txt = clean_text(ruolo_raw)

            rows.append({
                "file": file_name,
                "nome": clean_text(ent.get("nome")),
                "tipo": clean_text(ent.get("tipo")),
                "comune": clean_text(ent.get("comune") or ent.get("comune_matchato")),
                "provincia": clean_text(ent.get("provincia")),
                "sigla_provincia": clean_text(ent.get("sigla_provincia")).upper(),
                "regione": normalize_regione(ent.get("regione")),
                "livello_territoriale": clean_text(ent.get("livello_territoriale")).lower(),
                "lat": lat,
                "lon": lon,
                "ha_coordinate": int(lat is not None and lon is not None and -90 <= lat <= 90 and -180 <= lon <= 180),
                "ruolo": ruolo_txt,
                "governance_detail": clean_text(ent.get("governance_detail")),
                "is_firmatario": to_bool(ent.get("is_firmatario")),
                "is_proponente": to_bool(ent.get("is_proponente")),
                "is_attore": to_bool(ent.get("is_attore")),
                "is_gestione": to_bool(ent.get("is_gestione")),
                "is_monitoraggio": to_bool(ent.get("is_monitoraggio")),
                "is_coordinamento": to_bool(ent.get("is_coordinamento")),
                "is_governance": to_bool(ent.get("is_governance")),
                "is_governance_generica": to_bool(ent.get("is_governance_generica")),
                "is_ente_capofila": to_bool(ent.get("is_ente_capofila")),
                "ente_capofila": clean_text(ent.get("ente_capofila")),
                "note": clean_text(ent.get("note")),
            })

    df = pd.DataFrame(rows)
    for c in [
        "is_firmatario", "is_proponente", "is_attore", "is_gestione", "is_monitoraggio",
        "is_coordinamento", "is_governance", "is_governance_generica", "is_ente_capofila", "ha_coordinate"
    ]:
        if c not in df.columns:
            df[c] = 0
        df[c] = df[c].fillna(0).astype(int)

    df["regione"] = df["regione"].fillna("").astype(str).map(normalize_regione)
    df["provincia"] = df["provincia"].fillna("").astype(str)
    df["comune"] = df["comune"].fillna("").astype(str)
    df["id_soggetto_geo"] = [
        " | ".join([
            normalize_name(r.nome), normalize_name(r.tipo), normalize_name(r.comune),
            normalize_name(r.provincia), normalize_name(r.regione), normalize_name(r.file)
        ])
        for r in df.itertuples(index=False)
    ]
    return df


def safe_write_csv(df: pd.DataFrame, out_file: Path) -> Path:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    try:
        if out_file.exists():
            out_file.unlink()
        df.to_csv(out_file, index=False, encoding="utf-8-sig")
        return out_file
    except PermissionError:
        alt_file = out_file.with_name(f"{out_file.stem}_NEW{out_file.suffix}")
        df.to_csv(alt_file, index=False, encoding="utf-8-sig")
        return alt_file


def build_summary(df: pd.DataFrame, level_col: str) -> pd.DataFrame:
    cols = [
        "is_firmatario", "is_proponente", "is_attore", "is_gestione", "is_monitoraggio",
        "is_coordinamento", "is_governance", "is_governance_generica", "is_ente_capofila"
    ]
    use = df[df[level_col].fillna("").astype(str).str.strip() != ""].copy()
    if use.empty:
        return pd.DataFrame(columns=[level_col, "totale_soggetti", "firmatari", "proponenti", "attori", "gestione", "monitoraggio", "coordinamento", "governance_totale", "governance_generica", "ente_capofila"])
    grouped = use.groupby(level_col).agg({
        "id_soggetto_geo": pd.Series.nunique,
        "is_firmatario": "sum",
        "is_proponente": "sum",
        "is_attore": "sum",
        "is_gestione": "sum",
        "is_monitoraggio": "sum",
        "is_coordinamento": "sum",
        "is_governance": "sum",
        "is_governance_generica": "sum",
        "is_ente_capofila": "sum",
    }).reset_index()
    grouped = grouped.rename(columns={
        "id_soggetto_geo": "totale_soggetti",
        "is_firmatario": "firmatari",
        "is_proponente": "proponenti",
        "is_attore": "attori",
        "is_gestione": "gestione",
        "is_monitoraggio": "monitoraggio",
        "is_coordinamento": "coordinamento",
        "is_governance": "governance_totale",
        "is_governance_generica": "governance_generica",
        "is_ente_capofila": "ente_capofila",
    })
    if level_col == "regione":
        grouped = sort_region_df(grouped, "regione")
    else:
        grouped = grouped.sort_values([level_col]).reset_index(drop=True)
    return grouped


def build_excluded_detail(df_all: pd.DataFrame) -> pd.DataFrame:
    df_exc = df_all.loc[df_all["ha_coordinate"] == 0].copy()
    if df_exc.empty:
        return df_exc
    df_exc["motivo_esclusione"] = [guess_exclusion_reason(rec._asdict()) for rec in df_exc.itertuples(index=False)]
    df_exc["peso_ruolo"] = (
        df_exc[["is_firmatario", "is_proponente", "is_attore", "is_governance", "is_ente_capofila"]]
        .sum(axis=1)
        .astype(int)
    )
    cols = [
        "file", "nome", "tipo", "ruolo", "regione", "provincia", "comune", "livello_territoriale",
        "motivo_esclusione", "peso_ruolo", "is_firmatario", "is_proponente", "is_attore", "is_gestione",
        "is_monitoraggio", "is_coordinamento", "is_governance", "is_governance_generica", "is_ente_capofila",
        "ente_capofila", "note"
    ]
    return df_exc[cols].sort_values(["peso_ruolo", "regione", "provincia", "comune", "nome"], ascending=[False, True, True, True, True]).reset_index(drop=True)


def write_txt_report(path: Path, df_all: pd.DataFrame, df_map: pd.DataFrame, reg: pd.DataFrame, prov: pd.DataFrame, com: pd.DataFrame, df_exc: pd.DataFrame) -> None:
    lines: list[str] = []
    lines.append("REPORT MAPPABILI ED ESCLUSI")
    lines.append(f"Input JSON: {INPUT_JSON}")
    lines.append("")
    lines.append("1) SINTESI GENERALE")
    total = len(df_all)
    mapped = len(df_map)
    excluded = len(df_exc)
    lines.append(f"- soggetti_totali: {total}")
    lines.append(f"- soggetti_mappabili: {mapped}")
    lines.append(f"- soggetti_esclusi_dalla_mappa: {excluded}")
    lines.append(f"- percentuale_mappabili: {round(mapped / max(total,1) * 100, 2)}%")
    lines.append("")
    lines.append("2) MAPPABILI PER REGIONE")
    if reg.empty:
        lines.append("- nessun dato")
    else:
        for _, r in reg.iterrows():
            lines.append(f"- {r['regione']}: totale={int(r['totale_soggetti'])}, firmatari={int(r['firmatari'])}, proponenti={int(r['proponenti'])}, attori={int(r['attori'])}, governance={int(r['governance_totale'])}, capofila={int(r['ente_capofila'])}")
    lines.append("")
    lines.append("3) MAPPABILI PER PROVINCIA")
    if prov.empty:
        lines.append("- nessun dato")
    else:
        for _, r in prov.head(100).iterrows():
            lines.append(f"- {r['provincia']}: totale={int(r['totale_soggetti'])}, firmatari={int(r['firmatari'])}, proponenti={int(r['proponenti'])}, attori={int(r['attori'])}, governance={int(r['governance_totale'])}, capofila={int(r['ente_capofila'])}")
    lines.append("")
    lines.append("4) MAPPABILI PER COMUNE")
    if com.empty:
        lines.append("- nessun dato")
    else:
        for _, r in com.head(150).iterrows():
            lines.append(f"- {r['comune']}: totale={int(r['totale_soggetti'])}, firmatari={int(r['firmatari'])}, proponenti={int(r['proponenti'])}, attori={int(r['attori'])}, governance={int(r['governance_totale'])}, capofila={int(r['ente_capofila'])}")
    lines.append("")
    lines.append("5) ESCLUSI DALLA MAPPA - RIEPILOGO")
    if df_exc.empty:
        lines.append("- nessun escluso")
    else:
        by_reason = df_exc.groupby("motivo_esclusione").size().reindex(EXCLUDED_REASON_ORDER, fill_value=0)
        for k, v in by_reason.items():
            lines.append(f"- {k}: {int(v)}")
        lines.append("")
        lines.append(f"- esclusi_firmatari: {int(df_exc['is_firmatario'].sum())}")
        lines.append(f"- esclusi_proponenti: {int(df_exc['is_proponente'].sum())}")
        lines.append(f"- esclusi_attori: {int(df_exc['is_attore'].sum())}")
        lines.append(f"- esclusi_governance: {int(df_exc['is_governance'].sum())}")
        lines.append(f"- esclusi_enti_capofila: {int(df_exc['is_ente_capofila'].sum())}")
        lines.append("")
        lines.append("Top esclusi per peso/ruolo")
        for _, r in df_exc.head(50).iterrows():
            lines.append(f"- {r['nome']} | ruolo={r['ruolo']} | regione={r['regione']} | provincia={r['provincia']} | comune={r['comune']} | motivo={r['motivo_esclusione']} | file={r['file']}")
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Report sintetico soggetti mappabili ed esclusi per regione/provincia/comune.")
    parser.add_argument("--input-json", default=str(INPUT_JSON))
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    args = parser.parse_args()

    input_json = Path(args.input_json)
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_json.exists():
        raise FileNotFoundError(f"JSON input non trovato: {input_json}")

    print("📂 INPUT_JSON:", input_json)
    print("💾 OUTPUT_DIR:", output_dir)

    df_all = load_records(input_json)
    df_map = df_all.loc[df_all["ha_coordinate"] == 1].copy()
    df_exc = build_excluded_detail(df_all)

    reg = build_summary(df_map, "regione")
    prov = build_summary(df_map, "provincia")
    com = build_summary(df_map, "comune")

    written = []
    written.append(safe_write_csv(df_all, output_dir / "tabella_soggetti_geo_ruoli.csv"))
    written.append(safe_write_csv(df_map, output_dir / "soggetti_mappabili_dettaglio.csv"))
    written.append(safe_write_csv(reg, output_dir / "mappabili_per_regione.csv"))
    written.append(safe_write_csv(prov, output_dir / "mappabili_per_provincia.csv"))
    written.append(safe_write_csv(com, output_dir / "mappabili_per_comune.csv"))
    written.append(safe_write_csv(df_exc, output_dir / "soggetti_esclusi_mappa_dettaglio.csv"))

    if not df_exc.empty:
        exc_reason = df_exc.groupby("motivo_esclusione").size().reset_index(name="totale")
        written.append(safe_write_csv(exc_reason, output_dir / "esclusi_per_motivo.csv"))
        exc_reg = sort_region_df(df_exc.groupby("regione").size().reset_index(name="totale"), "regione")
        written.append(safe_write_csv(exc_reg, output_dir / "esclusi_per_regione.csv"))

    report_txt = output_dir / "report_mappabili_esclusi.txt"
    write_txt_report(report_txt, df_all, df_map, reg, prov, com, df_exc)

    excel_path = output_dir / "report_mappabili_esclusi.xlsx"
    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        df_all.to_excel(writer, index=False, sheet_name="soggetti_geo_ruoli")
        df_map.to_excel(writer, index=False, sheet_name="mappabili")
        reg.to_excel(writer, index=False, sheet_name="per_regione")
        prov.head(100000).to_excel(writer, index=False, sheet_name="per_provincia")
        com.head(100000).to_excel(writer, index=False, sheet_name="per_comune")
        df_exc.head(100000).to_excel(writer, index=False, sheet_name="esclusi")

    print("✅ Completato")
    for p in written:
        print("   -", p)
    print("   -", report_txt)
    print("   -", excel_path)


if __name__ == "__main__":
    main()
