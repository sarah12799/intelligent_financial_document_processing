from langchain_text_splitters import RecursiveCharacterTextSplitter

from .pdf_service import normalize_table_rows

def create_chunks(tables: list[dict], chunk_size: int = 200, chunk_overlap: int = 50) -> list[str]:
    """
    Convert table rows into text chunks using a text splitter.
    Returns a list of text chunks.
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap
    )
    chunks = []
    for table in tables:
        normalized_rows = normalize_table_rows(table["rows"])  # Directly normalize rows here
        for row in normalized_rows:
            row_text = " | ".join(row)
            row_chunks = splitter.split_text(row_text)
            chunks.extend(row_chunks)
    return chunks