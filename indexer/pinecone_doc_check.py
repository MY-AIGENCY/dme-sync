import os
import pinecone
import argparse
import openai
from dotenv import load_dotenv

parser = argparse.ArgumentParser()
group = parser.add_mutually_exclusive_group()
group.add_argument('--canonical_url', type=str, help='Canonical URL to check in Pinecone')
group.add_argument('--query', type=str, help='Natural language query to search Pinecone')
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

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")

openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

def embed_query(query):
    response = client.embeddings.create(input=query, model=EMBEDDING_MODEL)
    return response.data[0].embedding

def search_by_natural_language(query, top_k=5):
    print(f"\nSearching Pinecone for: '{query}' (top_k={top_k})")
    embedding = embed_query(query)
    results = index.query(
        vector=embedding,
        top_k=top_k,
        include_metadata=True,
        namespace=NAMESPACE
    )
    matches = results.get("matches", [])
    print(f"Found {len(matches)} matches for query: '{query}'")
    for i, m in enumerate(matches):
        print(f"\nResult {i+1}:")
        print(f"  Score: {m['score']:.4f}")
        print(f"  Canonical URL: {m['metadata'].get('canonical_url')}")
        print(f"  Entity Type: {m['metadata'].get('entity_type')}")
        # Print a snippet of the text if available
        text = m['metadata'].get('text')
        if text:
            print(f"  Text Snippet: {text[:200]}{'...' if len(text) > 200 else ''}")
        else:
            print("  No text snippet available.")

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

if __name__ == "__main__":
    if args.canonical_url:
        check_url(args.canonical_url)
    elif args.query:
        search_by_natural_language(args.query)
    else:
        check_url(FIRST_URL)
        check_url(LAST_URL)
    print("\nUsage for natural language search:")
    print("  poetry run python indexer/pinecone_doc_check.py --query 'your question here'") 