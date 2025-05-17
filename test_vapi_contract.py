#!/usr/bin/env python3
import json
import os
import unittest
from fastapi.testclient import TestClient
from main import app

class VapiContractTest(unittest.TestCase):
    """Test suite for verifying Vapi integration contract is maintained"""
    
    def setUp(self):
        """Set up test client and load fixtures"""
        self.client = TestClient(app)
        
        # Load test fixture
        fixture_path = "test_vapi_fixture.json"
        with open(fixture_path, "r") as f:
            self.fixture = json.load(f)
        
        # Set up test auth token
        os.environ["VAPI_TOKEN"] = "test-token-for-contract-tests"
        self.auth_header = {"Authorization": f"Bearer {os.environ['VAPI_TOKEN']}"}
    
    def test_vapi_search_contract(self):
        """Test that the Vapi search endpoint correctly handles the fixture payload"""
        # Send the request with the fixture payload
        response = self.client.post(
            "/vapi-search", 
            json=self.fixture,
            headers=self.auth_header
        )
        
        # Check response status
        self.assertEqual(response.status_code, 200, 
                        f"Expected 200 OK, got {response.status_code}: {response.text}")
        
        # Verify response structure
        data = response.json()
        self.assertIn("results", data, "Response missing 'results' field")
        self.assertTrue(isinstance(data["results"], list), "'results' should be a list")
        
        # Check results format - must have at least one result with toolCallId and result fields
        if data["results"]:
            result = data["results"][0]
            self.assertIn("toolCallId", result, "Result missing 'toolCallId'")
            self.assertIn("result", result, "Result missing 'result' field")
            
            # Verify the toolCallId matches the one in the fixture
            fixture_tool_call_id = self.fixture["message"]["toolCallList"][0]["id"]
            self.assertEqual(result["toolCallId"], fixture_tool_call_id, 
                            "toolCallId in response does not match fixture")
            
            # Parse the result JSON and verify it has the expected fields
            result_data = json.loads(result["result"])
            self.assertIn("results", result_data, "Result data missing 'results' field")
            self.assertIn("query", result_data, "Result data missing 'query' field")
            self.assertIn("processingTimeMs", result_data, "Result data missing 'processingTimeMs' field")
    
    def test_unauthorized_request(self):
        """Test that unauthorized requests are properly rejected"""
        # Send request without authorization header
        response = self.client.post("/vapi-search", json=self.fixture)
        
        # Verify unauthorized response
        self.assertEqual(response.status_code, 401, 
                        f"Expected 401 Unauthorized, got {response.status_code}")
        
        # Check error format
        data = response.json()
        self.assertIn("error", data, "Error response missing 'error' field")
        self.assertEqual(data["error"], "unauthorized", "Incorrect error type")
    
    def test_invalid_payload(self):
        """Test that invalid payloads are properly handled with helpful error messages"""
        # Create an invalid payload missing required fields
        invalid_payload = {"message": {"something": "wrong"}}
        
        # Send request
        response = self.client.post(
            "/vapi-search", 
            json=invalid_payload,
            headers=self.auth_header
        )
        
        # Verify bad request response
        self.assertEqual(response.status_code, 400, 
                        f"Expected 400 Bad Request, got {response.status_code}")
        
        # Check error format
        data = response.json()
        self.assertIn("error", data, "Error response missing 'error' field")
        self.assertIn("hint", data, "Error response missing 'hint' field")
        self.assertEqual(data["error"], "unsupported_payload", "Incorrect error type")

if __name__ == "__main__":
    unittest.main() 