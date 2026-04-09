import subprocess
import os
import sys
import argparse

SCRIPTS = [
    "protocolli_s2.1_enrich_runts_cav.py",
    "protocolli_s2.2_enrich_sovracomunali_province_regioni.py",
    "protocolli_s2.3_enrich_comuni_province_regioni.py",
    "protocolli_s2.4_enrich_ruoli.py",
]

ALL_REGIONI = [f"{i:02d}" for i in range(1, 22)]


def normalize_reg_code(value: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError("Codice regione vuoto")
    value = value.zfill(2)
    if value not in ALL_REGIONI:
        raise ValueError(f"Codice regione non valido: {value}")
    return value


def parse_regioni(spec: str | None) -> list[str]:
    """
    Supporta:
    - 09
    - 01-05
    - 01,07,09
    - all
    - 01-03,07,09
    """
    if spec is None or not str(spec).strip():
        return ["09"]

    spec = str(spec).strip().lower()

    if spec == "all":
        return ALL_REGIONI.copy()

    result = []

    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue

        if "-" in part:
            start_s, end_s = part.split("-", 1)
            start = int(normalize_reg_code(start_s))
            end = int(normalize_reg_code(end_s))

            if start > end:
                raise ValueError(f"Range non valido: {part}")

            for n in range(start, end + 1):
                result.append(f"{n:02d}")
        else:
            result.append(normalize_reg_code(part))

    # deduplica mantenendo l'ordine
    seen = set()
    ordered = []
    for r in result:
        if r not in seen:
            seen.add(r)
            ordered.append(r)

    return ordered


def run_script(script_path, reg_code):
    cmd = [sys.executable, script_path, "--reg_code", reg_code]
    print("\n" + "=" * 80)
    print(f"🚀 Eseguo: {script_path} | REGIONE {reg_code}")
    print("=" * 80)

    result = subprocess.run(cmd)

    if result.returncode != 0:
        print(f"❌ Errore in {script_path} per regione {reg_code}")
        return False

    print(f"✅ Completato: {script_path} | REGIONE {reg_code}")
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--regioni",
        type=str,
        default="09",
        help="Specifica regioni: 09 oppure 01-05 oppure 01,07,09 oppure all"
    )
    args = parser.parse_args()

    try:
        regioni = parse_regioni(args.regioni)
    except ValueError as e:
        print(f"❌ {e}")
        sys.exit(1)

    print("🌍 Regioni selezionate:", ", ".join(regioni))

    for reg_code in regioni:
        print("\n" + "#" * 100)
        print(f"🌍 AVVIO PIPELINE REGIONE {reg_code}")
        print("#" * 100)

        for script in SCRIPTS:
            if not os.path.exists(script):
                print(f"⚠️ Script non trovato: {script}")
                continue

            ok = run_script(script, reg_code)
            if not ok:
                print(f"⛔ Pipeline interrotta per REGIONE {reg_code}")
                break

        print(f"\n🏁 Fine pipeline REGIONE {reg_code}")


if __name__ == "__main__":
    main()