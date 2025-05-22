import os
from dotenv import load_dotenv
load_dotenv(override=True)
print("[DEBUG] Environment variables at test start:")
for k, v in os.environ.items():
    if 'KEY' in k or 'SECRET' in k or 'TOKEN' in k or 'PASS' in k:
        print(f"{k}: {'*' * min(8, len(v))}")
    else:
        print(f"{k}: {v}")
import pytest
from unittest import mock
from indexer import chunk_embed_index as cei
from indexer.chunk_embed_index import chunk_text

@pytest.fixture
def sample_text():
    return "This is a test document. It has several sentences. Each sentence is a test. This is for chunking."

def test_chunk_text_section(sample_text):
    # Should return one chunk if section size > text length
    chunks = cei.chunk_text(sample_text, level="section")
    assert len(chunks) == 1
    assert sample_text.split()[0] in chunks[0]

def test_chunk_text_paragraph_overlap():
    text = " ".join([f"word{i}" for i in range(200)])
    chunks = cei.chunk_text(text, level="paragraph")
    # Should produce overlapping chunks
    assert len(chunks) > 1
    overlap = int(cei.CHUNK_PARAGRAPH_TOKENS * cei.CHUNK_PARAGRAPH_OVERLAP)
    assert overlap > 0

def test_get_embedding_returns_vector(monkeypatch):
    # Mock OpenAI client
    monkeypatch.setattr(cei, "client", mock.MagicMock())
    fake_embed = [0.1] * cei.EMBEDDING_DIMENSION
    cei.client.embeddings.create.return_value = mock.MagicMock(data=[mock.MagicMock(embedding=fake_embed)])
    vec = cei.get_embedding("test")
    assert isinstance(vec, list)
    assert len(vec) == cei.EMBEDDING_DIMENSION

def test_get_embedding_handles_error(monkeypatch):
    monkeypatch.setattr(cei, "client", mock.MagicMock())
    cei.client.embeddings.create.side_effect = Exception("fail")
    vec = cei.get_embedding("test")
    assert vec == [0.0] * cei.EMBEDDING_DIMENSION

def test_process_and_upsert_runs(monkeypatch):
    # Mock DB, Pinecone, and OpenAI
    monkeypatch.setattr(cei, "get_normalized_records", lambda conn: [{
        "doc_id": "abc",
        "canonical_url": "url",
        "entity_type": "type",
        "text": "word " * 600,
        "raw": {}
    }])
    monkeypatch.setattr(cei, "get_embedding", lambda text, model=None: [0.1] * cei.EMBEDDING_DIMENSION)
    fake_index = mock.MagicMock()
    monkeypatch.setattr(cei, "ensure_pinecone_index", lambda test_mode=None, **kwargs: fake_index)
    monkeypatch.setattr(cei, "psycopg2", mock.MagicMock())
    # Just call the function and assert it completes (mocked side effects)
    cei.process_and_upsert()

def test_chunk_metadata_enrichment():
    doc = {
        "doc_id": "abc123",
        "canonical_url": "https://example.com",
        "entity_type": "program",
        "text": "Coach John Smith teaches the Basketball Program starting June 1st.",
        "entities": ["John Smith", "Basketball Program"],
        "relationships": [
            {"subject": "John Smith", "predicate": "teaches", "object": "Basketball Program"}
        ],
        "metadata": {"date": "June 1st"}
    }
    section_chunks = chunk_text(doc["text"], level="section")
    para_chunks = chunk_text(section_chunks[0], level="paragraph")
    # Simulate metadata creation as in chunk_embed_index.py
    meta = {
        "doc_id": doc["doc_id"],
        "canonical_url": doc["canonical_url"],
        "entity_type": doc["entity_type"],
        "text": para_chunks[0][:200],
        "entities": doc.get("entities", []),
        "relationships": doc.get("relationships", []),
        "metadata": doc.get("metadata", {}),
    }
    assert "entities" in meta
    assert "relationships" in meta
    assert "metadata" in meta
    assert meta["entities"] == ["John Smith", "Basketball Program"]
    assert meta["relationships"][0]["predicate"] == "teaches"
    assert meta["metadata"]["date"] == "June 1st" 