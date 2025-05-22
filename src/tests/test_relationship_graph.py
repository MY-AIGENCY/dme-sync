import pytest
from unittest import mock
from indexer import relationship_graph as rg
from neo4j.exceptions import ServiceUnavailable
from unittest.mock import MagicMock, ANY

@pytest.fixture
def sample_records():
    return [
        {
            "doc_id": "staff1",
            "canonical_url": "https://dmeacademy.com/staff/jane-doe",
            "entity_type": "staff",
            "text": "Coach Jane Doe",
            "raw": {"program_ids": ["prog1", "prog2"]},
        },
        {
            "doc_id": "prog1",
            "canonical_url": "https://dmeacademy.com/programs/basketball",
            "entity_type": "program",
            "text": "Basketball Program",
            "raw": {},
        },
    ]

def test_upsert_node():
    """Test that upsert_node sends correct Cypher and parameters."""
    tx = mock.MagicMock()
    doc = {"doc_id": "abc", "entity_type": "staff", "text": "Test", "raw": {}}
    rg.upsert_node(tx, "Staff", doc)
    tx.run.assert_called()
    args, kwargs = tx.run.call_args
    assert "MERGE (n:Staff {doc_id: $doc_id})" in args[0]
    assert kwargs["doc_id"] == "abc"
    assert "raw" not in kwargs["props"]

def test_upsert_relationship():
    """Test that upsert_relationship sends correct Cypher and parameters."""
    tx = mock.MagicMock()
    rg.upsert_relationship(tx, "Staff", "staff1", "COACHES", "Program", "prog1")
    tx.run.assert_called()
    args, kwargs = tx.run.call_args
    assert "MERGE (a)-[r:COACHES]->(b)" in args[0]
    assert kwargs["from_id"] == "staff1"
    assert kwargs["to_id"] == "prog1"

def test_process_graph_batch_creates_nodes_and_edges(sample_records):
    driver = mock.MagicMock()
    session = driver.session.return_value.__enter__.return_value
    session.write_transaction = mock.MagicMock()
    # Should not raise
    rg.process_graph_batch(sample_records, driver, batch_num=1)
    # Should upsert 2 nodes (staff, program)
    assert session.write_transaction.call_count >= 2
    # Should upsert at least one relationship (staff COACHES program)
    calls = [c for c in session.write_transaction.call_args_list if c[0][0] == rg.upsert_relationship]
    assert any("COACHES" in str(c) for c in calls)

def test_process_graph_batch_handles_missing_program_ids():
    driver = mock.MagicMock()
    session = driver.session.return_value.__enter__.return_value
    session.write_transaction = mock.MagicMock()
    records = [{
        "doc_id": "staff2",
        "canonical_url": "https://dmeacademy.com/staff/john-smith",
        "entity_type": "staff",
        "text": "Coach John Smith",
        "raw": {},  # No program_ids
    }]
    # Should not raise
    rg.process_graph_batch(records, driver, batch_num=1)
    # Should upsert node, not fail on missing program_ids
    assert session.write_transaction.call_count == 1

def test_get_normalized_records():
    """Test that get_normalized_records fetches and formats records from Postgres."""
    cur = mock.MagicMock()
    cur.fetchall.return_value = [
        ("id1", "url1", "staff", "text1", {"raw": 1}),
        ("id2", "url2", "program", "text2", {"raw": 2}),
    ]
    conn = mock.MagicMock()
    conn.cursor.return_value.__enter__.return_value = cur
    records = rg.get_normalized_records(conn)
    assert len(records) == 2
    assert records[0]["doc_id"] == "id1"
    assert records[1]["entity_type"] == "program"

def test_materialize_adjacency_to_postgres():
    """Test that materialize_adjacency_to_postgres is a no-op (placeholder)."""
    conn = mock.MagicMock()
    rg.materialize_adjacency_to_postgres([], conn)  # Should not raise

def test_process_graph_with_retries_handles_transient_errors(monkeypatch, sample_records):
    driver = mock.MagicMock()
    # Simulate ServiceUnavailable on first batch, then success
    call_count = {"count": 0}
    def flaky_batch(records, driver, batch_num):
        if call_count["count"] == 0:
            call_count["count"] += 1
            raise ServiceUnavailable("Simulated connection drop")
        # Success on retry
    monkeypatch.setattr(rg, "process_graph_batch", flaky_batch)
    # Should not raise, should retry and succeed
    rg.process_graph_with_retries(sample_records, driver)
    assert call_count["count"] == 1

def test_process_graph_with_retries_skips_after_max_retries(monkeypatch, sample_records):
    driver = mock.MagicMock()
    # Always fail
    def always_fail(records, driver, batch_num):
        raise ServiceUnavailable("Simulated persistent failure")
    monkeypatch.setattr(rg, "process_graph_batch", always_fail)
    # Should not raise, should skip after max retries
    rg.process_graph_with_retries(sample_records, driver)

def test_process_graph_batch_enrichment(monkeypatch):
    # Mock Neo4j driver/session/tx
    class DummySession:
        def write_transaction(self, func, *args, **kwargs):
            func_calls.append((func.__name__, args, kwargs))
            return func(*args, **kwargs)
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc_val, exc_tb):
            pass
    class DummyDriver:
        def session(self):
            return DummySession()
    func_calls = []
    # Patch upsert_node and upsert_relationship
    import indexer.relationship_graph as rg
    def named_mock(name):
        m = MagicMock()
        m.__name__ = name
        return m
    monkeypatch.setattr(rg, "upsert_node", named_mock("upsert_node"))
    monkeypatch.setattr(rg, "upsert_relationship", named_mock("upsert_relationship"))
    # Doc with enrichment fields
    doc = {
        "doc_id": "abc123",
        "entity_type": "program",
        "text": "Coach John Smith teaches the Basketball Program starting June 1st.",
        "entities": ["John Smith", "Basketball Program"],
        "relationships": [
            {"subject": "John Smith", "predicate": "teaches", "object": "Basketball Program"}
        ],
        "raw": {}
    }
    rg.process_graph_batch([doc], DummyDriver(), 1)
    # Check that upsert_node and upsert_relationship were called for enrichment
    upsert_node_calls = [call.args for call in rg.upsert_node.call_args_list]
    assert any(
        args[0] == 'Entity' and args[1] == {'doc_id': 'John Smith', 'name': 'John Smith'}
        for args in upsert_node_calls
    ), "upsert_node was not called with expected enrichment entity arguments."
    upsert_relationship_calls = [call.args for call in rg.upsert_relationship.call_args_list]
    assert any(
        args[0] == 'Entity' and args[1] == 'John Smith' and args[2] == 'teaches' and args[3] == 'Entity' and args[4] == 'Basketball Program'
        for args in upsert_relationship_calls
    ), "upsert_relationship was not called with expected enrichment relationship arguments."
