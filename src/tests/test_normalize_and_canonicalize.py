import os
import json
import shutil
import tempfile
import pytest
from unittest import mock
from processor import normalize_and_canonicalize as nc

@pytest.fixture
def sample_raw_page():
    return {
        "url": "https://dmeacademy.com/programs/basketball",
        "html": "<html><head><title>Basketball</title></head><body>Program info</body></html>",
        "scraped_at": "2024-06-01T12:00:00Z",
        "etag": "abc123",
        "checksum": "def456"
    }

def test_sha256_of_url():
    url = "https://example.com/page"
    result = nc.sha256_of_url(url)
    assert isinstance(result, str) and len(result) == 64

def test_clean_text():
    dirty = "This   is\n\t a   test."
    assert nc.clean_text(dirty) == "This is a test."

def test_detect_entity_type_url(sample_raw_page):
    url = sample_raw_page["url"]
    html = sample_raw_page["html"]
    assert nc.detect_entity_type(url, html) == "program"

def test_detect_entity_type_html():
    url = "https://dmeacademy.com/other"
    html = "<div itemscope itemtype=\"schema.org/Event\"></div>"
    assert nc.detect_entity_type(url, html) == "event"

def test_validate_schema_valid(sample_raw_page):
    doc = {
        "doc_id": "abc",
        "canonical_url": sample_raw_page["url"],
        "entity_type": "program",
        "text": "Program info",
        "raw": sample_raw_page,
    }
    assert nc.validate_schema(doc) is None

def test_validate_schema_invalid(sample_raw_page):
    doc = {
        "doc_id": "abc",
        # missing canonical_url
        "entity_type": "program",
        "text": "Program info",
        "raw": sample_raw_page,
    }
    err = nc.validate_schema(doc)
    assert err is not None

def test_quarantine_failure(tmp_path, sample_raw_page):
    doc = {
        "doc_id": "abc",
        "canonical_url": sample_raw_page["url"],
        "entity_type": "program",
        "text": "Program info",
        "raw": sample_raw_page,
    }
    reason = "schema error"
    quarantine_dir = tmp_path / "quarantine"
    nc.quarantine_failure(doc, reason, str(quarantine_dir))
    files = list(quarantine_dir.iterdir())
    assert any(f.name == "abc.json" for f in files)
    with open(quarantine_dir / "abc.json") as f:
        data = json.load(f)
        assert data["reason"] == reason

def test_persist_to_postgres():
    doc = {
        "doc_id": "abc",
        "canonical_url": "https://dmeacademy.com/programs/basketball",
        "entity_type": "program",
        "text": "Program info",
        "raw": {"foo": "bar"},
    }
    mock_conn = mock.MagicMock()
    nc.persist_to_postgres(doc, mock_conn)
    mock_conn.cursor().__enter__().execute.assert_called()
    mock_conn.commit.assert_called()

def test_process_raw_page_valid(monkeypatch, sample_raw_page):
    doc_id = nc.sha256_of_url(sample_raw_page["url"])
    calls = {}
    def fake_persist(doc, conn):
        calls["persisted"] = doc["doc_id"]
    monkeypatch.setattr(nc, "persist_to_postgres", fake_persist)
    monkeypatch.setattr(nc, "validate_schema", lambda doc: None)
    nc.process_raw_page(sample_raw_page, mock.MagicMock())
    assert calls["persisted"] == doc_id

def test_process_raw_page_invalid(monkeypatch, sample_raw_page, tmp_path):
    calls = {}
    def fake_quarantine(doc, reason, quarantine_dir="quarantine"):
        calls["quarantined"] = doc["doc_id"]
    monkeypatch.setattr(nc, "persist_to_postgres", lambda doc, conn: None)
    monkeypatch.setattr(nc, "validate_schema", lambda doc: "fail")
    monkeypatch.setattr(nc, "quarantine_failure", fake_quarantine)
    nc.process_raw_page(sample_raw_page, mock.MagicMock())
    assert calls["quarantined"] == nc.sha256_of_url(sample_raw_page["url"]) 