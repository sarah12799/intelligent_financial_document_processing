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



