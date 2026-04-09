#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations

import json
import re
from pathlib import Path


# =========================================================
# CONFIG FISSA
# =========================================================
INPUT_DIR = Path("output") / "json" / "step_2"
OUTPUT_JSON = Path("output") / "json" / "merged" / "all_risultati_enriched_2.4.json"


JSON_PATTERN = re.compile(r"^\d{2}_risultati_enriched_2\.4\.json$")


def find_all_enriched_24_json(input_dir: str | Path) -> list[Path]:
    input_dir = Path(input_dir)

    if not input_dir.exists():
        raise FileNotFoundError(f"Cartella input non trovata: {input_dir}")

    files = sorted(
        p for p in input_dir.iterdir()
        if p.is_file() and JSON_PATTERN.match(p.name)
    )

    if not files:
        raise FileNotFoundError(
            f"Nessun file ??_risultati_enriched_2.4.json trovato in: {input_dir}"
        )

    return files


def load_json_list(path: Path) -> list:
    with path.open("r", encoding="utf-8") as f:
        obj = json.load(f)

    if not isinstance(obj, list):
        raise ValueError(f"Il file JSON non contiene una lista: {path}")

    return obj


def merge_json_files(json_paths: list[Path]) -> list:
    merged = []

    for path in json_paths:
        data = load_json_list(path)
        print(f"📄 {path.name}: {len(data)} record")
        merged.extend(data)

    return merged


def main():
    input_dir = Path(INPUT_DIR)
    output_json = Path(OUTPUT_JSON)

    print("📂 INPUT_DIR :", input_dir)
    print("💾 OUTPUT_JSON:", output_json)

    json_paths = find_all_enriched_24_json(input_dir)

    print("\n🔎 File trovati:")
    for p in json_paths:
        print(" -", p.name)

    merged = merge_json_files(json_paths)

    output_json.parent.mkdir(parents=True, exist_ok=True)

    with output_json.open("w", encoding="utf-8") as f:
        json.dump(merged, f, ensure_ascii=False, indent=2)

    print("\n✅ Merge completato")
    print(f"📦 File sorgente: {len(json_paths)}")
    print(f"📚 Record totali: {len(merged)}")
    print(f"💾 Output: {output_json.resolve()}")


if __name__ == "__main__":
    main()