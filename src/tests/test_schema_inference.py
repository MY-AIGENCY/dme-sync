import pytest
from processor.schema_inference import infer_schema_from_samples

def test_infer_schema_from_samples():
    samples = [
        {"text": "Coach John Smith teaches the Basketball Program starting June 1st."},
        {"text": "The Summer Camp is organized by DME Academy."}
    ]
    schema = infer_schema_from_samples(samples)
    assert isinstance(schema, dict)
    assert "entities" in schema
    assert "relationships" in schema
    assert "attributes" in schema
    assert isinstance(schema["entities"], list)
    assert isinstance(schema["relationships"], list)
    assert isinstance(schema["attributes"], list) 