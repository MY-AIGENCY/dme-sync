#!/usr/bin/env python3
"""
Section 4: Chunk, Embed, Index Pipeline
- Reads normalized docs from Postgres (kb_docs)
- Hierarchical chunking: sections (≈512 tokens), paragraphs (≈128 tokens, 20% overlap)
- Embeds with OpenAI (for now)
- Upserts to Pinecone (default)
- Modular for future Weaviate/local embedding support
"""
import os
import logging
import psycopg2
import openai
import pinecone
import hashlib
from dotenv import load_dotenv
from typing import List, Dict, Any
from tqdm import tqdm
import re

# Load environment variables
load_dotenv()

POSTGRES_DSN = os.getenv("POSTGRES_DSN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSION = 1536
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "dme-kb")
CHUNK_SECTION_TOKENS = int(os.getenv("CHUNK_SECTION_TOKENS", 512))
CHUNK_PARAGRAPH_TOKENS = int(os.getenv("CHUNK_PARAGRAPH_TOKENS", 128))
CHUNK_PARAGRAPH_OVERLAP = float(os.getenv("CHUNK_PARAGRAPH_OVERLAP", 0.2))

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Initialize OpenAI
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Initialize Pinecone
if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY environment variable is required")
pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)

# Tokenizer (simple whitespace for now; TODO: use tiktoken or transformers for accurate count)
def simple_tokenize(text: str) -> List[str]:
    return text.split()

def chunk_text(text: str, level: str = "section") -> List[str]:
    tokens = simple_tokenize(text)
    if level == "section":
        chunk_size = CHUNK_SECTION_TOKENS
        overlap = 0
    else:
        chunk_size = CHUNK_PARAGRAPH_TOKENS
        overlap = int(CHUNK_PARAGRAPH_TOKENS * CHUNK_PARAGRAPH_OVERLAP)
    chunks = []
    i = 0
    while i < len(tokens):
        chunk = tokens[i:i+chunk_size]
        if not chunk:
            break
        chunks.append(" ".join(chunk))
        if overlap:
            i += chunk_size - overlap
        else:
            i += chunk_size
    return chunks

def get_embedding(text: str, model=EMBEDDING_MODEL) -> List[float]:
    # Truncate text if too long
    if len(text) > 25000:
        text = text[:25000]
    try:
        response = client.embeddings.create(input=text, model=model)
        return response.data[0].embedding
    except Exception as e:
        logging.error(f"Error getting embedding: {e}")
        return [0.0] * EMBEDDING_DIMENSION

def ensure_pinecone_index():
    index_list = pc.list_indexes()
    if PINECONE_INDEX_NAME not in index_list.names():
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            dimension=EMBEDDING_DIMENSION,
            metric="cosine",
            spec=pinecone.ServerlessSpec(cloud='aws', region='us-east-1')
        )
        logging.info(f"Created Pinecone index: {PINECONE_INDEX_NAME}")
    return pc.Index(PINECONE_INDEX_NAME)

def get_normalized_records(conn) -> List[Dict[str, Any]]:
    with conn.cursor() as cur:
        cur.execute("SELECT doc_id, canonical_url, entity_type, text, raw FROM kb_docs")
        rows = cur.fetchall()
        return [
            {
                "doc_id": r[0],
                "canonical_url": r[1],
                "entity_type": r[2],
                "text": r[3],
                "raw": r[4],
            }
            for r in rows
        ]

def process_and_upsert():
    logging.info("Starting chunk, embed, index pipeline...")
    pg_conn = psycopg2.connect(POSTGRES_DSN)
    records = get_normalized_records(pg_conn)
    pinecone_index = ensure_pinecone_index()
    batch = []
    for doc in tqdm(records, desc="Processing docs"):
        # Hierarchical chunking
        section_chunks = chunk_text(doc["text"], level="section")
        for section in section_chunks:
            para_chunks = chunk_text(section, level="paragraph")
            for para in para_chunks:
                chunk_id = hashlib.sha256((doc["doc_id"] + para).encode()).hexdigest()
                embedding = get_embedding(para)
                meta = {
                    "doc_id": doc["doc_id"],
                    "canonical_url": doc["canonical_url"],
                    "entity_type": doc["entity_type"],
                }
                batch.append({
                    "id": chunk_id,
                    "values": embedding,
                    "metadata": meta
                })
                if len(batch) >= 100:
                    pinecone_index.upsert(vectors=batch)
                    batch = []
    if batch:
        pinecone_index.upsert(vectors=batch)
    logging.info("Chunk, embed, index pipeline complete.")
    pg_conn.close()

# TODO: Add Weaviate and local embedding support (modularize get_embedding and upsert)

def main():
    process_and_upsert()

if __name__ == "__main__":
    main() 