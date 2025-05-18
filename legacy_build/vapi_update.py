# New Vapi implementation
from pydantic import BaseModel
from typing import Dict, Any, Optional

class VapiMessage(BaseModel):
    type: str
    functionCall: Optional[Dict[str, Any]] = None

class VapiEnvelope(BaseModel):
    message: VapiMessage

@app.post("/vapi-search")
async def vapi_search(request: Request):
    """
    Handle search requests from Vapi.ai using the new Server-Events dialect
    
    This endpoint accepts POST requests from Vapi.ai's function calling system,
    extracts the search query, forwards it to our search functionality,
    and returns the results in Vapi's expected format.
    """
    # Verify auth token
    auth = request.headers.get("authorization")
    if not auth or auth != f"Bearer {VAPI_TOKEN}":
        raise HTTPException(401, "Unauthorized")
    
    try:
        # Parse request body
        body = await request.json()
        env = VapiEnvelope.parse_obj(body)
        msg = env.message
        
        # Log request details
        logging.info(f"Received Vapi request of type: {msg.type}")
        
        # Handle only function-call message types
        if msg.type != "function-call" or not msg.functionCall:
            logging.info("Ignoring non-function-call event")
            return {}  # Ignore non-function events
        
        # Handle only knowledge_search function calls
        if msg.functionCall["name"] != "knowledge_search":
            logging.warning(f"Unknown function: {msg.functionCall['name']}")
            return {"result": f"Unknown function {msg.functionCall['name']}"}
        
        # Extract parameters
        params = {}
        if "parameters" in msg.functionCall:
            # Handle if parameters is a string
            if isinstance(msg.functionCall["parameters"], str):
                params = json.loads(msg.functionCall["parameters"])
            else:
                params = msg.functionCall["parameters"]
        
        # Extract query
        q = params.get("q")
        if not q:
            logging.warning("Missing required parameter: q")
            return {"result": "Missing q parameter"}
        
        # Get optional parameters
        top_k = params.get("top_k", 3)
        filter_type = params.get("filter_type", None)
        
        # Call the search function
        logging.info(f"Searching for query: {q}, top_k: {top_k}")
        result = await search_kb(q, top_k=top_k, filter_type=filter_type)
        
        # Format the final response
        logging.info(f"Search complete, found {len(result.get('results', []))} results")
        return {"result": result.get("results", [])}
        
    except Exception as e:
        logging.error(f"Error processing Vapi request: {str(e)}")
        raise HTTPException(500, f"Error processing request: {str(e)}")
