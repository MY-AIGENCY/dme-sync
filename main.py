#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import openai
import pinecone
import json
import os
from typing import List, Optional, Dict, Any, Union
from dotenv import load_dotenv
import logging
import time
from datetime import datetime
import hashlib

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# Load environment variables
load_dotenv()

# API keys and configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_ENVIRONMENT = os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "dme-kb")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
TOP_K = int(os.getenv("TOP_K", "5"))

# Check for required API keys
if not OPENAI_API_KEY:
    logging.error("OPENAI_API_KEY environment variable is required")
    raise ValueError("OPENAI_API_KEY environment variable is required")

if not PINECONE_API_KEY:
    logging.error("PINECONE_API_KEY environment variable is required")
    raise ValueError("PINECONE_API_KEY environment variable is required")

# Initialize OpenAI client
openai.api_key = OPENAI_API_KEY
client = openai.OpenAI(api_key=OPENAI_API_KEY)

# Initialize Pinecone
try:
    pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_ENVIRONMENT)
    index = pinecone.Index(PINECONE_INDEX_NAME)
    logging.info(f"Successfully connected to Pinecone index: {PINECONE_INDEX_NAME}")
except Exception as e:
    logging.error(f"Error connecting to Pinecone: {e}")
    raise ValueError(f"Failed to connect to Pinecone: {e}")

# Create FastAPI app
app = FastAPI(
    title="DME Knowledge Base API",
    description="Search API for the DME Academy knowledge base",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class SearchQuery(BaseModel):
    query: str = Field(..., description="The search query")
    top_k: int = Field(5, description="Number of results to return")
    filter: Optional[Dict[str, Any]] = Field(None, description="Optional metadata filters")

class IngestItem(BaseModel):
    title: str
    content: str
    type: str
    url: Optional[str] = None
    date: Optional[str] = None
    categories: Optional[List[int]] = None
    sports: Optional[List[int]] = None
    metadata: Optional[Dict[str, Any]] = None

class SearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    query: str
    processingTimeMs: int

def get_embedding(text, model=EMBEDDING_MODEL):
    """Get embedding for text using OpenAI API"""
    start_time = time.time()
    logging.info(f"Getting embedding for text of length {len(text)}")
    
    # Truncate text if it's too long
    if len(text) > 25000:
        text = text[:25000]
    
    try:
        response = client.embeddings.create(
            input=text,
            model=model
        )
        embedding = response.data[0].embedding
        
        end_time = time.time()
        logging.info(f"Got embedding in {end_time - start_time:.2f} seconds")
        
        return embedding
    except Exception as e:
        logging.error(f"Error getting embedding: {e}")
        raise HTTPException(status_code=500, detail=f"Error getting embedding: {str(e)}")

def ingest_to_pinecone(item: IngestItem):
    """Ingest an item into Pinecone"""
    logging.info(f"Ingesting item: {item.title}")
    
    # Generate a stable ID
    item_dict = item.dict(exclude_none=True)
    item_id = hashlib.md5(json.dumps(item_dict, sort_keys=True).encode()).hexdigest()
    
    # Get embedding
    text_for_embedding = f"Title: {item.title}\n\nContent: {item.content}"
    embedding = get_embedding(text_for_embedding)
    
    # Prepare metadata
    metadata = {
        "title": item.title,
        "type": item.type,
        "url": item.url or "",
        "date": item.date or "",
    }
    
    # Add optional metadata
    if item.metadata:
        metadata.update(item.metadata)
    
    # Upsert to Pinecone
    try:
        index.upsert(
            vectors=[{
                "id": item_id,
                "values": embedding,
                "metadata": metadata
            }]
        )
        logging.info(f"Successfully ingested item {item_id}")
        return {"id": item_id, "status": "success"}
    except Exception as e:
        logging.error(f"Error upserting to Pinecone: {e}")
        raise HTTPException(status_code=500, detail=f"Error upserting to Pinecone: {str(e)}")

@app.post("/ingest", response_model=Dict[str, str])
async def ingest(item: IngestItem, background_tasks: BackgroundTasks):
    """Ingest an item into the knowledge base"""
    background_tasks.add_task(ingest_to_pinecone, item)
    return {"status": "ingestion started"}

@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(5, description="Number of results to return"),
    filter_type: Optional[str] = Query(None, description="Filter by content type"),
):
    """Search the knowledge base"""
    start_time = time.time()
    logging.info(f"Search query: {q}")
    
    # Get embedding for query
    query_embedding = get_embedding(q)
    
    # Prepare filter
    filter_dict = {}
    if filter_type:
        filter_dict["type"] = {"$eq": filter_type}
    
    # Search Pinecone
    try:
        search_results = index.query(
            vector=query_embedding,
            top_k=top_k,
            include_metadata=True,
            filter=filter_dict if filter_dict else None
        )
        
        # Process results
        results = []
        for match in search_results["matches"]:
            results.append({
                "id": match["id"],
                "score": match["score"],
                "metadata": match["metadata"]
            })
        
        end_time = time.time()
        processing_time = int((end_time - start_time) * 1000)  # Convert to milliseconds
        
        return {
            "results": results,
            "query": q,
            "processingTimeMs": processing_time
        }
    except Exception as e:
        logging.error(f"Error searching Pinecone: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching Pinecone: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "DME KB API",
        "connections": {
            "pinecone": "connected",
            "openai": "connected" if OPENAI_API_KEY else "not configured"
        }
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 