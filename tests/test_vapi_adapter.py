#!/usr/bin/env python3
import json
import os
import unittest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock
import sys
sys.path.append('..')  # Add the parent directory to the path

# Import the application
from main import app

class TestVapiAdapter(unittest.TestCase):
    """Test the new Vapi Server-Events adapter"""
    
    def setUp(self):
        self.client = TestClient(app)
        os.environ["VAPI_TOKEN"] = "test-token"
        self.headers = {"Authorization": "Bearer test-token"}
        
        # Sample valid request
        self.valid_request = {
            "message": {
                "type": "function-call",
                "functionCall": {
                    "name": "knowledge_search",
                    "parameters": {
                        "q": "Who is Dan Panaggio?"
                    }
                }
            }
        }
        
        # Sample expected search results
        self.sample_results = {
            "results": [
                {
                    "id": "test-id-1",
                    "score": 0.95,
                    "metadata": {
                        "title": "About Dan Panaggio",
                        "type": "staff"
                    }
                }
            ],
            "query": "Who is Dan Panaggio?",
            "processingTimeMs": 123
        }

    @patch('main.search_kb')
    async def async_test_valid_request(self, mock_search_kb):
        """Test that a valid request returns expected results"""
        # Setup mock
        mock_search_kb.return_value = self.sample_results
        
        # Make request
        response = self.client.post(
            "/vapi-search",
            json=self.valid_request,
            headers=self.headers
        )
        
        # Check response
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("result", data)
        self.assertEqual(len(data["result"]), 1)
        
        # Check that search_kb was called with correct parameters
        mock_search_kb.assert_called_once_with(
            "Who is Dan Panaggio?", 
            top_k=3, 
            filter_type=None
        )
    
    def test_valid_request(self):
        """Run the async test"""
        import asyncio
        asyncio.run(self.async_test_valid_request())
    
    def test_missing_auth(self):
        """Test that missing auth header returns 401"""
        response = self.client.post(
            "/vapi-search",
            json=self.valid_request
        )
        self.assertEqual(response.status_code, 401)
    
    def test_invalid_auth(self):
        """Test that invalid auth token returns 401"""
        response = self.client.post(
            "/vapi-search",
            json=self.valid_request,
            headers={"Authorization": "Bearer invalid-token"}
        )
        self.assertEqual(response.status_code, 401)
    
    def test_non_function_call(self):
        """Test that non-function-call message types are ignored"""
        request = {
            "message": {
                "type": "not-a-function-call"
            }
        }
        response = self.client.post(
            "/vapi-search",
            json=request,
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {})
    
    def test_unknown_function(self):
        """Test that unknown function names return appropriate error"""
        request = {
            "message": {
                "type": "function-call",
                "functionCall": {
                    "name": "unknown_function",
                    "parameters": {
                        "q": "test query"
                    }
                }
            }
        }
        response = self.client.post(
            "/vapi-search",
            json=request,
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("result", data)
        self.assertIn("Unknown function", data["result"])
    
    def test_missing_query(self):
        """Test that missing query parameter returns appropriate error"""
        request = {
            "message": {
                "type": "function-call",
                "functionCall": {
                    "name": "knowledge_search",
                    "parameters": {}
                }
            }
        }
        response = self.client.post(
            "/vapi-search",
            json=request,
            headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertIn("result", data)
        self.assertIn("Missing q", data["result"])

if __name__ == "__main__":
    unittest.main() 