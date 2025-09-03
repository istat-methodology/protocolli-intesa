import os

def rename_files_with_code(folder_path, code):
    # Ensure the folder path exists
    if not os.path.isdir(folder_path):
        print(f"Error: Folder '{folder_path}' does not exist.")
        return

    for filename in os.listdir(folder_path):
        old_path = os.path.join(folder_path, filename)

        # Skip directories
        if os.path.isdir(old_path):
            continue

        new_filename = f"{code}_{filename}"
        new_path = os.path.join(folder_path, new_filename)

        os.rename(old_path, new_path)
        print(f"Renamed: {filename} → {new_filename}")

if __name__ == "__main__":
    folder = input("Enter the folder path: ").strip()
    code = input("Enter the code to prefix: ").strip()
    rename_files_with_code(folder, code)
