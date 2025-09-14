import re
import pdfplumber
import json
import os

def extract_pdf_words_boxes(pdf_path, max_gap=10):
    data = []
    uid_counter = 1  # Compteur global pour attribuer un id unique

    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            words = page.extract_words()
            merged = []
            i = 0
            while i < len(words):
                word = words[i]
                text = word["text"]

                # Cas 1: Token faisant partie d'un nombre avec plusieurs groupes de chiffres
                if re.match(r"^-?\d{1,3}$", text):  # Début potentiel d'un nombre (ex. "1", "14", "444")
                    number_parts = [text]
                    start_word = word
                    j = i + 1
                    # Continuer à collecter les tokens qui forment un nombre
                    while j < len(words):
                        next_word = words[j]
                        next_text = next_word["text"]
                        close_enough = int(next_word["x0"]) - int(word["x1"]) < max_gap
                        same_line = abs(int(next_word["top"]) - int(word["top"])) < 3

                        if not (close_enough and same_line):
                            break

                        # Ajouter les groupes de 3 chiffres ou la partie décimale
                        if re.match(r"^\d{3}$", next_text) or re.match(r"^\d{1,3}[,.]\d{1,2}-?$", next_text):
                            number_parts.append(next_text)
                            word = next_word  # Mettre à jour le dernier mot utilisé
                            j += 1
                        else:
                            break

                    # Vérifier si les parties collectées forment un nombre valide
                    full_number = " ".join(number_parts)
                    if re.match(r"^-?\d{1,3}( \d{3})*[,.]\d{1,2}-?$", full_number):
                        merged.append({
                            "id": uid_counter,
                            "text": full_number,
                            "x0": int(start_word["x0"]),
                            "y0": int(start_word["top"]),
                            "x1": int(word["x1"]),
                            "y1": int(word["bottom"]),
                            "page": page_num
                        })
                        uid_counter += 1
                        i = j  # Sauter tous les tokens utilisés
                        continue

                # Cas 2: Token déjà complet (ex. "123,45" ou "123 456,78")
                if re.match(r"^-?\d{1,3}( \d{3})*[,.]\d{1,2}-?$", text):
                    merged.append({
                        "id": uid_counter,
                        "text": text,
                        "x0": int(word["x0"]),
                        "y0": int(word["top"]),
                        "x1": int(word["x1"]),
                        "y1": int(word["bottom"]),
                        "page": page_num
                    })
                    uid_counter += 1
                    i += 1
                    continue

                # Mot normal
                merged.append({
                    "id": uid_counter,
                    "text": text,
                    "x0": int(word["x0"]),
                    "y0": int(word["top"]),
                    "x1": int(word["x1"]),
                    "y1": int(word["bottom"]),
                    "page": page_num
                })
                uid_counter += 1
                i += 1

            data.extend(merged)

    return data


def get_tokens_ids(data, tokens_json="tokens.json"):
    tokens_dict = {}
    for item in data:
        token_id = item["id"]
        tokens_dict[token_id] = item["text"]

    # Sauvegarde dans un JSON (si tu veux le garder)
    with open(tokens_json, "w", encoding="utf-8") as f:
        json.dump(tokens_dict, f, indent=2, ensure_ascii=False)

    return tokens_dict

###fonctions pour le RAG

def extract_pdf_tables(pdf_path: str) -> list[dict]:
    """
    Extract tables from a PDF file.
    Returns a list of dictionaries, each containing page number, table index, and rows.
    """
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF file '{pdf_path}' not found.")
    
    all_tables = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_num, page in enumerate(pdf.pages):
            tables = page.extract_tables()
            for table_index, table in enumerate(tables):
                cleaned_table = []
                for row in table:
                    cleaned_row = [cell.strip() if cell else "" for cell in row]
                    cleaned_table.append(cleaned_row)
                all_tables.append({
                    "page": page_num,
                    "table_index": table_index,
                    "rows": cleaned_table
                })
    return all_tables

def normalize_table_rows(rows: list[list[str]]) -> list[list[str]]:
    """
    Normalize table rows where cells may contain multiple lines (\\n).
    Returns a list of normalized rows, each representing a logical row.
    """
    normalized_rows = []
    for row in rows:
        split_cells = [cell.split("\n") for cell in row]
        max_lines = max(len(cell) for cell in split_cells)
        for i in range(max_lines):
            new_row = [cell[i] if i < len(cell) else "" for cell in split_cells]
            normalized_rows.append(new_row)
    return normalized_rows
