import os
import pytest

# Pinecone
try:
    import pinecone
    PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
    PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "dme-kb")
    pinecone_ok = False
    if PINECONE_API_KEY:
        pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
        try:
            indexes = pc.list_indexes()
            print(f"[HEALTH] Pinecone indexes: {indexes.names()}")
            if PINECONE_INDEX_NAME in indexes.names():
                pinecone_ok = True
        except Exception as e:
            print(f"[HEALTH] Pinecone error: {e}")
    else:
        print("[HEALTH] Pinecone API key not set.")
except ImportError:
    print("[HEALTH] Pinecone not installed.")
    pinecone_ok = False

# Postgres
try:
    import psycopg2
    POSTGRES_DSN = os.getenv("POSTGRES_DSN")
    pg_ok = False
    if POSTGRES_DSN:
        try:
            conn = psycopg2.connect(POSTGRES_DSN)
            with conn.cursor() as cur:
                cur.execute("SELECT 1;")
                print(f"[HEALTH] Postgres connection OK.")
                pg_ok = True
            conn.close()
        except Exception as e:
            print(f"[HEALTH] Postgres error: {e}")
    else:
        print("[HEALTH] POSTGRES_DSN not set.")
except ImportError:
    print("[HEALTH] psycopg2 not installed.")
    pg_ok = False

# Neo4j
try:
    from neo4j import GraphDatabase
    NEO4J_URI = os.getenv("NEO4J_URI")
    NEO4J_USER = os.getenv("NEO4J_USER")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
    neo4j_ok = False
    if NEO4J_URI and NEO4J_USER and NEO4J_PASSWORD:
        try:
            driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
            with driver.session() as session:
                result = session.run("RETURN 1 AS ok")
                print(f"[HEALTH] Neo4j connection OK.")
                neo4j_ok = True
            driver.close()
        except Exception as e:
            print(f"[HEALTH] Neo4j error: {e}")
    else:
        print("[HEALTH] Neo4j credentials not set.")
except ImportError:
    print("[HEALTH] neo4j not installed.")
    neo4j_ok = False

# S3/MinIO
try:
    import boto3
    S3_BUCKET = os.getenv("S3_BUCKET_NAME", "raw-site-data")
    s3_ok = False
    try:
        s3 = boto3.client("s3")
        resp = s3.list_buckets()
        print(f"[HEALTH] S3 buckets: {[b['Name'] for b in resp.get('Buckets', [])]}")
        if any(b['Name'] == S3_BUCKET for b in resp.get('Buckets', [])):
            s3_ok = True
    except Exception as e:
        print(f"[HEALTH] S3 error: {e}")
except ImportError:
    print("[HEALTH] boto3 not installed.")
    s3_ok = False

def test_endpoint_health():
    assert pinecone_ok, "Pinecone endpoint not healthy or misconfigured."
    assert pg_ok, "Postgres endpoint not healthy or misconfigured."
    assert neo4j_ok, "Neo4j endpoint not healthy or misconfigured."
    assert s3_ok, "S3 endpoint not healthy or misconfigured." 