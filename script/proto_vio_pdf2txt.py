import os
import pytesseract
from pdf2image import convert_from_path

def process_pdfs_in_folder(pdf_folder, txt_folder, tesseract_cmd):
    # esegue Tesseract
    pytesseract.pytesseract.tesseract_cmd = tesseract_cmd    
    # Scansiona i file nella cartella
    for filename in os.listdir(pdf_folder):
        if filename.lower().endswith(".pdf"):
            pdf_path_filename = os.path.join(pdf_folder, filename)
            print(f"esecuzione: {pdf_path_filename}")            
            # Converti il PDF in immagini
            images = convert_from_path(pdf_path_filename)            
            # Estrai il testo da ogni immagine
            extracted_text = ""
            for i, image in enumerate(images):
                text = pytesseract.image_to_string(image)
                extracted_text += text + "\n"
                print(f"pagina {i+1} ...")            
            # Salva il testo estratto in un file di output
            txt_filename = os.path.splitext(filename)[0] + ".txt"
            output_text_path = os.path.join(txt_folder, txt_filename)
            with open(output_text_path, "w", encoding="utf-8") as text_file:
                text_file.write(extracted_text)
            print(f"Salva il testo estratto nel file: {output_text_path}\n")
# Esempio di utilizzo
pdf_folder = "./pdf"  # 
txt_folder = "./txt"  # 
tesseract_cmd='C:/Program Files/Tesseract-OCR/tesseract.exe'
process_pdfs_in_folder(pdf_folder, txt_folder, tesseract_cmd)