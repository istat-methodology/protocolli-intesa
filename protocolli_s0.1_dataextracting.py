# Installare:
# Tesseract
# OpenCV
# python -m pip install ot
# py -m pip install opencv-contrib-python

import os
import cv2
import numpy as np
import pytesseract
from pdf2image import convert_from_path
import json

PDF_FOLDER = f"data/pdf/"
TXT_FOLDER = f"data/txt/"


def process_pdfs_in_folder(
    pdf_folder,
    txt_folder,
    tesseract_cmd,
    poppler_path,
    skip_existing=True,
    save_json=False
):

    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd

    os.makedirs(txt_folder, exist_ok=True)

    for filename in os.listdir(pdf_folder):

        if not filename.lower().endswith(".pdf"):
            continue

        pdf_path = os.path.join(pdf_folder, filename)
        txt_filename = os.path.splitext(filename)[0] + ".txt"
        txt_path = os.path.join(txt_folder, txt_filename)

        # SKIP opzionale
        if skip_existing and os.path.exists(txt_path):
            print(f"⏭️ skip: {filename}")
            continue

        print(f"\n📄 elaboro: {filename}")

        try:

            images = convert_from_path(
                pdf_path,
                dpi=300,
                poppler_path=poppler_path
            )

            extracted_text = ""
            pages = []

            for i, image in enumerate(images):

                print(f"pagina {i+1}")

                img = cv2.cvtColor(np.array(image), cv2.COLOR_BGR2GRAY)
                img = cv2.threshold(
                    img, 0, 255,
                    cv2.THRESH_BINARY + cv2.THRESH_OTSU
                )[1]

                text = pytesseract.image_to_string(
                    img,
                    lang="ita",
                    config="--psm 6"
                )

                extracted_text += text + "\n"

                if save_json:
                    pages.append({
                        "page": i + 1,
                        "text": text
                    })

            # salva TXT
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write(extracted_text)

            print(f"✅ salvato TXT: {txt_path}")

            # salva JSON opzionale
            if save_json:

                json_filename = os.path.splitext(filename)[0] + ".json"
                json_path = os.path.join(txt_folder, json_filename)

                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump({
                        "file": filename,
                        "pages": pages
                    }, f, indent=2, ensure_ascii=False)

                print(f"✅ salvato JSON: {json_path}")

        except Exception as e:

            print(f"❌ errore su {filename}")
            print(e)


if __name__ == "__main__":
    tesseract_cmd = 'C:/Program Files/Tesseract-OCR/tesseract.exe'
    poppler_path = None  # es. 'C:/poppler/bin'
    process_pdfs_in_folder(PDF_FOLDER, TXT_FOLDER, tesseract_cmd, poppler_path)
