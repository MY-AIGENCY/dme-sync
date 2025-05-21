"""
relationship_graph.py
---------------------
Section 3: Relationship Graph for DME Knowledge Base

- Connects to Neo4j Aura using credentials from .env
- Upserts nodes and relationships (e.g., Staff, Program, Event)
- Materializes adjacency list back into Postgres for fast joins
- Designed for modularity, testability, and VAPI integration

Author: CursorDevArchitect (Fred)
"""

import os
import json
import logging
import time
from typing import Dict, Any, List
from dotenv import load_dotenv
from neo4j import GraphDatabase
import psycopg2
from neo4j.exceptions import ServiceUnavailable, SessionExpired, TransientError

# Load environment variables
load_dotenv()

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

POSTGRES_DSN = os.getenv("POSTGRES_DSN")  # e.g., "dbname=... user=... password=... host=... port=..."

BATCH_SIZE = int(os.getenv("NEO4J_BATCH_SIZE", 50))
MAX_RETRIES = int(os.getenv("NEO4J_MAX_RETRIES", 3))
RETRY_BACKOFF = float(os.getenv("NEO4J_RETRY_BACKOFF", 2.0))  # seconds, exponential

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

def get_normalized_records(conn) -> List[Dict[str, Any]]:
    """Fetch normalized records from Postgres."""
    with conn.cursor() as cur:
        cur.execute("SELECT doc_id, canonical_url, entity_type, text, raw FROM kb_docs")
        rows = cur.fetchall()
        logging.info(f"Fetched {len(rows)} records from Postgres kb_docs.")
        print(f"Fetched {len(rows)} records from Postgres kb_docs.")
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

def upsert_node(tx, label: str, doc: Dict[str, Any]):
    try:
        logging.info(f"Upserting node: label={label}, doc_id={doc['doc_id']}")
        print(f"Upserting node: label={label}, doc_id={doc['doc_id']}")
        tx.run(
            f"""
            MERGE (n:{label} {{doc_id: $doc_id}})
            SET n += $props
            """,
            doc_id=doc["doc_id"],
            props={k: v for k, v in doc.items() if k != "raw"}
        )
    except Exception as e:
        logging.error(f"Error upserting node {doc['doc_id']}: {e}")
        print(f"Error upserting node {doc['doc_id']}: {e}")

def upsert_relationship(tx, from_label: str, from_id: str, rel: str, to_label: str, to_id: str):
    try:
        logging.info(f"Upserting relationship: ({from_label}:{from_id})-[:{rel}]->({to_label}:{to_id})")
        print(f"Upserting relationship: ({from_label}:{from_id})-[:{rel}]->({to_label}:{to_id})")
        tx.run(
            f"""
            MATCH (a:{from_label} {{doc_id: $from_id}}), (b:{to_label} {{doc_id: $to_id}})
            MERGE (a)-[r:{rel}]->(b)
            """,
            from_id=from_id,
            to_id=to_id
        )
    except Exception as e:
        logging.error(f"Error upserting relationship {from_id}->{to_id}: {e}")
        print(f"Error upserting relationship {from_id}->{to_id}: {e}")

def process_graph_batch(records: List[Dict[str, Any]], driver, batch_num: int):
    """Process a batch of records: upsert nodes and relationships."""
    try:
        with driver.session() as session:
            for doc in records:
                label = doc["entity_type"].capitalize()
                session.write_transaction(upsert_node, label, doc)
                # --- New: Upsert entities and relationships from enrichment ---
                for entity in doc.get("entities", []):
                    session.write_transaction(upsert_node, "Entity", {"doc_id": entity, "name": entity})
                for rel in doc.get("relationships", []):
                    session.write_transaction(
                        upsert_relationship,
                        "Entity", rel.get("subject"),
                        rel.get("predicate", "RELATED_TO"),
                        "Entity", rel.get("object")
                    )
                # Existing logic for staff/program
                raw = doc["raw"]
                if label == "Staff" and "program_ids" in raw:
                    for pid in raw["program_ids"]:
                        session.write_transaction(
                            upsert_relationship, "Staff", doc["doc_id"], "COACHES", "Program", pid
                        )
        logging.info(f"Batch {batch_num}: Successfully processed {len(records)} records.")
    except (ServiceUnavailable, SessionExpired, TransientError) as e:
        logging.error(f"Batch {batch_num}: Neo4j connection error: {e}")
        raise
    except Exception as e:
        logging.error(f"Batch {batch_num}: Unexpected error: {e}")
        raise

def process_graph_with_retries(records: List[Dict[str, Any]], driver):
    total = len(records)
    num_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    for i in range(num_batches):
        batch = records[i * BATCH_SIZE : (i + 1) * BATCH_SIZE]
        attempt = 0
        while attempt <= MAX_RETRIES:
            try:
                process_graph_batch(batch, driver, i + 1)
                break  # Success
            except (ServiceUnavailable, SessionExpired, TransientError) as e:
                attempt += 1
                if attempt > MAX_RETRIES:
                    logging.error(f"Batch {i+1}: Failed after {MAX_RETRIES} retries. Skipping batch.")
                    break
                backoff = RETRY_BACKOFF * (2 ** (attempt - 1))
                logging.warning(f"Batch {i+1}: Retry {attempt}/{MAX_RETRIES} after error: {e}. Backing off {backoff:.1f}s.")
                time.sleep(backoff)
            except Exception as e:
                logging.error(f"Batch {i+1}: Non-retryable error: {e}. Skipping batch.")
                break

def materialize_adjacency_to_postgres(records: List[Dict[str, Any]], conn):
    """Materialize adjacency list from Neo4j into Postgres for fast joins."""
    # Placeholder: implement as needed for your schema
    pass

def ensure_kb_docs_table(conn):
    """Ensure the kb_docs table exists. Auto-create in dev/test, fail in prod."""
    with conn.cursor() as cur:
        try:
            cur.execute("SELECT 1 FROM kb_docs LIMIT 1;")
        except Exception as e:
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
    print("[DEBUG] Starting relationship graph pipeline main()")
    # Connect to Postgres
    pg_conn = psycopg2.connect(POSTGRES_DSN)
    ensure_kb_docs_table(pg_conn)
    records = get_normalized_records(pg_conn)
    print(f"[DEBUG] Number of records fetched from Postgres: {len(records)}")
    logging.info(f"Fetched {len(records)} normalized records from Postgres.")
    # Connect to Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    process_graph_with_retries(records, driver)
    logging.info("Graph upsert complete.")
    # Materialize adjacency list (optional/expandable)
    materialize_adjacency_to_postgres(records, pg_conn)
    logging.info("Adjacency list materialization complete.")
    pg_conn.close()
    driver.close()

if __name__ == "__main__":
    main() 