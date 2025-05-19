import hashlib
import json
import logging
import os
import re
import sys
from typing import Dict, Any, Optional
import psycopg2
from jsonschema import validate, ValidationError

# Configure logging
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

# Entity detection rules (expand as needed)
ENTITY_PATTERNS = {
    "event": re.compile(r"/event|/events|/calendar", re.I),
    "staff": re.compile(r"/staff|/coach|/faculty", re.I),
    "program": re.compile(r"/program|/course|/curriculum", re.I),
}

def sha256_of_url(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()

def clean_text(text: str) -> str:
    # Collapse whitespace, remove non-printables, basic readability
    text = re.sub(r"\s+", " ", text)
    return text.strip()

def detect_entity_type(url: str, html: str) -> str:
    for entity, pattern in ENTITY_PATTERNS.items():
        if pattern.search(url):
            return entity
    # Fallback: look for cues in HTML
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

def quarantine_failure(doc: Dict[str, Any], reason: str, quarantine_dir: str = "quarantine"):
    os.makedirs(quarantine_dir, exist_ok=True)
    doc_id = doc.get("doc_id", "unknown")
    with open(os.path.join(quarantine_dir, f"{doc_id}.json"), "w") as f:
        json.dump({"doc": doc, "reason": reason}, f, indent=2)
    logging.warning(f"Document {doc_id} quarantined: {reason}")

def process_raw_page(raw: Dict[str, Any], conn):
    url = raw.get("url")
    html = raw.get("html", "")
    canonical_url = url  # TODO: canonicalization logic if needed
    doc_id = sha256_of_url(canonical_url)
    text = clean_text(html)  # TODO: use readability if available
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
        quarantine_failure(doc, validation_error)
    else:
        persist_to_postgres(doc, conn)
        logging.info(f"Document {doc_id} processed and stored.")

def main(raw_pages_path: str, db_url: str):
    # Connect to Postgres
    conn = psycopg2.connect(db_url)
    with open(raw_pages_path) as f:
        for line in f:
            raw = json.loads(line)
            process_raw_page(raw, conn)
    conn.close()

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python normalize_and_canonicalize.py <raw_pages.jsonl> <postgres_dsn>")
        sys.exit(1)
    main(sys.argv[1], sys.argv[2]) 