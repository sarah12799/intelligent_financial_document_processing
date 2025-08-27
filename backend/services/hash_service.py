import hashlib

def sha256_bytes(data: bytes) -> str:
    """Retourne le SHA-256 hex d'un buffer bytes."""
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()

def sha256_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    """Alternative: calcule le hash d'un fichier sans tout charger en mémoire."""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            h.update(chunk)
    return h.hexdigest()
