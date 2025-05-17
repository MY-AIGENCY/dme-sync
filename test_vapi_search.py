#!/usr/bin/env python3
import requests
import json
import argparse
import os
import time
from dotenv import load_dotenv

# Load environment variables from .env file if present
load_dotenv()

def test_vapi_search(url, query, auth_token=None, top_k=5, filter_type=None):
    """
    Test the Vapi search endpoint by simulating a Vapi function call
    
    Args:
        url (str): The URL of the vapi-search endpoint
        query (str): The search query to use
        auth_token (str, optional): The auth token for Bearer authentication
        top_k (int, optional): Number of results to return
        filter_type (str, optional): Filter by content type
    
    Returns:
        dict: The response from the API
    """
    # Create a simulated Vapi request
    vapi_request = {
        "message": {
            "toolCallList": [
                {
                    "id": f"test-call-{int(time.time())}",
                    "name": "searchDMEKnowledgeBase",
                    "arguments": {
                        "query": query,
                        "top_k": top_k
                    }
                }
            ]
        }
    }
    
    # Add filter_type if provided
    if filter_type:
        vapi_request["message"]["toolCallList"][0]["arguments"]["filter_type"] = filter_type
    
    # Setup headers
    headers = {
        "Content-Type": "application/json"
    }
    
    # Add authorization if token provided
    if auth_token:
        headers["Authorization"] = f"Bearer {auth_token}"
    
    print(f"Sending request to {url}")
    print(f"Request payload: {json.dumps(vapi_request, indent=2)}")
    
    # Send the request
    try:
        response = requests.post(url, json=vapi_request, headers=headers)
        
        # Print response status and headers
        print(f"Response status: {response.status_code}")
        
        # Try to parse as JSON
        try:
            result = response.json()
            print(f"Response: {json.dumps(result, indent=2)}")
            return result
        except json.JSONDecodeError:
            print(f"Response is not valid JSON: {response.text}")
            return {"error": "Invalid JSON response", "text": response.text}
    
    except Exception as e:
        print(f"Error sending request: {e}")
        return {"error": str(e)}

def main():
    parser = argparse.ArgumentParser(description="Test Vapi search endpoint")
    parser.add_argument("--url", required=True, help="URL for the vapi-search endpoint")
    parser.add_argument("--query", required=True, help="Search query to use")
    parser.add_argument("--auth-token", help="Auth token for request authentication")
    parser.add_argument("--top-k", type=int, default=5, help="Number of results to return")
    parser.add_argument("--filter-type", help="Filter by content type")
    
    args = parser.parse_args()
    
    # Use auth token from args or environment
    auth_token = args.auth_token or os.getenv("VAPI_TOKEN") or os.getenv("VAPI_SECRET_KEY")
    
    # Run the test
    test_vapi_search(
        url=args.url,
        query=args.query,
        auth_token=auth_token,
        top_k=args.top_k,
        filter_type=args.filter_type
    )

if __name__ == "__main__":
    main() 