import boto3
import os
import json

BUCKET = os.getenv("S3_BUCKET_NAME", "raw-site-data")
FIRST_KEY = "raw/43a2972d9f30f52415e76676c8a7e0ff2f21ace755d954eab241257e3cfd0ba7.json"
LAST_KEY = "raw/wp_pages_78_5a80a20bbf38a1f20ab26e9a5bad4c58dbbfa31e1618c8c45efe1ba29930d6c8.json"

s3 = boto3.client("s3")

def extract_doc_id_and_url(key):
    obj = s3.get_object(Bucket=BUCKET, Key=key)
    data = json.loads(obj["Body"].read())
    doc_id = data.get("doc_id") or data.get("id")
    canonical_url = data.get("canonical_url") or data.get("url")
    # Try to extract from 'raw' if missing
    if not doc_id and "raw" in data and isinstance(data["raw"], dict):
        doc_id = data["raw"].get("id")
        canonical_url = data["raw"].get("link") or data["raw"].get("url")
    print(f"{key}: doc_id = {doc_id}, canonical_url = {canonical_url}")
    return doc_id, canonical_url

first_doc_id, first_url = extract_doc_id_and_url(FIRST_KEY)
last_doc_id, last_url = extract_doc_id_and_url(LAST_KEY) 