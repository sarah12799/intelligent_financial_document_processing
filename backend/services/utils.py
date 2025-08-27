# utils.py
import re
import json
from pathlib import Path
from pdf2image import convert_from_path
from PIL import Image

def clean_json_output(raw_text: str):
    cleaned = re.sub(r"^```json", "", raw_text)
    cleaned = re.sub(r"^```\s*", "", cleaned)
    cleaned = re.sub(r"\s*```$", "", cleaned)

    first_bracket = min(
        [pos for pos in [cleaned.find("["), cleaned.find("{")] if pos != -1] or [0]
    )
    cleaned = cleaned[first_bracket:]
    return cleaned.strip()

def save_json(data, path="outputs/results.json"):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def convert_pdf_to_images(pdf_path: Path, out_dir: Path, dpi: int = 200, img_format: str = "jpg") -> list[Path]:
    pages = convert_from_path(str(pdf_path), dpi=dpi)
    image_paths = []
    out_dir.mkdir(parents=True, exist_ok=True)
    pil_format = "JPEG" if img_format.lower() in ("jpg", "jpeg") else "PNG"

    for idx, page in enumerate(pages):
        img_name = f"{pdf_path.stem}_page-{idx+1:04d}.{img_format}"
        img_path = out_dir / img_name
        page.save(str(img_path), pil_format)
        image_paths.append(img_path)

        # Afficher la taille de l'image générée
        with Image.open(img_path) as im:
            print(f"[TAILLE] Image générée {img_name} : {im.size} (largeur x hauteur)")

        print(f"[INFO] {pdf_path.name} - Page {idx+1} convertie -> {img_path.name}")

    return image_paths