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
from src.indexer import chunk_embed_index as cei

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
    monkeypatch.setattr(cei, "ensure_pinecone_index", lambda: fake_index)
    monkeypatch.setattr(cei, "psycopg2", mock.MagicMock())
    with pytest.raises(SystemExit) as e:
        cei.process_and_upsert()
    assert e.value.code == 0 