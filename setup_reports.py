import os
import json
from pathlib import Path

BASE_DIR = Path("output/reports")

folders = [
    "3.4.1_csv",
    "3.4.1_html",
    "3.4.1_png",
    "3.4.1_txt",
    "3.4.2_csv",
    "3.4.2_html",
    "3.4.2_txt",
    "4.1_mappe_csv",
    "4.1_mappe_html",
]

def create_folders():
    BASE_DIR.mkdir(parents=True, exist_ok=True)

    for folder in folders:
        path = BASE_DIR / folder
        path.mkdir(parents=True, exist_ok=True)

def generate_manifest():
    manifest = {}

    for folder in folders:
        path = BASE_DIR / folder

        files = sorted([
            f.name for f in path.iterdir()
            if f.is_file()
        ])

        manifest[folder] = files

    manifest_path = BASE_DIR / "manifest.json"

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    print("Creato:", manifest_path)

if __name__ == "__main__":
    create_folders()
    generate_manifest()