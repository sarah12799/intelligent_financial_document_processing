from langchain_openai import OpenAIEmbeddings

def generate_embeddings(chunks: list[str], model: str = "text-embedding-3-small", api_key: str = None) -> list[list[float]]:
    """
    Generate embeddings for a list of text chunks using OpenAI's embedding model.
    Returns a list of embedding vectors.
    """
    try:
        embeddings_model = OpenAIEmbeddings(model=model, openai_api_key=api_key)
        return embeddings_model.embed_documents(chunks)
    except Exception as e:
        raise Exception(f"Failed to generate embeddings: {str(e)}")