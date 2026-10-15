import chromadb
from typing import List
from config import config
from ddtrace.llmobs.decorators import retrieval
from ddtrace.llmobs import LLMObs

# Configuration
chromadb_client = chromadb.PersistentClient(path=config.CHROMA_DATA_DIR)


def get_collection(collection_name: str):
    """
    Returns the collection with the given name.
    If it doesn't exist, creates it.
    """
    return chromadb_client.get_or_create_collection(collection_name)


def delete_collection(collection_name: str):
    """
    Deletes the collection
    """
    chromadb_client.delete_collection(collection_name)


def get_all_collections():
    """
    Returns a list of all collections in the vector store
    """
    return chromadb_client.list_collections()


@retrieval
def find_similar_documents(
    embeddings: List[float], n_results: int = 3, topic: str = None
) -> List[str]:
    """
    Retrieves similar documents based on embeddings.
    If topic is provided, searches in that topic's collection.
    """
    if not topic:
        raise ValueError("Topic is required for searching documents")

    collection = get_collection(topic)

    # Ensure we request at least 1 result, but no more than available
    n_results = max(1, min(n_results, collection.count()))

    results = collection.query(
        query_embeddings=[embeddings],
        n_results=n_results,
        include=["documents"],
    )

    LLMObs.annotate(
        output_data=results.get("documents", [[]])[0]
    )

    # Extract first document list from results if available
    # documents = results.get("document", [[]])  # <-- this is a bug!
    documents = results.get("documents", [[]])
    return documents[0] if documents else []
