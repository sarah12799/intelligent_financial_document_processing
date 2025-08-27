import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from pathlib import Path
from services.utils import convert_pdf_to_images
from services.hash_service import sha256_bytes
from services.pdf_service import extract_pdf_words_boxes, get_tokens_ids
from services.llm_service import process_tokens
from services.db_service import get_extraction_by_id, insert_extraction, update_extraction_with_correction

app = Flask(__name__)
CORS(app, resources={r"/extract": {"origins": "http://127.0.0.1:8081"}, r"/correct": {"origins": "http://127.0.0.1:8081"}})  # Autoriser 127.0.0.1:8081

UPLOAD_DIR = "uploads"
DATA_DIR = "../frontend/data"
IMAGE_DIR = "../frontend/images_pdf"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

@app.route("/extract", methods=["POST"])
def extract():
    if "file" not in request.files:
        return jsonify({"error": "Aucun fichier fourni"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "Nom de fichier vide"}), 400

    # 1) Lire les bytes et calculer le hash → documentId
    file_bytes = file.read()
    document_id = sha256_bytes(file_bytes)
    print(f"Calculé documentId : {document_id}")  # Log pour traçabilité

    # 2) Sauvegarder le PDF localement pour debug/audit
    filepath = os.path.join(UPLOAD_DIR, f"{document_id}.pdf")
    with open(filepath, "wb") as f:
        f.write(file_bytes)
    print(f"Fichier sauvegardé : {filepath}")

    # 3) Extraction des tokens → dictionnaire id->texte (toujours généré)
    try:
        tokens_data = extract_pdf_words_boxes(filepath)
        tokens_dict = get_tokens_ids(tokens_data)
        print(f"Extraction des tokens réussie pour {document_id}")
        # Sauvegarde des tokens avec bboxes dans frontend/data
        pdf_filename = Path(file.filename).stem  # Nom du fichier sans extension
        tokens_json_path = Path(DATA_DIR) / f"{pdf_filename}.json"
        with open(tokens_json_path, "w", encoding="utf-8") as f:
            json.dump(tokens_data, f, indent=2, ensure_ascii=False)
        print(f"Tokens sauvegardés dans : {tokens_json_path}")
    except Exception as e:
        print(f"Erreur lors de l'extraction des tokens : {str(e)}")
        return jsonify({"error": "Erreur lors de l'extraction des tokens"}), 500

    # 4) Conversion du PDF en images (toujours générée)
    try:
        pdf_path = Path(filepath)
        image_paths = convert_pdf_to_images(pdf_path, Path(IMAGE_DIR))
        print(f"Conversion en images réussie, images générées : {len(image_paths)}")
    except Exception as e:
        print(f"Erreur lors de la conversion en images : {str(e)}")
        return jsonify({"error": "Erreur lors de la conversion en images"}), 500

    # 5) Vérifier si existe déjà en DB
    existing = get_extraction_by_id(document_id)
    if existing:
        print(f"Document {document_id} déjà existant, utilisation de finalData existant")
        results = existing.get("finalData", [])  # Utiliser finalData existant
    else:
        # 6) Passage LLM (seulement si nouveau)
        try:
            results = process_tokens(tokens_dict)
            print(f"Processing LLM réussi pour {document_id}")
        except Exception as e:
            print(f"Erreur lors du processing LLM : {str(e)}")
            return jsonify({"error": "Erreur lors du processing LLM"}), 500

        # 7) Insertion MongoDB (seulement si nouveau)
        try:
            inserted_doc = insert_extraction(
                document_id=document_id,
                file_name=file.filename,   # informatif
                raw_data=results,
                meta={"model": "gpt-4-0125-preview"}
            )
            print(f"Insertion MongoDB réussie pour {document_id}")
        except Exception as e:
            print(f"Erreur lors de l'insertion MongoDB : {str(e)}")
            return jsonify({"error": "Erreur lors de l'insertion dans la base de données"}), 500

    # 8) Préparer la réponse avec les chemins relatifs des images et documentId
    base_path = Path("../frontend")
    response_data = {
        "data": results,
        "images": [str(img_path.relative_to(base_path)) for img_path in image_paths],
        "documentId": document_id  # Toujours inclure l'ID
    }

    return jsonify(response_data)

@app.route("/correct", methods=["PATCH"])
def correct():
    data = request.get_json()
    document_id = data.get("documentId")
    new_final_data = data.get("finalData")

    if not document_id or not new_final_data:
        return jsonify({"error": "documentId et finalData sont requis"}), 400

    try:
        updated_doc = update_extraction_with_correction(document_id, new_final_data)
        if not updated_doc:
            print(f"Document {document_id} non trouvé")
            return jsonify({"error": "Document introuvable"}), 404
        print(f"Correction appliquée avec succès pour {document_id}")
    except Exception as e:
        print(f"Erreur lors de la mise à jour : {str(e)}")
        return jsonify({"error": "Erreur lors de la mise à jour"}), 500

    return jsonify({
        "documentId": document_id,
        "finalData": updated_doc["finalData"],
        "raw": updated_doc["raw"],
        "source": "corrected",
        "corrections": updated_doc.get("corrections", [])
    })

if __name__ == "__main__":
    app.run(debug=True, port=5001)