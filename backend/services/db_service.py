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

# Index unique sur documentId (hash)
extractions.create_index([("documentId", ASCENDING)], unique=True)

def get_extraction_by_id(document_id: str):
    """Récupère tout le document (sans _id) par documentId."""
    return extractions.find_one({"documentId": document_id}, {"_id": 0})

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