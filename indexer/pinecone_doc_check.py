import os
import pinecone
import argparse

parser = argparse.ArgumentParser()
parser.add_argument('--canonical_url', type=str, help='Canonical URL to check in Pinecone')
parser.add_argument('--namespace', type=str, default=None, help='Pinecone namespace to use')
args = parser.parse_args()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "dme-kb")
NAMESPACE = args.namespace or os.getenv("PINECONE_NAMESPACE", "dme-kb")

# Canonical URLs from S3 docid extract
FIRST_URL = "https://www.gov.uk/sitemaps/sitemap_1.xml"
LAST_URL = "https://dmeacademy.com/about-dme_academy/"

pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

def check_url(url):
    print(f"\nChecking Pinecone for canonical_url: {url}")
    # Query by metadata filter
    results = index.query(
        vector=[0.0]*1536,  # dummy vector, filter only
        top_k=10,
        include_metadata=True,
        filter={"canonical_url": {"$eq": url}},
        namespace=NAMESPACE
    )
    matches = results.get("matches", [])
    print(f"Found {len(matches)} vectors for {url}")
    if matches:
        print("Example metadata:")
        for m in matches[:2]:
            print(m["metadata"])

if args.canonical_url:
    check_url(args.canonical_url)
else:
    check_url(FIRST_URL)
    check_url(LAST_URL) 