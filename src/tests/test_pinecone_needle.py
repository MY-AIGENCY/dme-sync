import os
import time
import pinecone
import numpy as np
import pytest
from indexer.chunk_embed_index import get_embedding

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "dme-kb")

# Initialize Pinecone client
pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

# Test data: 3 simple vectors with unique content
TEST_VECTORS = [
    {"id": "needle-1", "values": [1.0] * 1536, "metadata": {"desc": "all ones"}},
    {"id": "needle-2", "values": [0.5] * 1536, "metadata": {"desc": "all halfs"}},
    {"id": "needle-3", "values": [0.0] * 1535 + [0.1], "metadata": {"desc": "single non-zero at end"}},
]

@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    # Upsert test vectors
    index.upsert(vectors=TEST_VECTORS)
    yield
    # Clean up test vectors
    index.delete(ids=[v["id"] for v in TEST_VECTORS])

def test_needle_queries():
    for v in TEST_VECTORS:
        start = time.time()
        query_vec = v["values"]
        result = index.query(vector=query_vec, top_k=1, include_metadata=True)
        elapsed = time.time() - start
        assert result["matches"], f"No match for {v['id']}"
        top = result["matches"][0]
        print(f"Query for {v['id']} (desc: {v['metadata']['desc']}):")
        print(f"  Top match: {top['id']} (score: {top['score']:.4f}, latency: {elapsed:.3f}s)")
        assert top["id"] == v["id"], f"Expected {v['id']}, got {top['id']}"
        assert top["score"] > 0.99, f"Low score for {v['id']}: {top['score']}" 