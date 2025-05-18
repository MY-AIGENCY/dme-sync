# Vapi Integration Deployment Checklist

This checklist covers all the steps needed to configure and deploy the DME Knowledge Base API with Vapi.ai integration.

## Local Development & Testing

- [ ] Install all required dependencies:
  ```
  pip install fastapi uvicorn pinecone openai python-dotenv pytest httpx
  ```

- [ ] Set up environment variables for local testing:
  ```
  export OPENAI_API_KEY=your-openai-key
  export PINECONE_API_KEY=your-pinecone-key
  export VAPI_TOKEN=your-test-token
  ```

- [ ] Run unit tests to verify the integration:
  ```
  python test_vapi_contract.py
  ```

- [ ] Run local server for testing:
  ```
  uvicorn main:app --reload
  ```

- [ ] Run the test script against your local server:
  ```
  python test_vapi_search.py --url http://localhost:8000/vapi-search --query "test query" --auth-token your-test-token
  ```

## Render.com Deployment

- [ ] Update environment variables in the Render.com dashboard:
  - `OPENAI_API_KEY`
  - `PINECONE_API_KEY`
  - `PINECONE_ENVIRONMENT` (gcp-starter or us-east-1 for free tier)
  - `PINECONE_INDEX_NAME`
  - `VAPI_TOKEN` (new secure token for production)

- [ ] Commit and push the latest code to GitHub:
  ```
  git add .
  git commit -m "Add Vapi.ai integration with best practices"
  git push
  ```

- [ ] Verify deployment was successful:
  ```
  curl -X GET https://dme-sync.onrender.com/health
  ```

- [ ] Test Vapi endpoint on the deployed version:
  ```
  python test_vapi_search.py --url https://dme-sync.onrender.com/vapi-search --query "Dan Panaggio" --auth-token your-production-token
  ```

## Vapi.ai Configuration

- [ ] In Vapi dashboard, create or edit a function tool with:
  - **Name**: `searchDMEKnowledgeBase`
  - **Description**: `Search the DME Academy knowledge base for information about programs, staff, facilities, and more.`
  - **Server URL**: `https://dme-sync.onrender.com/vapi-search`
  - **Method**: `POST` (default)

- [ ] Add authentication header in Vapi:
  - **Key**: `Authorization`
  - **Value**: `Bearer your-production-token`

- [ ] Configure Vapi response messages:
  - Request start: `Searching the DME Academy knowledge base for information about your query...`
  - Request complete: `I found some information that might help:`
  - Request failed: `I'm sorry, I wasn't able to search our knowledge base right now. Let me see if I can help you in another way.`

- [ ] Test the function in Vapi dashboard:
  - Use the "Test" button with a sample query like "Who is Dan Panaggio?"
  - Verify that results appear and match expectations

## Monitoring & Maintenance

- [ ] Set up regular monitoring of:
  - API logs for errors or unusual patterns
  - Rate limiting effectiveness
  - Response times

- [ ] Create a monitoring dashboard or alerts for:
  - 4xx or 5xx errors
  - High latency responses
  - Rate limit exceeded events

- [ ] Document the API version and contract for future reference

## Troubleshooting Common Issues

- **401 Unauthorized**: Check that the Authorization header is correctly configured with the Bearer token
- **400 Bad Request**: Verify the request payload format matches what Vapi sends
- **429 Too Many Requests**: Adjust rate limits if legitimate traffic is being blocked
- **500 Internal Server Error**: Check logs for issues with OpenAI or Pinecone connectivity 