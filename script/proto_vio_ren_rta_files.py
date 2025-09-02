import os
import re

def rename_files_with_code(folder_path):
    if not os.path.isdir(folder_path):
        print(f"❌ Errore: la cartella '{folder_path}' non esiste.")
        return

    for filename in os.listdir(folder_path):
        old_path = os.path.join(folder_path, filename)

        # Salta le directory
        if os.path.isdir(old_path):
            continue

        # Cerca la sequenza "_rta_<codice>_"
        match = re.search(r"_rta_(\d{2})_", filename.lower())
        if match:
            code = match.group(1)  # Es. '01'
            new_filename = f"{code}_{filename}"
            new_path = os.path.join(folder_path, new_filename)
            os.rename(old_path, new_path)
            print(f"✅ Renamed: {filename} → {new_filename}")
        else:
            print(f"⚠️ Nessun codice trovato in: {filename}")

if __name__ == "__main__":
    folder = input("📂 Inserisci il percorso della cartella: ").strip()
    rename_files_with_code(folder)