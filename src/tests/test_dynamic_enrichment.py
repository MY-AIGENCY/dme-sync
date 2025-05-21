import pytest
from processor.dynamic_enrichment import extract_entities_and_relationships
from processor.schema_inference import infer_schema_from_samples

def test_extract_entities_and_relationships():
    sample_doc = {"text": "Coach John Smith teaches the Basketball Program starting June 1st."}
    schema = infer_schema_from_samples([sample_doc])
    enrichment = extract_entities_and_relationships(sample_doc, schema)
    assert isinstance(enrichment, dict)
    assert "entities" in enrichment
    assert "relationships" in enrichment
    assert "metadata" in enrichment
    assert isinstance(enrichment["entities"], list)
    assert isinstance(enrichment["relationships"], list)
    assert isinstance(enrichment["metadata"], dict) 