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

class VapiFunctionCall(BaseModel):
    """Model representing a function call from Vapi"""
    name: str
    parameters: Union[str, Dict[str, Any]]
    id: Optional[str] = None

class VapiMessage(BaseModel):
    """Model representing Vapi's standardized message format"""
    type: str
    functionCall: Optional[VapiFunctionCall] = None

class VapiRequest(BaseModel):
    """Model representing a request from Vapi"""
    message: VapiMessage

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
async def vapi_search(request: Request):
    """
    Handle search requests from Vapi.ai using the Server-Events format
    
    Accepts POST requests from Vapi.ai's function calling system according to docs:
    {
      "message": {
        "type": "function-call",
        "functionCall": {
          "name": "knowledge_search",
          "parameters": "{ \"q\": \"query string\" }"
        }
      }
    }
    """
    # Verify auth token
    auth = request.headers.get("authorization")
    if VAPI_TOKEN and (not auth or auth != f"Bearer {VAPI_TOKEN}"):
        logging.warning("Unauthorized Vapi request: Invalid or missing authorization header")
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # Parse request body
        body = await request.json()
        
        # Log request details in dev mode
        if DEV_MODE:
            logging.info(f"Received Vapi request: {json.dumps(body)[:1000]}")
        
        # Parse using Pydantic model
        try:
            vapi_req = VapiRequest.parse_obj(body)
            msg = vapi_req.message
        except Exception as e:
            logging.warning(f"Failed to parse request using Pydantic model: {str(e)}")
            # Fallback to direct dictionary access if parsing fails
            if "message" not in body:
                logging.warning("Invalid request format: missing 'message' field")
                raise HTTPException(status_code=400, detail="Invalid request format")
                
            msg = body["message"]
            
        # Handle only function-call message types
        if msg.type != "function-call" or not msg.functionCall:
            logging.info("Ignoring non-function-call event")
            return {}  # Ignore non-function events
        
        # Handle only knowledge_search function calls
        if msg.functionCall.name != "knowledge_search":
            logging.warning(f"Unknown function: {msg.functionCall.name}")
            return {"result": f"Unknown function {msg.functionCall.name}"}
        
        # Extract parameters
        params = {}
        if hasattr(msg.functionCall, "parameters") and msg.functionCall.parameters is not None:
            # Handle if parameters is a string
            if isinstance(msg.functionCall.parameters, str):
                try:
                    params = json.loads(msg.functionCall.parameters)
                except json.JSONDecodeError:
                    logging.error(f"Invalid JSON in parameters: {msg.functionCall.parameters}")
                    return {"result": "Invalid parameters format"}
            else:
                params = msg.functionCall.parameters
        
        # Extract query
        q = params.get("q")
        # If params has a nested structure with arguments that contain q
        if not q and isinstance(params, dict) and "arguments" in params:
            if isinstance(params["arguments"], dict):
                q = params["arguments"].get("q")
            elif isinstance(params["arguments"], str):
                try:
                    arg_dict = json.loads(params["arguments"])
                    q = arg_dict.get("q")
                except json.JSONDecodeError:
                    pass
        
        if not q:
            logging.warning("Missing required parameter: q")
            return {"result": "Missing q parameter"}
        
        # Get optional parameters
        top_k = params.get("top_k", 3)
        filter_type = params.get("filter_type", None)
        
        # Call the search function
        logging.info(f"Searching for query: {q}, top_k: {top_k}")
        result = await search_kb(q, top_k=top_k, filter_type=filter_type)
        
        # Format the response according to Vapi's documented format
        logging.info(f"Search complete, found {len(result.get('results', []))} results")
        return {"result": result.get("results", [])}
        
    except Exception as e:
        logging.error(f"Error processing Vapi request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

@app.post("/search")
async def search_adapter(request: Request):
    """
    Adapter endpoint for Vapi requests that are sent to /search
    instead of the configured /vapi-search endpoint.
    
    This uses Vapi's standardized format as documented:
    {
      "message": {
        "type": "function-call",
        "functionCall": {
          "name": "knowledge_search",
          "parameters": "{ \"q\": \"query string\" }"
        }
      }
    }
    """
    logging.info("Received request to /search endpoint (Vapi adapter)")
    
    # Verify auth token
    auth = request.headers.get("authorization")
    if VAPI_TOKEN and (not auth or auth != f"Bearer {VAPI_TOKEN}"):
        logging.warning("Unauthorized Vapi request: Invalid or missing authorization header")
        raise HTTPException(status_code=401, detail="Unauthorized")
    
    try:
        # Get raw body content for detailed logging if in dev mode
        if DEV_MODE:
            body_raw = await request.body()
            body_text = body_raw.decode('utf-8')
            logging.info(f"Raw request body to /search: {body_text[:1000]}")
        
        # Parse and process the request
        body = await request.json()
        
        # Parse using Pydantic model
        try:
            vapi_req = VapiRequest.parse_obj(body)
            msg = vapi_req.message
        except Exception as e:
            logging.warning(f"Failed to parse request using Pydantic model: {str(e)}")
            # Fallback to direct dictionary access
            if "message" not in body:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "invalid_request",
                        "hint": "Request must include a 'message' field"
                    }
                )
            
            msg = body["message"]
            if not isinstance(msg, dict):
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "invalid_message",
                        "hint": "Message must be an object"
                    }
                )
            
            # Try to extract query from various formats regardless of message type
            query = None
            
            # First check if we have a standard function-call format
            if msg.get("type") == "function-call" and "functionCall" in msg:
                function_call = msg["functionCall"]
                if function_call.get("name") == "knowledge_search":
                    params = function_call.get("parameters", {})
                    if isinstance(params, str):
                        try:
                            params = json.loads(params)
                        except json.JSONDecodeError:
                            return JSONResponse(
                                status_code=400,
                                content={
                                    "error": "invalid_parameters",
                                    "hint": "Parameters must be valid JSON"
                                }
                            )
                    query = params.get("q")
            
            # If standard format didn't yield a query, try alternative formats
            if not query:
                # Extract from toolCalls array (OpenAI format)
                if "toolCalls" in msg and msg["toolCalls"]:
                    tool_call = msg["toolCalls"][0]
                    if "function" in tool_call and "arguments" in tool_call["function"]:
                        args = tool_call["function"]["arguments"]
                        if isinstance(args, dict):
                            query = args.get("q") or args.get("query")
                        elif isinstance(args, str):
                            try:
                                json_args = json.loads(args)
                                query = json_args.get("q") or json_args.get("query")
                            except json.JSONDecodeError:
                                pass
                
                # Extract from toolCallList (older Vapi format)
                if not query and "toolCallList" in msg and msg["toolCallList"]:
                    tool_call = msg["toolCallList"][0]
                    if "function" in tool_call and "arguments" in tool_call["function"]:
                        args = tool_call["function"]["arguments"]
                        if isinstance(args, dict):
                            query = args.get("q") or args.get("query")
                        elif isinstance(args, str):
                            try:
                                json_args = json.loads(args)
                                query = json_args.get("q") or json_args.get("query")
                            except json.JSONDecodeError:
                                pass
                
                # Extract from toolWithToolCallList (another format)
                if not query and "toolWithToolCallList" in msg and msg["toolWithToolCallList"]:
                    tool_with_call = msg["toolWithToolCallList"][0]
                    if "toolCall" in tool_with_call:
                        tool_call = tool_with_call["toolCall"]
                        if "function" in tool_call and "arguments" in tool_call["function"]:
                            args = tool_call["function"]["arguments"]
                            if isinstance(args, dict):
                                query = args.get("q") or args.get("query")
                            elif isinstance(args, str):
                                try:
                                    json_args = json.loads(args)
                                    query = json_args.get("q") or json_args.get("query")
                                except json.JSONDecodeError:
                                    pass
                
                if query:
                    logging.warning("Found query using legacy format fallback")
                    result = await search_kb(query, top_k=5)
                    return {"result": result.get("results", [])}
                    
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "unsupported_format", 
                        "hint": "Expected message.type to be 'function-call'"
                    }
                )
                
            # If we get here, we have a message with type function-call but not in the Pydantic model format
            if "functionCall" not in msg:
                return JSONResponse(
                    status_code=400,
                    content={
                        "error": "missing_function_call",
                        "hint": "Request must include a functionCall field"
                    }
                )
            
            # Extract params from non-Pydantic format
            function_call = msg["functionCall"]
            if function_call.get("name") != "knowledge_search":
                return {"result": f"Unknown function {function_call.get('name')}"}
                
            params = function_call.get("parameters", {})
            if isinstance(params, str):
                try:
                    params = json.loads(params)
                except json.JSONDecodeError:
                    return JSONResponse(
                        status_code=400,
                        content={
                            "error": "invalid_parameters",
                            "hint": "Parameters must be valid JSON"
                        }
                    )
            query = params.get("q")
            
            # If params has a nested structure with arguments that contain q
            if not query and isinstance(params, dict) and "arguments" in params:
                if isinstance(params["arguments"], dict):
                    query = params["arguments"].get("q")
                elif isinstance(params["arguments"], str):
                    try:
                        arg_dict = json.loads(params["arguments"])
                        query = arg_dict.get("q")
                    except json.JSONDecodeError:
                        pass
        else:
            # Successfully parsed using Pydantic model
            # Extract parameters from standard format
            params = {}
            if msg.functionCall and msg.functionCall.parameters:
                if isinstance(msg.functionCall.parameters, str):
                    try:
                        params = json.loads(msg.functionCall.parameters)
                    except json.JSONDecodeError:
                        return JSONResponse(
                            status_code=400,
                            content={
                                "error": "invalid_parameters",
                                "hint": "Parameters must be valid JSON"
                            }
                        )
                else:
                    params = msg.functionCall.parameters
                    
            query = params.get("q")
            # If params has a nested structure with arguments that contain q
            if not query and isinstance(params, dict) and "arguments" in params:
                if isinstance(params["arguments"], dict):
                    query = params["arguments"].get("q")
                elif isinstance(params["arguments"], str):
                    try:
                        arg_dict = json.loads(params["arguments"])
                        query = arg_dict.get("q")
                    except json.JSONDecodeError:
                        pass
        
        if not query:
            logging.error("Could not extract query from request")
            return JSONResponse(
                status_code=400,
                content={
                    "error": "missing_parameter",
                    "hint": "Could not find 'q' parameter in the request"
                }
            )
        
        logging.info(f"Successfully extracted query: '{query}' from request")
        
        # Call our internal search function
        try:
            # Use default values for optional parameters
            top_k = 5
            filter_type = None
            
            # Call our internal search function
            search_response = await search_kb(query, top_k, filter_type)
            
            # Format the response according to Vapi's documented format
            # Simply return the result as documented
            return {"result": search_response.get("results", [])}
            
        except Exception as e:
            logging.error(f"Error during search: {str(e)}")
            return JSONResponse(
                status_code=500,
                content={
                    "error": "search_error",
                    "hint": f"Error processing search: {str(e)}"
                }
            )
    
    except Exception as e:
        logging.error(f"Error in /search adapter: {str(e)}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "hint": f"Error in adapter: {str(e)}"
            }
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