# app.py
import json
from flask import Flask, request, jsonify
from flask_cors import CORS
import os
from pathlib import Path
from services.utils import convert_pdf_to_images
from services.hash_service import sha256_bytes
from services.pdf_service import extract_pdf_words_boxes, get_tokens_ids, extract_pdf_tables
from services.llm_service import process_tokens
from services.db_service import get_extraction_by_id, update_extraction_with_correction, insert_placeholder, complete_extraction, store_embeddings
from services.chunking_service import create_chunks
from services.embedding_service import generate_embeddings
from services.similarity_service import get_most_similar_document_ids, get_similar_examples
from dotenv import load_dotenv

# Load environment variables
load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")

app = Flask(__name__)
CORS(app, resources={r"/extract": {"origins": "http://127.0.0.1:8081"}, r"/correct": {"origins": "http://127.0.0.1:8081"}})

UPLOAD_DIR = "uploads"
DATA_DIR = "../frontend/data"
IMAGE_DIR = "../frontend/images_pdf"
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(IMAGE_DIR, exist_ok=True)

def get_similar_documents_examples(document_id: str, embedding_vectors: list[list[float]], top_k_docs: int = 3, top_k_per_doc: int = 3):
    """
    Récupère des exemples d'extraction depuis les documents similaires.
    Retourne une liste d'exemples pour alimenter le prompt LLM.
    """
    try:
        # Vérifier que document_id est défini
        if not document_id:
            raise ValueError("document_id is not provided or empty")
        
        # Obtenir les IDs des documents similaires
        similar_doc_ids = get_most_similar_document_ids(embedding_vectors, exclude_doc_id=document_id, top_k=top_k_docs)
        print(f"Documents similaires trouvés : {similar_doc_ids}")
        
        examples = get_similar_examples(similar_doc_ids, top_k_per_doc=top_k_per_doc)
        
        print(f"Exemples récupérés : {len(examples)} lignes")
        return examples[:6]  # Maximum 6 exemples au total pour limiter les tokens
        
    except Exception as e:
        print(f"Erreur lors de la récupération des exemples similaires : {str(e)}")
        return []

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
    print(f"Calculé documentId : {document_id}")

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
        pdf_filename = Path(file.filename).stem
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
        results = existing.get("finalData", [])
    else:
        # **NOUVEAU : Document inexistant - Workflow avec RAG**
        print(f"Nouveau document {document_id}, lancement du workflow RAG")
        
        # 6) Insérer un placeholder pour réserver l'ID
        try:
            insert_placeholder(document_id, file.filename)
            print(f"Placeholder inséré pour {document_id}")
        except Exception as e:
            print(f"Erreur lors de l'insertion du placeholder : {str(e)}")
            return jsonify({"error": "Erreur lors de l'insertion du placeholder"}), 500

        # 7) Générer et stocker les embeddings
        try:
            tables = extract_pdf_tables(filepath)
            chunks = create_chunks(tables)
            embedding_vectors = generate_embeddings(chunks, api_key=api_key)
            store_embeddings(document_id, chunks, embedding_vectors)
            print(f"Embeddings générés et stockés pour {document_id}")
        except Exception as e:
            print(f"Erreur lors du stockage des embeddings : {str(e)}")
            # Continue même si les embeddings échouent

        # 8) Récupérer des exemples depuis les documents similaires
        examples = get_similar_documents_examples(document_id, embedding_vectors)
        
        # 9) Passage LLM avec exemples (si disponibles)
        try:
            if examples:
                print(f"Utilisation de {len(examples)} exemples pour guider l'extraction")
                results = process_tokens(tokens_dict, examples=examples)
            else:
                print("Aucun exemple disponible, extraction sans guide")
                results = process_tokens(tokens_dict)
            print(f"Processing LLM réussi pour {document_id}")
        except Exception as e:
            print(f"Erreur lors du processing LLM : {str(e)}")
            return jsonify({"error": "Erreur lors du processing LLM"}), 500

        # 10) Mise à jour avec les résultats finaux
        try:
            # Convert tokens_dict to a list of [id, text] pairs to ensure string keys
            raw_data = [{"id": str(k), "text": v} for k, v in tokens_dict.items()]
            updated_doc = complete_extraction(document_id, raw_data, results)
            print(f"Mise à jour avec extraction finale réussie pour {document_id}")
        except Exception as e:
            print(f"Erreur lors de la mise à jour finale : {str(e)}")
            return jsonify({"error": "Erreur lors de la mise à jour finale"}), 500

    # 11) Préparer la réponse avec les chemins relatifs des images et documentId
    base_path = Path("../frontend")
    response_data = {
        "data": results,
        "images": [str(img_path.relative_to(base_path)) for img_path in image_paths],
        "documentId": document_id
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