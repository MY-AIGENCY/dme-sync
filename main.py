#!/usr/bin/env python3
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Header, Request, Response
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
from fastapi.responses import JSONResponse

# Import the rate limiter
from rate_limit import rate_limit_middleware

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler()
    ]
)

# Debug: Print all environment variables (sanitized)
logging.info("=== Environment Variables (sanitized) ===")
for key in sorted(os.environ.keys()):
    value = os.environ[key]
    # Don't log the actual API keys, just their presence
    if 'key' in key.lower() or 'secret' in key.lower() or 'token' in key.lower() or 'password' in key.lower():
        logging.info(f"{key}: {'*' * min(8, len(value))}")
    else:
        logging.info(f"{key}: {value}")
logging.info("======================================")

# Load environment variables
load_dotenv()

# For Render deployment, also try to load from .env
try:
    if os.path.exists('.env'):
        logging.info("Found .env file, loading variables")
        with open('.env', 'r') as f:
            for line in f:
                if line.strip() and not line.startswith('#'):
                    key, value = line.strip().split('=', 1)
                    os.environ[key] = value
except Exception as e:
    logging.warning(f"Error loading .env file: {e}")

# Check if we're in development mode
DEV_MODE = os.getenv("DEV_MODE", "false").lower() == "true"

# API keys and configuration
# Try multiple formats that Render might use
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY") or os.getenv("PINECONE_API_KEY") or ""
PINECONE_ENVIRONMENT = os.environ.get("PINECONE_ENVIRONMENT") or os.getenv("PINECONE_ENVIRONMENT", "gcp-starter")
PINECONE_INDEX_NAME = os.environ.get("PINECONE_INDEX_NAME") or os.getenv("PINECONE_INDEX_NAME", "dme-kb")
EMBEDDING_MODEL = os.environ.get("EMBEDDING_MODEL") or os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
TOP_K = int(os.environ.get("TOP_K") or os.getenv("TOP_K", "5"))
VAPI_TOKEN = os.environ.get("VAPI_TOKEN") or os.getenv("VAPI_TOKEN") or os.environ.get("VAPI_SECRET_KEY") or os.getenv("VAPI_SECRET_KEY", "")

# Debug: Print available key info
logging.info("=== API Key Debug ===")
logging.info(f"OPENAI_API_KEY present: {OPENAI_API_KEY is not None}")
if OPENAI_API_KEY:
    logging.info(f"OPENAI_API_KEY length: {len(OPENAI_API_KEY)}")
logging.info(f"PINECONE_API_KEY present: {PINECONE_API_KEY is not None}")
if PINECONE_API_KEY:
    logging.info(f"PINECONE_API_KEY length: {len(PINECONE_API_KEY)}")
logging.info(f"PINECONE_ENVIRONMENT: {PINECONE_ENVIRONMENT}")
logging.info(f"PINECONE_INDEX_NAME: {PINECONE_INDEX_NAME}")
logging.info("====================")

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

# Check for API keys and initialize clients
missing_keys = []
openai_client = None
pinecone_index = None

if not OPENAI_API_KEY:
    missing_keys.append("OPENAI_API_KEY")
    logging.warning("OPENAI_API_KEY environment variable is missing. Search and ingestion will be disabled.")
else:
    try:
        openai.api_key = OPENAI_API_KEY
        openai_client = openai.OpenAI(api_key=OPENAI_API_KEY)
        logging.info("OpenAI client initialized successfully")
    except Exception as e:
        logging.error(f"Failed to initialize OpenAI client: {e}")

if not PINECONE_API_KEY:
    missing_keys.append("PINECONE_API_KEY")
    logging.warning("PINECONE_API_KEY environment variable is missing. Search and ingestion will be disabled.")
else:
    try:
        # New Pinecone initialization approach
        pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
        
        # Check if index exists
        index_list = pc.list_indexes()
        logging.info(f"Available Pinecone indexes: {index_list}")
        
        if PINECONE_INDEX_NAME not in index_list.names():
            logging.info(f"Index {PINECONE_INDEX_NAME} does not exist. Creating it now...")
            try:
                # Create the index - use aws us-east-1 for free tier (as per Pinecone's recommendation)
                # The error message indicates this is the only supported region for free accounts now
                pc.create_index(
                    name=PINECONE_INDEX_NAME,
                    dimension=1536,  # For OpenAI's text-embedding-3-small
                    metric='cosine',
                    spec=pinecone.ServerlessSpec(
                        cloud='aws',
                        region='us-east-1'
                    )
                )
                logging.info(f"Successfully created Pinecone index: {PINECONE_INDEX_NAME}")
                
                # Connect to the index
                pinecone_index = pc.Index(PINECONE_INDEX_NAME)
                logging.info(f"Successfully connected to Pinecone index: {PINECONE_INDEX_NAME}")
            except Exception as e:
                logging.error(f"Error creating Pinecone index: {e}")
                # If we can't create an index, we'll need to use an existing one
                logging.info("Cannot create a new index. Please create a Pinecone index manually in AWS us-east-1 region.")
                # Don't use fallback name as it also won't exist
                logging.warning("Vector database functionality will be disabled.")
                # Don't try to connect to an index that doesn't exist
                pinecone_index = None
        else:
            # Connect to existing index
            try:
                pinecone_index = pc.Index(PINECONE_INDEX_NAME)
                logging.info(f"Successfully connected to Pinecone index: {PINECONE_INDEX_NAME}")
            except Exception as e:
                logging.error(f"Error connecting to Pinecone index: {e}")
                logging.warning("Vector database functionality will be disabled.")
                pinecone_index = None
    except Exception as e:
        logging.error(f"Error connecting to Pinecone: {e}")
        logging.info("Pinecone connection failed. Search and ingestion will be disabled.")

# Define data models
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

class VapiToolCall(BaseModel):
    """Model representing a single tool call from Vapi"""
    id: str
    name: str
    arguments: Dict[str, Any]

class VapiToolCallList(BaseModel):
    """Model representing the list of tool calls from Vapi"""
    toolCallList: List[VapiToolCall]

class VapiRequest(BaseModel):
    """Model representing the structure of a Vapi function call request"""
    message: VapiToolCallList

class VapiResponse(BaseModel):
    """Model representing the structure of a response back to Vapi"""
    results: List[Dict[str, Any]]

def get_embedding(text, model=EMBEDDING_MODEL):
    """Get embedding for text using OpenAI API"""
    if not openai_client:
        raise HTTPException(status_code=503, detail="OpenAI client not initialized. Check environment variables.")
    
    start_time = time.time()
    logging.info(f"Getting embedding for text of length {len(text)}")
    
    # Truncate text if it's too long
    if len(text) > 25000:
        text = text[:25000]
    
    try:
        response = openai_client.embeddings.create(
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
    if not pinecone_index:
        raise HTTPException(status_code=503, detail="Pinecone client not initialized. Check environment variables.")
    
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
        pinecone_index.upsert(
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
    if not openai_client or not pinecone_index:
        raise HTTPException(status_code=503, 
                           detail="API not fully functional. Missing required API keys: " + ", ".join(missing_keys))
    
    background_tasks.add_task(ingest_to_pinecone, item)
    return {"status": "ingestion started"}

@app.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., description="Search query"),
    top_k: int = Query(5, description="Number of results to return"),
    filter_type: Optional[str] = Query(None, description="Filter by content type"),
):
    """Search the knowledge base"""
    try:
        return await search_kb(q, top_k, filter_type)
    except Exception as e:
        logging.error(f"Error in search endpoint: {e}")
        raise HTTPException(status_code=500, detail=f"Error searching knowledge base: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    status = "healthy"
    if missing_keys:
        status = "degraded"
    
    return {
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "service": "DME KB API",
        "connections": {
            "pinecone": "connected" if pinecone_index else "not configured",
            "openai": "connected" if openai_client else "not configured"
        },
        "missing_env_vars": missing_keys if missing_keys else []
    }

@app.get("/")
@app.head("/")  # Add support for HEAD requests
async def root():
    """Root endpoint with API information"""
    return {
        "api": "DME Knowledge Base API",
        "version": "1.0.0",
        "status": "degraded" if missing_keys else "healthy",
        "documentation": "/docs",
        "health": "/health"
    }

@app.post("/vapi-search")
async def vapi_search(
    request: Request,
    vapi_request: VapiRequest, 
    authorization: Optional[str] = Header(None),
    x_vapi_version: Optional[str] = Header(None)
):
    """
    Handle search requests from Vapi.ai
    
    This endpoint accepts POST requests from Vapi.ai's function calling system,
    extracts the search query, forwards it to our search functionality,
    and returns the results in Vapi's expected format.
    """
    # Apply rate limiting
    await rate_limit_middleware(request)
    
    # Set rate limit headers in response if available
    response = Response()
    if hasattr(request.state, "rate_limit_headers"):
        for header, value in request.state.rate_limit_headers.items():
            response.headers[header] = value
    
    # Log Vapi version if provided (for tracking API changes)
    if x_vapi_version:
        logging.info(f"Received request with Vapi version: {x_vapi_version}")
    
    # Verify the auth token if defined in environment
    if VAPI_TOKEN:
        expected_auth = f"Bearer {VAPI_TOKEN}"
        if not authorization or authorization != expected_auth:
            logging.warning("Unauthorized Vapi request: Invalid or missing authorization header")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "unauthorized",
                    "hint": "Authorization header with Bearer token required"
                },
                headers=response.headers
            )
    
    logging.info("Received authorized Vapi search request")
    
    try:
        # Extract tool call information from the request
        if not hasattr(vapi_request.message, "toolCallList") or not vapi_request.message.toolCallList:
            raise ValueError("Missing toolCallList in request")
        
        # Get the first tool call
        tool_call = vapi_request.message.toolCallList[0]
        tool_call_id = tool_call.id
        
        # Extract search parameters
        search_query = tool_call.arguments.get("query") or tool_call.arguments.get("q", "")
        top_k = tool_call.arguments.get("top_k", TOP_K)
        filter_type = tool_call.arguments.get("filter_type")
        
        if not search_query:
            raise ValueError("Missing required parameter: query or q")
        
        # Log the parsed request for debugging
        logging.info(f"Vapi tool call - id: {tool_call_id}, query: {search_query}, top_k: {top_k}")
        
        start_time = time.time()
        
        # Call the internal search function
        search_response = await search_kb(search_query, top_k, filter_type)
        
        end_time = time.time()
        processing_time = int((end_time - start_time) * 1000)  # Convert to milliseconds
        
        # Format the response following Vapi's requirements
        vapi_response = {
            "results": [
                {
                    "toolCallId": tool_call_id,
                    "result": json.dumps(search_response)
                }
            ]
        }
        
        logging.info(f"Completed Vapi search request in {processing_time}ms with {len(search_response['results'])} results")
        return vapi_response
        
    except ValueError as e:
        # Client error (bad request format)
        logging.warning(f"Invalid Vapi request: {str(e)}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "unsupported_payload",
                "hint": str(e)
            },
            headers=response.headers
        )
    except Exception as e:
        # Server error
        logging.error(f"Error processing Vapi request: {e}")
        return JSONResponse(
            status_code=500, 
            content={
                "error": "internal_error",
                "hint": "An unexpected error occurred while processing the request"
            },
            headers=response.headers
        )

# Internal search function (decoupled from HTTP transport)
async def search_kb(
    query: str,
    top_k: int = TOP_K,
    filter_type: Optional[str] = None
) -> Dict[str, Any]:
    """Internal search function that can be called by different endpoints"""
    if not openai_client or not pinecone_index:
        raise HTTPException(status_code=503, 
                           detail="API not fully functional. Missing required API keys: " + ", ".join(missing_keys))
    
    start_time = time.time()
    logging.info(f"Search query: {query}")
    
    # Get embedding for query
    query_embedding = get_embedding(query)
    
    # Prepare filter
    filter_dict = {}
    if filter_type:
        filter_dict["type"] = {"$eq": filter_type}
    
    # Search Pinecone
    search_results = pinecone_index.query(
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
        "query": query,
        "processingTimeMs": processing_time
    }

if __name__ == "__main__":
    import uvicorn
    
    # Print warning if keys are missing
    if missing_keys:
        logging.warning(f"Running with limited functionality. Missing environment variables: {', '.join(missing_keys)}")
    
    uvicorn.run(app, host="0.0.0.0", port=8000) 