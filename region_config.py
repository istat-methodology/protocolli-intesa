# region_config.py
import argparse
import os

VALID_REGION_CODES = {f"{i:02d}" for i in range(1, 22)}

def get_reg_code(default="09", required=False):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--reg_code", type=str, default=None)
    args, _ = parser.parse_known_args()

    reg_code = args.reg_code or os.environ.get("REG_CODE") or default
    reg_code = str(reg_code).zfill(2)

    if required and reg_code not in VALID_REGION_CODES:
        raise ValueError(f"Codice regione non valido: {reg_code}")

    return reg_code

def print_reg_code(reg_code):
    print(f"📍 REG_CODE ATTIVO: {reg_code}")

def build_region_file(base_dir, reg_code, suffix):
    return os.path.join(base_dir, f"{reg_code}_{suffix}")
    