#!/usr/bin/env python3
import json
import os
import time
from datetime import datetime
import openai
import pinecone
import hashlib
from tqdm import tqdm
import re
from dotenv import load_dotenv
import html

# Load environment variables
load_dotenv()

# API keys and configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "dme-kb")
TYPESENSE_API_KEY = os.getenv("TYPESENSE_API_KEY")
TYPESENSE_HOST = os.getenv("TYPESENSE_HOST", "localhost")
TYPESENSE_PORT = os.getenv("TYPESENSE_PORT", "8108")
TYPESENSE_PROTOCOL = os.getenv("TYPESENSE_PROTOCOL", "http")
TYPESENSE_COLLECTION = os.getenv("TYPESENSE_COLLECTION", "dme-kb")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
EMBEDDING_DIMENSION = 1536  # Dimension for text-embedding-3-small

# Flag to determine if Typesense is available
USE_TYPESENSE = TYPESENSE_API_KEY is not None and TYPESENSE_API_KEY.strip() != ""

# Initialize OpenAI client
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required")
openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Initialize Pinecone
if not PINECONE_API_KEY:
    raise ValueError("PINECONE_API_KEY environment variable is required")

# Use the new Pinecone initialization
pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
print(f"Pinecone client initialized successfully with environment: {PINECONE_ENVIRONMENT}")

# Initialize Typesense only if API key is available
typesense_client = None
if USE_TYPESENSE:
    try:
        import typesense
        typesense_client = typesense.Client({
            'api_key': TYPESENSE_API_KEY,
            'nodes': [{
                'host': TYPESENSE_HOST,
                'port': TYPESENSE_PORT,
                'protocol': TYPESENSE_PROTOCOL
            }],
            'connection_timeout_seconds': 10
        })
        print("Typesense client initialized successfully.")
    except ImportError:
        print("Typesense package not installed. Skipping Typesense integration.")
        USE_TYPESENSE = False
    except Exception as e:
        print(f"Error initializing Typesense client: {e}")
        USE_TYPESENSE = False
else:
    print("TYPESENSE_API_KEY not provided. Skipping Typesense integration.")

def clean_html(html_text):
    """Remove HTML tags and decode entities"""
    # Remove HTML tags
    text = re.sub(r'<[^>]*>', ' ', html_text)
    # Decode HTML entities
    text = html.unescape(text)
    # Replace multiple spaces with a single space
    text = re.sub(r'\s+', ' ', text)
    return text.strip()

def create_typesense_collection():
    """Create or recreate the Typesense collection"""
    if not USE_TYPESENSE:
        return
    
    # Check if collection exists and delete it
    try:
        typesense_client.collections[TYPESENSE_COLLECTION].delete()
        print(f"Deleted existing Typesense collection: {TYPESENSE_COLLECTION}")
    except Exception:
        print(f"No existing collection to delete: {TYPESENSE_COLLECTION}")

    # Create collection
    collection_schema = {
        'name': TYPESENSE_COLLECTION,
        'fields': [
            {'name': 'id', 'type': 'string'},
            {'name': 'original_id', 'type': 'int32'},
            {'name': 'type', 'type': 'string', 'facet': True},
            {'name': 'title', 'type': 'string'},
            {'name': 'clean_content', 'type': 'string'},
            {'name': 'url', 'type': 'string'},
            {'name': 'date', 'type': 'string', 'facet': True},
            {'name': 'categories', 'type': 'int32[]', 'facet': True},
            {'name': 'sports', 'type': 'int32[]', 'facet': True},
            {'name': 'embedding', 'type': 'float[]', 'num_dim': EMBEDDING_DIMENSION},
        ]
    }
    
    typesense_client.collections.create(collection_schema)
    print(f"Created Typesense collection: {TYPESENSE_COLLECTION}")

def ensure_pinecone_index():
    """Ensure Pinecone index exists"""
    # List all indexes
    index_list = pc.list_indexes()
    print(f"Available Pinecone indexes: {index_list}")
    
    # Check if index exists
    if PINECONE_INDEX_NAME not in index_list.names():
        # Create index
        try:
            pc.create_index(
                name=PINECONE_INDEX_NAME,
                dimension=EMBEDDING_DIMENSION,
                metric="cosine",
                spec=pinecone.ServerlessSpec(
                    cloud='aws',
                    region='us-east-1'
                )
            )
            print(f"Created Pinecone index: {PINECONE_INDEX_NAME}")
        except Exception as e:
            print(f"Error creating Pinecone index: {e}")
            print(f"Attempting to use existing index if available.")
    else:
        print(f"Pinecone index already exists: {PINECONE_INDEX_NAME}")
    
    # Connect to index
    return pc.Index(PINECONE_INDEX_NAME)

def get_embedding(text, model=EMBEDDING_MODEL):
    """Get embedding for text using OpenAI API"""
    # Truncate text if it's too long (OpenAI has token limits)
    if len(text) > 25000:
        text = text[:25000]
    
    try:
        response = client.embeddings.create(
            input=text,
            model=model
        )
        return response.data[0].embedding
    except Exception as e:
        print(f"Error getting embedding: {e}")
        # Return a zero vector in case of error
        return [0.0] * EMBEDDING_DIMENSION

def process_kb_items():
    """Process KB items, create embeddings, and upsert to Pinecone and Typesense"""
    print(f"[{datetime.now()}] Starting embedding and upsert process...")
    
    # Load KB items
    with open("master_kb.json", "r") as f:
        kb_items = json.load(f)
    
    print(f"Loaded {len(kb_items)} items from master_kb.json")
    
    # Ensure Pinecone index exists
    pinecone_index = ensure_pinecone_index()
    
    # Create Typesense collection if enabled
    if USE_TYPESENSE:
        create_typesense_collection()
    
    # Process items in batches
    batch_size = 100
    pinecone_vectors = []
    typesense_documents = []
    
    for i, item in enumerate(tqdm(kb_items, desc="Processing items")):
        # Extract and clean text for embedding
        title = item.get("title", "")
        content = item.get("content", "")
        
        # Clean HTML from content
        clean_content = clean_html(content)
        
        # Create text for embedding
        text_for_embedding = f"Title: {title}\n\nContent: {clean_content}"
        
        # Get embedding
        embedding = get_embedding(text_for_embedding)
        
        # Prepare Pinecone vector
        pinecone_vector = {
            "id": item["id"],
            "values": embedding,
            "metadata": {
                "original_id": item["original_id"],
                "type": item["type"],
                "title": title,
                "url": item.get("url", ""),
                "date": item.get("date", ""),
            }
        }
        pinecone_vectors.append(pinecone_vector)
        
        # Prepare Typesense document if enabled
        if USE_TYPESENSE:
            typesense_document = {
                "id": item["id"],
                "original_id": item["original_id"],
                "type": item["type"],
                "title": title,
                "clean_content": clean_content[:65000],  # Typesense may have size limits
                "url": item.get("url", ""),
                "date": item.get("date", ""),
                "categories": item.get("categories", []),
                "sports": item.get("sports", []),
                "embedding": embedding
            }
            typesense_documents.append(typesense_document)
        
        # Upsert in batches
        if len(pinecone_vectors) >= batch_size or i == len(kb_items) - 1:
            # Upsert to Pinecone
            try:
                pinecone_index.upsert(vectors=pinecone_vectors)
                print(f"Upserted {len(pinecone_vectors)} vectors to Pinecone")
            except Exception as e:
                print(f"Error upserting to Pinecone: {e}")
            
            # Upsert to Typesense if enabled
            if USE_TYPESENSE and typesense_documents:
                try:
                    # Import documents in chunks to avoid payload size issues
                    chunk_size = 20
                    for j in range(0, len(typesense_documents), chunk_size):
                        chunk = typesense_documents[j:j+chunk_size]
                        typesense_client.collections[TYPESENSE_COLLECTION].documents.import_(chunk)
                    print(f"Upserted {len(typesense_documents)} documents to Typesense")
                except Exception as e:
                    print(f"Error upserting to Typesense: {e}")
            
            # Clear batches
            pinecone_vectors = []
            typesense_documents = []
            
            # Small delay to avoid rate limits
            time.sleep(0.5)
    
    print(f"[{datetime.now()}] Embedding and upsert process complete!")

def test_search(query, limit=5):
    """Test search functionality"""
    print(f"\nTesting search for: '{query}'")
    
    # Get embedding for query
    query_embedding = get_embedding(query)
    
    # Search Pinecone
    pinecone_index = pc.Index(PINECONE_INDEX_NAME)
    pinecone_results = pinecone_index.query(
        vector=query_embedding,
        top_k=limit,
        include_metadata=True
    )
    
    print("\nPinecone Results:")
    for match in pinecone_results["matches"]:
        print(f"  - Score: {match['score']:.4f}")
        print(f"    Title: {match['metadata']['title']}")
        print(f"    Type: {match['metadata']['type']}")
        print(f"    URL: {match['metadata']['url']}")
        print()
    
    # Search Typesense if enabled
    if USE_TYPESENSE:
        try:
            search_parameters = {
                'q': query,
                'query_by': 'title, clean_content',
                'per_page': limit
            }
            typesense_results = typesense_client.collections[TYPESENSE_COLLECTION].documents.search(search_parameters)
            
            print("Typesense Results:")
            for hit in typesense_results["hits"]:
                print(f"  - Score: {hit['text_match']:.4f}")
                print(f"    Title: {hit['document']['title']}")
                print(f"    Type: {hit['document']['type']}")
                print(f"    URL: {hit['document']['url']}")
                print()
        except Exception as e:
            print(f"Error searching Typesense: {e}")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Embed KB items and upsert to Pinecone and Typesense")
    parser.add_argument("--test", help="Test search with the given query")
    
    args = parser.parse_args()
    
    if args.test:
        test_search(args.test)
    else:
        process_kb_items() 