# DME Knowledge Base API Integration with Vapi.ai

This README provides instructions for integrating the DME Knowledge Base API with Vapi.ai's voice assistant platform.

## Overview

The integration allows Vapi.ai assistants to search the DME Academy knowledge base and provide relevant information to users through voice interactions. This is implemented through Vapi's function calling mechanism, which allows the assistant to query external APIs for information.

## Prerequisites

1. A running instance of the DME Knowledge Base API
2. A Vapi.ai account with access to create or modify assistants
3. An API key for Vapi.ai
4. A secret API token for securing the integration (required)

## Setting Up the Integration

### 1. Configure the DME Knowledge Base API

1. Set the `VAPI_TOKEN` environment variable with a secure secret token. This will be used to authenticate requests from Vapi.
   ```
   export VAPI_TOKEN=your-secure-token-here
   ```

2. Ensure your API is deployed and accessible from the internet (e.g., via Render.com).

3. The DME Knowledge Base API exposes a special `/vapi-search` endpoint specifically for Vapi.ai, which:
   - Accepts POST requests with Vapi's function call payload format
   - Requires an Authorization header with your Bearer token
   - Returns results in the format expected by Vapi

### 2. Configure Vapi.ai

1. In your Vapi.ai dashboard, create or select an assistant.

2. Add a custom tool with the following configuration:
   - **Name**: `searchDMEKnowledgeBase`
   - **Description**: `Search the DME Academy knowledge base for information about programs, staff, facilities, and more.`
   - **Server URL**: `https://<your-api-url>/vapi-search` (e.g., `https://dme-sync.onrender.com/vapi-search`)
   - **Method**: `POST` (default)
   - **Headers**: Add an `Authorization` header with value `Bearer your-secure-token-here`

3. Define the parameters for the function:
   ```json
   {
     "query": {
       "type": "string",
       "description": "The search query about DME Academy",
       "required": true
     },
     "top_k": {
       "type": "number",
       "description": "Number of results to return",
       "default": 5
     },
     "filter_type": {
       "type": "string",
       "description": "Filter by content type (e.g., 'staff', 'program', 'facility')",
       "enum": ["staff", "program", "facility", "news", "page", "event"]
     }
   }
   ```

4. Add appropriate response messages in Vapi:
   - Request Start: "Searching the DME Academy knowledge base for information about your query..."
   - Request Complete: "I found some information that might help:"
   - Request Failed: "I'm sorry, I wasn't able to search our knowledge base right now. Let me see if I can help you in another way."

### 3. Test the Integration

1. Use the provided `test_vapi_search.py` script to test your integration:
   ```
   python test_vapi_search.py --url https://<your-api-url>/vapi-search --query "Who is Dan Panaggio?" --auth-token your-secure-token-here
   ```

2. Use the "Test Tool" feature in Vapi's assistant configuration to verify the integration works.

## Best Practices

1. **Security**: Always use the Authorization header with a Bearer token for authentication.
2. **Monitoring**: Monitor the API logs for errors or unusual request patterns.
3. **Rate Limiting**: Consider implementing rate limiting to prevent abuse.
4. **Versioning**: If you make changes to the API, version your endpoints (e.g., `/v1/vapi-search`).

## Troubleshooting

- If you receive 401 Unauthorized errors, check that the Authorization header is correctly set.
- If you receive 400 Bad Request errors, check the format of your JSON payload.
- Check the API logs for detailed error information.

## Example System Prompt for Assistant

You can enhance the assistant's effectiveness by adding instructions about when to use the search functionality. Here's an example system prompt:

```
You are a helpful assistant for DME Academy, a premier sports academy in Florida.

When users ask about DME Academy's programs, staff, facilities, or general information, use the searchDMEKnowledgeBase function to retrieve accurate information.

Present the search results in a friendly, conversational manner, highlighting the most relevant details. If multiple relevant results are found, summarize the most important information from all relevant sources.

If you're not sure about a specific detail, use the search function rather than making an assumption. If the search doesn't yield relevant results, acknowledge this and offer to help the user find information another way.
```

## Advanced Configuration

- **Filtering Results**: You can filter search results by content type using the `filter_type` parameter, with options like "news", "page", "staff", or "program".
- **Result Count**: Control the number of results returned with the `top_k` parameter (default is 5).

---

For further assistance with this integration, please contact the API administrator or refer to the Vapi.ai documentation for custom tool integration. 