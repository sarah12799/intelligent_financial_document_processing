import numpy as np
from pymongo import MongoClient
from dotenv import load_dotenv
import os
from services.db_service import get_extraction_by_id

# Load environment variables
load_dotenv()
MONGODB_URI = os.getenv("MONGODB_URI")
MONGODB_DB = os.getenv("MONGODB_DB", "pdf_extraction")

# Initialize MongoDB client
client = MongoClient(MONGODB_URI)
db = client[MONGODB_DB]
embeddings_collection = db.embeddings

def cosine_similarity(vec1: list[float], vec2: list[float]) -> float:
    """
    Calculate the cosine similarity between two vectors.
    Returns a value between -1 and 1, where 1 means identical.
    """
    vec1 = np.array(vec1, dtype=np.float32)
    vec2 = np.array(vec2, dtype=np.float32)
    dot_product = np.dot(vec1, vec2)
    norm_vec1 = np.linalg.norm(vec1)
    norm_vec2 = np.linalg.norm(vec2)
    if norm_vec1 == 0 or norm_vec2 == 0:
        return 0.0
    return dot_product / (norm_vec1 * norm_vec2)

def get_most_similar_document_ids(query_embeddings: list[list[float]], exclude_doc_id: str | None = None, top_k: int = 3) -> list[str]:
    """
    Retrieve the top-k most similar document IDs from the embeddings collection
    by comparing the query embeddings, excluding the specified document if provided.
    """
    # Fetch all embeddings from the collection
    all_docs = list(embeddings_collection.find({}, {"document_id": 1, "embedding": 1, "_id": 0}))

    # Find top-k most similar documents
    doc_scores = {}  # Map document_id to max similarity score
    for query_emb in query_embeddings:
        for doc in all_docs:
            doc_id = doc["document_id"]
            if exclude_doc_id and doc_id == exclude_doc_id:
                continue
            embedding = doc.get("embedding")
            if embedding:
                score = cosine_similarity(query_emb, embedding)
                doc_scores[doc_id] = max(doc_scores.get(doc_id, -1), score)

    # Sort documents by max score and get top_k IDs
    top_docs = sorted(doc_scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
    top_doc_ids = [doc_id for doc_id, _ in top_docs]

    return top_doc_ids

def get_similar_examples(doc_ids: list[str], top_k_per_doc: int = 3) -> list[dict]:
    """
    Retrieve the first top_k_per_doc examples from finalData for each similar document ID.
    """
    examples = []
    for doc_id in doc_ids:
        extraction = get_extraction_by_id(doc_id)
        final_data = extraction.get("finalData", []) if extraction else []
        # Take the first top_k_per_doc objects
        selected_examples = final_data[:top_k_per_doc]
        examples.extend(selected_examples)
        print(f"Retrieved {len(selected_examples)} examples from doc_id {doc_id}")
    return examples