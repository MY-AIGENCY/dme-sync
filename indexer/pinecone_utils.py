import os
import json
import pinecone
import boto3
from datetime import datetime, timezone

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "dme-kb")
S3_BUCKET = os.getenv("S3_BUCKET_NAME", "raw-site-data")
S3_MANIFEST_PREFIX = "manifests/pinecone_upsert_"

# Initialize Pinecone client
pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)

# Initialize S3 client
s3 = boto3.client("s3")

def clear_pinecone_index():
    """Delete all vectors from the Pinecone index."""
    index = pc.Index(PINECONE_INDEX_NAME)
    stats = index.describe_index_stats()
    ids = []
    for ns, ns_stats in stats.get("namespaces", {}).items():
        ids.extend(ns_stats.get("vector_count", 0) * [ns])  # Placeholder for actual IDs
    # Pinecone does not provide a direct way to list all IDs; you must track them or use a filter to delete all
    # Here, we use delete(delete_all=True) to clear the index
    index.delete(delete_all=True)
    print(f"Cleared all vectors from Pinecone index: {PINECONE_INDEX_NAME}")

def get_pinecone_index_stats():
    """Return Pinecone index stats (vector count, etc)."""
    index = pc.Index(PINECONE_INDEX_NAME)
    stats = index.describe_index_stats()
    print(json.dumps(stats, indent=2))
    return stats

def log_upsert_manifest_to_s3(vectors):
    """Log upserted vector IDs and metadata to S3 as a manifest."""
    now = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    manifest_key = f"{S3_MANIFEST_PREFIX}{now}.jsonl"
    lines = [json.dumps({"id": v["id"], "metadata": v.get("metadata", {}), "timestamp": now}) for v in vectors]
    body = "\n".join(lines).encode("utf-8")
    s3.put_object(Bucket=S3_BUCKET, Key=manifest_key, Body=body)
    print(f"Logged upsert manifest to S3: {manifest_key}")
    return manifest_key 