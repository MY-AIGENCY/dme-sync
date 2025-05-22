import os
import pytest
import importlib
import sys

@pytest.fixture(scope="session", autouse=True)
def clear_postgres():
    try:
        import importlib
        importlib.import_module("psycopg2")
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "psycopg2 failed to import – check that you are "
            "using psycopg2-binary>=2.9.9 on Python 3.12 or "
            "have libpq-dev installed for source builds"
        ) from exc
    import psycopg2
    from dotenv import load_dotenv, find_dotenv
    load_dotenv(find_dotenv('.env'), override=True)
    dsn = os.getenv("POSTGRES_DSN")
    if not dsn:
        pytest.skip("POSTGRES_DSN not set in .env")
    conn = psycopg2.connect(dsn)
    with conn.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS kb_docs;")
        cur.execute("""
        CREATE TABLE IF NOT EXISTS kb_docs (
            doc_id TEXT PRIMARY KEY,
            canonical_url TEXT,
            entity_type TEXT,
            text TEXT,
            raw JSONB,
            entities JSONB,
            relationships JSONB,
            metadata JSONB
        );
        """)
    conn.commit()
    conn.close()

@pytest.fixture(scope="session", autouse=True)
def clear_neo4j():
    try:
        from neo4j import GraphDatabase
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "neo4j failed to import – check that you have the neo4j Python package installed."
        ) from exc
    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASSWORD")
    if not uri or not user or not password:
        pytest.skip("Neo4j credentials not set in .env")
    driver = GraphDatabase.driver(uri, auth=(user, password))
    with driver.session() as session:
        session.run("MATCH (n) DETACH DELETE n")
    driver.close() 