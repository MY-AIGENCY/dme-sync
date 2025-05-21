import os
from typing import Dict, Any
import spacy
import openai
from .schema_inference import infer_schema_from_samples
import re

# Load spaCy model (en_core_web_trf is best-in-class for English NER)
NLP = spacy.load("en_core_web_trf")

# OpenAI API setup
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY


def extract_entities_spacy(text: str):
    doc = NLP(text)
    return list(set(ent.text for ent in doc.ents if ent.label_ not in ("CARDINAL", "ORDINAL", "PERCENT", "MONEY", "QUANTITY", "TIME", "DATE")))


def extract_relationships_openai(text: str, entities: list) -> list:
    """
    Use OpenAI GPT-4o to extract relationships as subject-predicate-object triples.
    Compatible with openai>=1.0.0 API. Forces valid JSON output.
    """
    prompt = (
        "Extract all subject-predicate-object relationships from the following text. "
        "Use only the entities provided if possible. Return ONLY a JSON list of triples with keys 'subject', 'predicate', 'object'. "
        "Do not include any explanation or extra text.\n"
        f"Entities: {entities}\nText: {text}"
    )
    try:
        response = openai.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert information extraction system. Only output valid JSON."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=256,
            temperature=0.0
        )
        import json
        content = response.choices[0].message.content.strip()
        # Try to extract the first JSON list from the response
        match = re.search(r'(\[.*?\])', content, re.DOTALL)
        if match:
            json_str = match.group(1)
            triples = json.loads(json_str)
            if isinstance(triples, list):
                return triples
        else:
            print(f"[WARN] No JSON list found in OpenAI response: {content}")
    except Exception as e:
        print(f"[WARN] OpenAI relationship extraction failed: {e} | Raw response: {locals().get('content', '')}")
    return []


def extract_entities_and_relationships(doc: Dict[str, Any], schema: Dict[str, Any]) -> Dict[str, Any]:
    text = doc.get("text", "")
    # 1. Entity extraction (spaCy)
    entities = extract_entities_spacy(text)
    # 2. Relationship extraction (OpenAI)
    relationships = extract_relationships_openai(text, entities)
    # 3. Metadata (demo: extract first date found by spaCy)
    spacy_doc = NLP(text)
    date = next((ent.text for ent in spacy_doc.ents if ent.label_ == "DATE"), None)
    metadata = {"date": date} if date else {}
    return {
        "entities": entities,
        "relationships": relationships,
        "metadata": metadata
    }

# Timing/estimation utility
import time

def estimate_enrichment_runtime(num_docs: int, avg_chars: int = 2000) -> float:
    """
    Estimate total runtime in seconds for enrichment across the dataset.
    - spaCy NER: ~0.2s/doc (en_core_web_trf, GPU), ~0.5s/doc (CPU)
    - OpenAI GPT-4o: ~1.5s/doc (API call, parallelizable)
    """
    spacy_time = num_docs * 0.5  # conservative CPU estimate
    openai_time = num_docs * 1.5
    total = spacy_time + openai_time
    return total

if __name__ == "__main__":
    sample_doc = {"text": "Coach John Smith teaches the Basketball Program starting June 1st."}
    schema = infer_schema_from_samples([sample_doc])
    enrichment = extract_entities_and_relationships(sample_doc, schema)
    print("Enrichment:", enrichment)
    # Example timing estimate
    n = 1000
    print(f"Estimated time for {n} docs: {estimate_enrichment_runtime(n)/60:.1f} minutes") 