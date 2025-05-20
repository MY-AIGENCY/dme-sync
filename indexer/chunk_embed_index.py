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
from dotenv import load_dotenv
import pinecone
import hashlib
from typing import List, Dict, Any
from tqdm import tqdm
import re
from indexer.pinecone_utils import log_upsert_manifest_to_s3, get_pinecone_index_stats
import time
import random
import boto3
import json
import sys
from pinecone import Pinecone

# Load environment variables
load_dotenv(override=True)

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
CHECKPOINT_KEY = os.getenv("CHECKPOINT_KEY", "checkpoints/chunk_embed_checkpoint.json")
DRY_RUN_LIMIT = int(os.getenv("DRY_RUN_LIMIT", 10))  # Set to 0 for full run
BATCH_SIZE = 200
THROTTLE_SEC = 1.0
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "dme-kb")  # Best practice: explicit namespace

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# Initialize OpenAI
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Initialize Pinecone
if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY environment variable is required")

# Use the new Pinecone client API
pc = Pinecone(api_key=PINECONE_API_KEY, pool_threads=10)

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
            spec=pinecone.ServerlessSpec(
                cloud='aws',
                region='us-east-1'
            )
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

s3 = boto3.client("s3")

# Helper: Save checkpoint to S3
def save_checkpoint(last_doc_idx):
    checkpoint = {"last_doc_idx": last_doc_idx}
    s3.put_object(Bucket=os.getenv("S3_BUCKET_NAME", "raw-site-data"), Key=CHECKPOINT_KEY, Body=json.dumps(checkpoint).encode("utf-8"))
    logging.info(f"Checkpoint saved at doc idx {last_doc_idx}")

# Helper: Load checkpoint from S3
def load_checkpoint():
    try:
        resp = s3.get_object(Bucket=os.getenv("S3_BUCKET_NAME", "raw-site-data"), Key=CHECKPOINT_KEY)
        checkpoint = json.loads(resp["Body"].read())
        return checkpoint.get("last_doc_idx", 0)
    except Exception:
        return 0

# Exponential backoff
def backoff_sleep(attempt):
    delay = min(60, (2 ** attempt) + random.uniform(0, 1))
    logging.warning(f"Backing off for {delay:.1f} seconds...")
    time.sleep(delay)

def process_and_upsert():
    logging.info("=== ENVIRONMENT VARIABLES ===")
    logging.info(f"S3_BUCKET_NAME={os.getenv('S3_BUCKET_NAME')}")
    logging.info(f"POSTGRES_DSN={os.getenv('POSTGRES_DSN')}")
    logging.info(f"DRY_RUN_LIMIT={DRY_RUN_LIMIT}")
    logging.info(f"PINECONE_NAMESPACE={PINECONE_NAMESPACE}")
    pg_conn = psycopg2.connect(POSTGRES_DSN)
    records = get_normalized_records(pg_conn)
    logging.info(f"Loaded {len(records)} records from Postgres.")
    logging.info("First 5 canonical URLs:")
    for r in records[:5]:
        logging.info(f"  {r['canonical_url']}")
    pinecone_index = ensure_pinecone_index()
    batch = []
    total_upserted = 0
    get_pinecone_index_stats()  # Log stats before upserts
    start_idx = load_checkpoint()
    end_idx = start_idx + DRY_RUN_LIMIT if DRY_RUN_LIMIT > 0 else len(records)
    logging.info(f"DRY_RUN_LIMIT={DRY_RUN_LIMIT}, processing records {start_idx} to {end_idx-1} (total: {end_idx-start_idx}) out of {len(records)} available.")
    processed_docs = 0
    for doc_idx, doc in enumerate(tqdm(records, desc="Processing docs")):
        if doc_idx < start_idx:
            continue
        if DRY_RUN_LIMIT > 0 and doc_idx >= end_idx:
            break
        processed_docs += 1
        # Hierarchical chunking
        section_chunks = chunk_text(doc["text"], level="section")
        logging.info(f"Doc {doc_idx} ({doc['canonical_url']}): {len(section_chunks)} section chunks.")
        for section in section_chunks:
            para_chunks = chunk_text(section, level="paragraph")
            logging.info(f"  Section: {len(para_chunks)} paragraph chunks.")
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
                logging.info(f"Batch size before upsert check: {len(batch)}")
                if len(batch) >= BATCH_SIZE:
                    # Upsert with async and backoff
                    for attempt in range(5):
                        try:
                            logging.info(f"[UPSERT] Attempting to upsert {len(batch)} vectors to Pinecone (namespace={PINECONE_NAMESPACE})...")
                            response = pinecone_index.upsert(vectors=batch, namespace=PINECONE_NAMESPACE, async_req=True)
                            # Wait for async result
                            result = response.get()
                            logging.info(f"[UPSERT] Pinecone response: {result}")
                            log_upsert_manifest_to_s3(batch)
                            total_upserted += len(batch)
                            break
                        except Exception as e:
                            if hasattr(e, 'status') and e.status == 429:
                                wait = 2 ** attempt + random.uniform(0, 1)
                                logging.warning(f"[UPSERT] Rate limited (429). Backing off {wait:.2f}s...")
                                time.sleep(wait)
                            else:
                                logging.error(f"[UPSERT] Error: {e}")
                                raise
                    batch = []
    if batch:
        for attempt in range(5):
            try:
                logging.info(f"[UPSERT] Attempting to upsert {len(batch)} vectors to Pinecone (namespace={PINECONE_NAMESPACE})...")
                response = pinecone_index.upsert(vectors=batch, namespace=PINECONE_NAMESPACE)
                logging.info(f"[UPSERT] Pinecone response: {response}")
                log_upsert_manifest_to_s3(batch)
                total_upserted += len(batch)
                logging.info(f"Upserted {total_upserted} vectors total.")
                get_pinecone_index_stats()
                save_checkpoint(end_idx-1)
                time.sleep(THROTTLE_SEC)
                break
            except Exception as e:
                logging.error(f"Error upserting final batch: {e}")
                backoff_sleep(attempt)
    logging.info(f"Chunk, embed, index pipeline complete. Processed {processed_docs} docs in this run.")
    pg_conn.close()
    if DRY_RUN_LIMIT > 0:
        logging.info("DRY_RUN_LIMIT reached, exiting early for test.")
        sys.exit(0)

# TODO: Add Weaviate and local embedding support (modularize get_embedding and upsert)

def main():
    process_and_upsert()

def test_pinecone_hybrid_index():
    from pinecone import Pinecone, ServerlessSpec
    import os
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "llama-text-embed-v2")
    SPARSE_MODEL = os.getenv("SPARSE_MODEL", "pinecone-sparse-english")
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "dme-kb-hybrid")
    pc = Pinecone(api_key=PINECONE_API_KEY)
    index_list = pc.list_indexes()
    if PINECONE_INDEX_NAME not in index_list.names():
        print(f"Creating hybrid index {PINECONE_INDEX_NAME}...")
        pc.create_index(
            name=PINECONE_INDEX_NAME,
            metric="cosine",
            dimension=1024,  # llama-text-embed-v2 default
            embed_model=EMBEDDING_MODEL,
            sparse_model=SPARSE_MODEL,
            spec=ServerlessSpec(cloud="aws", region="us-east-1"),
        )
        print(f"Created hybrid index {PINECONE_INDEX_NAME}.")
    else:
        print(f"Hybrid index {PINECONE_INDEX_NAME} already exists.")
    index = pc.Index(PINECONE_INDEX_NAME)
    print(f"Connected to hybrid index {PINECONE_INDEX_NAME}.")

if __name__ == "__main__":
    # Usage: poetry run python -m indexer.chunk_embed_index
    main() 