import os
import sys
import pytest
from unittest.mock import patch, MagicMock

# Create mock modules before importing any modules that use them
mock_chromadb = MagicMock()
mock_collection = MagicMock()
mock_chromadb.HttpClient.return_value.get_or_create_collection.return_value = (
    mock_collection
)

# Mock the chromadb module
sys.modules["chromadb"] = mock_chromadb

# Mock LLMObs instrumentation. These unit tests validate ingestion behavior,
# not Datadog span delivery.
def passthrough_decorator(func=None, *args, **kwargs):
    if func is None:
        return lambda wrapped: wrapped
    return func


mock_llmobs = MagicMock()
mock_llmobs.LLMObs.enable = MagicMock()
mock_llmobs_decorators = MagicMock()
mock_llmobs_decorators.workflow = passthrough_decorator
mock_llmobs_decorators.tool = passthrough_decorator
mock_llmobs_decorators.embedding = passthrough_decorator
sys.modules["ddtrace.llmobs"] = mock_llmobs
sys.modules["ddtrace.llmobs.decorators"] = mock_llmobs_decorators

# Now we can safely import our modules
import ingest_documents
from ingest_documents import create_document_embeddings, store_document


@pytest.fixture
def mock_environment():
    """Set up test environment variables"""
    os.environ["DD_LLMOBS_ML_APP"] = "test-app"
    os.environ["DD_API_KEY"] = "test-key"
    os.environ["DD_SITE"] = "test-site"
    os.environ["DD_LLMOBS_AGENTLESS_ENABLED"] = "true"


@pytest.fixture
def mock_documents():
    """Mock document data"""
    return [
        ("quantum_physics", "This is a document about quantum physics"),
        ("machine_learning", "This is a document about machine learning"),
    ]


@patch("ingest_documents.create_embeddings")
def test_create_document_embeddings_success(mock_create_embeddings):
    """Test successful document embedding creation"""
    # Setup
    mock_create_embeddings.return_value = [0.1, 0.2, 0.3]
    document = "This is a test document"
    topic = "test_topic"

    # Execute
    embeddings, metadata = create_document_embeddings(document, topic)

    # Assert
    assert len(embeddings) == 3
    assert metadata["status"] == "success"
    mock_create_embeddings.assert_called_once_with(document, "search_document")


@patch("ingest_documents.create_embeddings")
def test_create_document_embeddings_error(mock_create_embeddings):
    """Test error handling in document embedding creation"""
    # Setup
    mock_create_embeddings.side_effect = Exception("Embedding error")
    document = "This is a test document"
    topic = "test_topic"

    # Execute
    embeddings, metadata = create_document_embeddings(document, topic)

    # Assert
    assert embeddings == []
    assert metadata["status"] == "error"
    assert "Embedding error" in metadata["error"]


@patch("ingest_documents.add_document")
def test_store_document_success(mock_add_document):
    """Test successful document storing"""
    # Setup
    document = "This is a test document"
    embeddings = [0.1, 0.2, 0.3]
    topic = "test_topic"

    # Execute
    result = store_document(document, embeddings, topic)

    # Assert
    assert "success" in result["message"].lower()
    mock_add_document.assert_called_once_with(document, embeddings, topic)


@patch("ingest_documents.add_document")
def test_store_document_error(mock_add_document):
    """Test error handling in document storing"""
    # Setup
    mock_add_document.side_effect = Exception("Storage error")
    document = "This is a test document"
    embeddings = [0.1, 0.2, 0.3]
    topic = "test_topic"

    # Execute
    result = store_document(document, embeddings, topic)

    # Assert
    assert "error" in result["message"].lower()
    assert "Storage error" in result["message"]


@patch("ingest_documents.load_data_for_kb")
@patch("ingest_documents.create_document_embeddings")
@patch("ingest_documents.store_document")
def test_ingest_documents_success(
    mock_store_document,
    mock_create_embeddings,
    mock_load_data,
    mock_environment,
    mock_documents,
):
    """Test successful document ingestion workflow"""
    # Setup
    mock_load_data.return_value = mock_documents
    success_data = ([0.1, 0.2, 0.3], {"status": "success"})
    mock_create_embeddings.return_value = success_data
    success_message = {"message": "Document stored successfully"}
    mock_store_document.return_value = success_message

    # Execute
    ingest_documents.ingest_documents()

    # Assert
    assert mock_load_data.call_count == 1
    assert mock_create_embeddings.call_count == 2  # Once for each document
    assert mock_store_document.call_count == 2  # Once for each document


@patch("ingest_documents.load_data_for_kb")
@patch("ingest_documents.create_document_embeddings")
def test_ingest_documents_embedding_error(
    mock_create_embeddings, mock_load_data, mock_environment, mock_documents
):
    """Test handling of embedding errors in document ingestion workflow"""
    # Setup
    mock_load_data.return_value = mock_documents
    error = "Test embedding error"
    error_data = ([], {"status": "error", "error": error})
    mock_create_embeddings.return_value = error_data

    # Execute and Assert
    with pytest.raises(Exception) as excinfo:
        ingest_documents.ingest_documents()

    assert error in str(excinfo.value)
    # Should fail on first document
    assert mock_create_embeddings.call_count == 1


@patch("ingest_documents.load_data_for_kb")
@patch("ingest_documents.create_document_embeddings")
@patch("ingest_documents.store_document")
def test_ingest_documents_storage_error(
    mock_store_document,
    mock_create_embeddings,
    mock_load_data,
    mock_environment,
    mock_documents,
):
    """Test handling of storage errors in document ingestion workflow"""
    # Setup
    mock_load_data.return_value = mock_documents
    success_data = ([0.1, 0.2, 0.3], {"status": "success"})
    mock_create_embeddings.return_value = success_data
    error_msg = {"message": "Error storing document: Test storage error"}
    mock_store_document.return_value = error_msg

    # Execute and Assert
    with pytest.raises(Exception) as excinfo:
        ingest_documents.ingest_documents()

    assert "Error storing document" in str(excinfo.value)
    assert mock_create_embeddings.call_count == 1  # Process first document
    assert mock_store_document.call_count == 1  # Fail on first document
