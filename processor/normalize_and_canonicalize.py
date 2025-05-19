import hashlib
import json
import logging
import os
import re
import sys
from typing import Dict, Any, Optional
import psycopg2
from jsonschema import validate, ValidationError
import boto3
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

# JSONSchema v1.0 placeholder (to be updated in docs/schema_v1.md)
SCHEMA_V1 = {
    "type": "object",
    "properties": {
        "doc_id": {"type": "string"},
        "canonical_url": {"type": "string", "format": "uri"},
        "entity_type": {"type": "string"},
        "text": {"type": "string"},
        "raw": {"type": "object"},
    },
    "required": ["doc_id", "canonical_url", "entity_type", "text", "raw"]
}

ENTITY_PATTERNS = {
    "event": re.compile(r"/event|/events|/calendar", re.I),
    "staff": re.compile(r"/staff|/coach|/faculty", re.I),
    "program": re.compile(r"/program|/course|/curriculum", re.I),
}

def sha256_of_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()

def clean_text(text: str) -> str:
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def detect_entity_type(url: str, html: str) -> str:
    for entity, pattern in ENTITY_PATTERNS.items():
        if pattern.search(url):
            return entity
    if "schema.org/Event" in html:
        return "event"
    if "schema.org/Person" in html:
        return "staff"
    if "schema.org/Course" in html or "Program" in html:
        return "program"
    return "other"

def validate_schema(doc: Dict[str, Any]) -> Optional[str]:
    try:
        validate(instance=doc, schema=SCHEMA_V1)
        return None
    except ValidationError as e:
        return str(e)

def persist_to_postgres(doc: Dict[str, Any], conn):
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO kb_docs (doc_id, canonical_url, entity_type, text, raw)
            VALUES (%s, %s, %s, %s, %s)
            ON CONFLICT (doc_id) DO UPDATE SET
                canonical_url=EXCLUDED.canonical_url,
                entity_type=EXCLUDED.entity_type,
                text=EXCLUDED.text,
                raw=EXCLUDED.raw;
            """,
            [doc["doc_id"], doc["canonical_url"], doc["entity_type"], doc["text"], json.dumps(doc["raw"])]
        )
    conn.commit()

def quarantine_failure(doc: Dict[str, Any], reason: str, quarantine_bucket: str = None):
    if not quarantine_bucket:
        logging.warning(f"Document {doc.get('doc_id', 'unknown')} quarantined: {reason} (no quarantine bucket set)")
        return
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
    )
    doc_id = doc.get("doc_id", "unknown")
    key = f"quarantine/{doc_id}.json"
    s3.put_object(Bucket=quarantine_bucket, Key=key, Body=json.dumps({"doc": doc, "reason": reason}, indent=2).encode('utf-8'))
    logging.warning(f"Document {doc_id} quarantined to S3 bucket {quarantine_bucket}: {reason}")

def process_raw_page(raw: Dict[str, Any], conn, quarantine_bucket=None):
    url = raw.get("url")
    html = raw.get("html", "")
    canonical_url = url
    doc_id = sha256_of_url(canonical_url)
    text = clean_text(html)
    entity_type = detect_entity_type(canonical_url, html)
    doc = {
        "doc_id": doc_id,
        "canonical_url": canonical_url,
        "entity_type": entity_type,
        "text": text,
        "raw": raw,
    }
    validation_error = validate_schema(doc)
    if validation_error:
        quarantine_failure(doc, validation_error, quarantine_bucket)
    else:
        persist_to_postgres(doc, conn)
        logging.info(f"Document {doc_id} processed and stored.")

def stream_s3_raw_pages(bucket: str, prefix: str = "raw/"):
    """Yield raw page JSONs from S3 bucket under the given prefix."""
    s3 = boto3.client(
        's3',
        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
        region_name=os.getenv('AWS_REGION', 'us-east-1'),
    )
    paginator = s3.get_paginator('list_objects_v2')
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            key = obj['Key']
            if not key.endswith('.json'):
                continue
            resp = s3.get_object(Bucket=bucket, Key=key)
            raw = json.loads(resp['Body'].read())
            yield raw

def ensure_kb_docs_table(conn):
    """Ensure the kb_docs table exists. Auto-create in dev/test, fail in prod."""
    with conn.cursor() as cur:
        try:
            cur.execute("SELECT 1 FROM kb_docs LIMIT 1;")
        except Exception as e:
            conn.rollback()  # Reset failed transaction
            env = os.getenv("ENV", "development").lower()
            if env in ("development", "dev", "test", "testing"):
                logging.warning("kb_docs table missing. Auto-creating for development/test.")
                cur.execute("""
                CREATE TABLE IF NOT EXISTS kb_docs (
                    doc_id TEXT PRIMARY KEY,
                    canonical_url TEXT,
                    entity_type TEXT,
                    text TEXT,
                    raw JSONB
                );
                """)
                conn.commit()
                logging.info("kb_docs table created.")
            else:
                raise RuntimeError("kb_docs table missing and not auto-created in production. Please run migrations.")

def main():
    bucket = os.getenv('S3_BUCKET_NAME', 'raw-site-data')
    quarantine_bucket = os.getenv('QUARANTINE_BUCKET_NAME')  # Optional: set in .env
    db_url = os.getenv('POSTGRES_DSN')
    conn = psycopg2.connect(db_url)
    ensure_kb_docs_table(conn)
    count = 0
    for raw in stream_s3_raw_pages(bucket):
        process_raw_page(raw, conn, quarantine_bucket)
        count += 1
        if count % 100 == 0:
            logging.info(f"Processed {count} raw pages...")
    conn.close()
    logging.info(f"Normalization complete. Total processed: {count}")

if __name__ == "__main__":
    main() 