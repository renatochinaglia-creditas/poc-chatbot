#!/usr/bin/env python3
import os
from typing import Dict, List, Tuple
from utils import (
    load_data_for_kb,
    create_embeddings,
    add_document,
    clear_collections,
)
from ddtrace.llmobs import LLMObs
from ddtrace.llmobs.decorators import workflow, tool, embedding

# Initialize LLMObs
LLMObs.enable(
    ml_app=os.getenv("DD_LLMOBS_ML_APP"),
    api_key=os.getenv("DD_API_KEY"),
    site=os.getenv("DD_SITE"),
    agentless_enabled=os.getenv("DD_LLMOBS_AGENTLESS_ENABLED"), #optional
)


@embedding
def create_document_embeddings(
    document: str, topic: str
) -> Tuple[List[float], Dict[str, str]]:
    """
    Creates embeddings for a single document and returns them along with metadata.
    """
    try:
        embeddings = create_embeddings(document, "search_document")
        return embeddings, {"status": "success"}
    except Exception as e:
        return [], {"status": "error", "error": str(e)}


@tool
def store_document(
    document: str, embeddings: List[float], topic: str
) -> Dict[str, str]:
    """
    Stores a single document and its embeddings in the vector store.
    """
    try:
        add_document(document, embeddings, topic)
        return {"message": "Document stored successfully"}
    except Exception as e:
        return {"message": f"Error storing document: {e}"}


@workflow
def process_document(document: str, topic: str) -> Dict[str, str]:
    """
    Process a single document by creating embeddings and storing it.
    """
    # Create embeddings
    embeddings, embed_metadata = create_document_embeddings(document, topic)
    if embed_metadata["status"] == "error":
        raise Exception(f"Error creating embeddings: {embed_metadata['error']}")

    # Store document
    store_result = store_document(document, embeddings, topic)
    if "error" in store_result["message"].lower():
        raise Exception(store_result["message"])

    return store_result


def ingest_documents() -> None:
    """
    Processes documents from the knowledge base directory.
    Clears all existing collections before adding new documents.
    """
    # Step 1: Clear existing collections
    clear_collections()

    # Step 2: Load documents from the knowledge base directory
    documents = load_data_for_kb()

    # Step 3: Process each document
    print("\nProcessing documents...")
    for topic, document in documents:
        process_document(document, topic)


if __name__ == "__main__":
    print("Starting document ingestion process...")
    ingest_documents()
    print("Document ingestion complete!")
