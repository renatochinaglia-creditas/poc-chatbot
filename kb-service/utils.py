import os
import json
import uuid
import chromadb
from typing import List, Tuple
from nltk.tokenize import sent_tokenize
from openai import OpenAI

CHROMA_HOST = os.getenv("CHROMADB_HOST", "vector-store")
CHROMA_PORT = os.getenv("CHROMADB_PORT", "8000")
CHROMA_DATA_DIR: str = os.getenv("CHROMA_DATA_DIR", "/chroma/data")
KB_DATA_DIR = os.getenv("KB_DATA_DIR", "./kb_data")
EMBED_BASE_URL = os.getenv("EMBED_BASE_URL", "http://text-embedder")
EMBED_PORT = os.getenv("EMBED_PORT", "11434")
EMBED_MODEL = os.getenv("EMBED_MODEL", "nomic-embed-text:v1.5")
CHUNKING_STRATEGY = os.getenv("CHUNKING_STRATEGY", "fixed")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")


chromadb_client = chromadb.PersistentClient(path=CHROMA_DATA_DIR)
openai_client_embedding = OpenAI(
    base_url=f"{EMBED_BASE_URL}:{EMBED_PORT}/v1",
    api_key=OPENAI_API_KEY,
)


# Document Processing Functions
def get_topic_from_filename(filename: str) -> str:
    """
    Extracts a topic name from a filename.
    For example: 'ancient-egypt.json' -> 'ancient-egypt'
    """
    # Remove file extension and any path components
    base_name = os.path.splitext(os.path.basename(filename))[0]
    # Convert to lowercase and replace spaces/hyphens with underscores
    return base_name.lower().replace(" ", "_").replace("-", "_")


def fixed_size_chunk_data(text, chunk_size=500):
    """
    Fixed-size chunking: Splits text into chunks of specified size,
    ignoring document structure.
    """
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


def sentence_chunk_text(text, max_chunk_size=500, overlap=100):
    """
    Structure-aware chunking that respects sentence boundaries
    while maintaining overlap.
    """
    sentences = sent_tokenize(text)  # Tokenize into sentences
    chunks, current_chunk = [], []

    for sentence in sentences:
        if sum(len(s) for s in current_chunk) + len(sentence) > max_chunk_size:
            chunks.append(" ".join(current_chunk))  # Append current chunk
            current_chunk = current_chunk[-overlap:]  # Keep overlap sentences

        current_chunk.append(sentence)

    if current_chunk:
        chunks.append(" ".join(current_chunk))

    return chunks


def process_json_file(file_path: str) -> List[Tuple[str, str]]:
    """
    Process a JSON file and return chunked text data with topic.
    Expects JSON files to contain a list of dictionaries.
    Returns list of (topic, text) tuples.
    """
    data: List[Tuple[str, str]] = []
    try:
        with open(file_path, "r") as file:
            json_data = json.load(file)

            if not isinstance(json_data, list):
                print(f"Skipping {file_path}: Expected a list, got {type(json_data)}")
                return data

            # Get topic from filename
            topic = get_topic_from_filename(file_path)

            for item in json_data:
                if isinstance(item, dict):
                    if CHUNKING_STRATEGY == "fixed":
                        # Size-based chunking: convert dict to string and split
                        chunked_text = fixed_size_chunk_data(json.dumps(item))
                    else:
                        # Structure-aware chunking: preserve structure
                        chunked_text = [json.dumps(item)]
                    # Add topic to each chunk
                    data.extend([(topic, chunk) for chunk in chunked_text])
                else:
                    print(f"Skipping non-dict item in {file_path}: {item}")
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return data


def process_markdown_file(file_path: str) -> List[Tuple[str, str]]:
    """
    Process a Markdown file and return chunked text data with topic.
    Splits by paragraphs.
    Returns list of (topic, text) tuples.
    """
    data: List[Tuple[str, str]] = []
    try:
        with open(file_path, "r") as file:
            content = file.read()
            topic = get_topic_from_filename(file_path)

            if CHUNKING_STRATEGY == "fixed":
                chunks = fixed_size_chunk_data(content)
            else:
                chunks = sentence_chunk_text(content)

            # Add topic to each chunk
            data.extend([(topic, chunk) for chunk in chunks])

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return data


def process_text_file(file_path: str) -> List[Tuple[str, str]]:
    """
    Process a plain text file and return chunked text data with topic.
    Returns list of (topic, text) tuples.
    """
    data: List[Tuple[str, str]] = []
    try:
        with open(file_path, "r") as file:
            content = file.read()
            topic = get_topic_from_filename(file_path)

            if CHUNKING_STRATEGY == "fixed":
                chunks = fixed_size_chunk_data(content)
            else:
                chunks = sentence_chunk_text(content)

            # Add topic to each chunk
            data.extend([(topic, chunk) for chunk in chunks])

    except Exception as e:
        print(f"Error processing {file_path}: {e}")
    return data


def load_data_for_kb() -> List[Tuple[str, str]]:
    """
    Loads and chunks data from all supported files in the KB_DATA_DIR.
    Returns list of (topic, text) tuples to be added to the knowledge base.
    """
    data: List[Tuple[str, str]] = []

    for filename in os.listdir(KB_DATA_DIR):
        file_path = os.path.join(KB_DATA_DIR, filename)

        if os.path.isfile(file_path):
            if filename.endswith(".json"):
                data.extend(process_json_file(file_path))
            elif filename.endswith(".md"):
                data.extend(process_markdown_file(file_path))
            elif filename.endswith(".txt"):
                data.extend(process_text_file(file_path))

    return data


# Embedding Functions
def create_embeddings(text: str, prefix: str = "search_query") -> List[float]:
    """
    Creates embeddings for the given text using the configured embedding model.
    """
    response = openai_client_embedding.embeddings.create(
        model=EMBED_MODEL, input=[f"{prefix}: {text}"]
    )
    return response.data[0].embedding


# Vector Store Functions
def add_document(document: str, embedding: List[float], topic: str) -> None:
    """
    Adds a single document with its embedding to the vector store.
    Uses a collection that matches the provided topic.
    """
    collection = get_collection(topic)
    doc_id = str(uuid.uuid4())
    collection.add(ids=[doc_id], documents=[document], embeddings=[embedding])
    print(f"Added document {doc_id[:8]} to collection '{topic}'")


def get_collection(collection_name: str):
    """
    Returns the collection with the given name.
    If it doesn't exist, creates it.
    """
    collection = chromadb_client.get_or_create_collection(collection_name)
    doc_count = collection.count()
    print(f"Using collection '{collection_name}'")
    print(f"Current document count: {doc_count}")
    return collection


def clear_collections() -> None:
    """
    Deletes all existing collections from the ChromaDB instance.
    """
    for collection_name in chromadb_client.list_collections():
        chromadb_client.delete_collection(collection_name)
