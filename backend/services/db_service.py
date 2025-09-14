import os
from datetime import datetime
from pymongo import MongoClient, ASCENDING
from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "pdf_extraction")

if not MONGODB_URI:
    raise ValueError("⚠️ MONGODB_URI manquant dans .env")

client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]
extractions = db.files
embeddings = db.embeddings  # Collection pour les embeddings

# Index unique sur documentId (hash) pour extractions
extractions.create_index([("documentId", ASCENDING)], unique=True)

# Index sur document_id et chunk_id pour embeddings (pour éviter les doublons)
embeddings.create_index([("document_id", ASCENDING), ("chunk_id", ASCENDING)], unique=True)

def get_extractions_by_ids(document_ids: list[str]) -> list[dict]:
    """
    Récupère plusieurs extractions par leurs IDs.
    Utilisé par l'API pour récupérer les documents similaires.
    """
    return list(extractions.find(
        {"documentId": {"$in": document_ids}}, 
        {"_id": 0}
    ))

def get_extraction_by_id(document_id: str):
    """Récupère tout le document (sans _id) par documentId."""
    return extractions.find_one({"documentId": document_id}, {"_id": 0})

def insert_placeholder(document_id: str, file_name: str | None = None):
    """
    Insert initial placeholder: only documentId and optional fileName, null/empty for others.
    Retourne le doc inséré (sans _id).
    """
    now = datetime.utcnow()
    doc = {
        "documentId": document_id,
        "fileName": file_name,
        "createdAt": now,
        "updatedAt": now,
        "raw": None,
        "finalData": None,
        "meta": {},
        "corrections": []
    }
    extractions.insert_one(doc)
    return get_extraction_by_id(document_id)

def complete_extraction(document_id: str, raw_data, final_data, meta: dict | None = None):
    """
    Complete the extraction after RAG and LLM processing: set raw, finalData, meta.
    Retourne le document mis à jour (sans _id).
    """
    extractions.update_one(
        {"documentId": document_id},
        {
            "$set": {
                "raw": raw_data,
                "finalData": final_data,
                "meta": meta or {},
                "updatedAt": datetime.utcnow()
            }
        }
    )
    return get_extraction_by_id(document_id)

def insert_extraction(document_id: str, file_name: str, raw_data, meta: dict | None = None):
    """
    Insert initiale: raw + finalData = raw.
    Retourne le doc inséré (sans _id).
    """
    now = datetime.utcnow()
    doc = {
        "documentId": document_id,
        "fileName": file_name,
        "createdAt": now,
        "updatedAt": now,
        "raw": raw_data,
        "finalData": raw_data,     # au début, finalData = raw
        "meta": meta or {},
        "corrections": []          # initialisation vide
    }
    extractions.insert_one(doc)
    return get_extraction_by_id(document_id)

def update_extraction_with_correction(document_id: str, new_final_data):
    """
    Ajoute une correction avec timestamp et met à jour finalData.
    Retourne le document mis à jour (sans _id).
    """
    doc = get_extraction_by_id(document_id)
    if not doc:
        return None

    # Ajouter l'ancienne version de finalData dans corrections
    correction_entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "finalData": doc.get("finalData", [])
    }

    corrections = doc.get("corrections", [])
    corrections.append(correction_entry)

    # Mise à jour de finalData et corrections
    extractions.update_one(
        {"documentId": document_id},
        {
            "$set": {
                "finalData": new_final_data,
                "corrections": corrections,
                "updatedAt": datetime.utcnow()
            }
        }
    )

    # Retourner le document mis à jour
    return get_extraction_by_id(document_id)

def store_embeddings(document_id: str, chunks: list[str], embedding_vectors: list[list[float]]):
    """
    Store embeddings in the embeddings collection.
    Each embedding document contains document_id, chunk_id, text, and embedding.
    """
    for chunk_id, (text, embedding) in enumerate(zip(chunks, embedding_vectors), 1):
        embedding_doc = {
            "document_id": document_id,
            "chunk_id": chunk_id,
            "text": text,
            "embedding": embedding
        }
        try:
            embeddings.insert_one(embedding_doc)
        except Exception as e:
            # Gérer les doublons potentiels (si l'index unique est violé)
            if "duplicate key error" in str(e).lower():
                print(f"Embedding for document_id={document_id}, chunk_id={chunk_id} already exists. Skipping.")
            else:
                raise Exception(f"Failed to store embedding: {str(e)}")