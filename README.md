# Current Status

- Completed: Section 1 (Discovery & Capture)
- In Progress: Section 2 (Normalize & Canonicalize)
- Next: Section 3 (Relationship Graph)
- Blockers: None

# DME Knowledge Base Pipeline

A complete end-to-end pipeline for syncing content from DME Academy's website into a queryable knowledge base.

## Overview

This system consists of three main components:

1. **Data Syncing**: Scrapes content from dmeacademy.com website into a SQLite database
2. **Knowledge Base Building**: Converts the database content into a structured KB and embeds it
3. **Search API**: Provides a FastAPI service to search the knowledge base

The system runs daily via GitHub Actions to keep the knowledge base up-to-date.

## Components

### 1. Content Syncing (`dme_sync.py`)

Scrapes various content types from the DME Academy website:
- Blog posts and news articles
- Static website pages
- Staff profiles
- Events and programs

### 2. Knowledge Base Building

#### `kb_update.py`
Converts the SQLite database to a structured JSON knowledge base.

#### `embed_upsert.py`
Embeds the content using OpenAI embeddings and uploads to:
- Pinecone (vector database)
- Typesense (text search, optional)

### 3. Search API (`main.py`)

FastAPI service with endpoints:
- `/search`: Search the knowledge base (used by Vapi.ai)
- `/ingest`: Manually add content

## Setup

### Prerequisites

- Python 3.10+
- API keys for:
  - OpenAI (required for embeddings)
  - Pinecone (required for vector storage)
  - Typesense (optional for text search)
- Docker (for containerized deployment)

### Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/dme-sync.git
   cd dme-sync
   ```

2. Set up a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create `.env` file with your API keys:
   ```
   # Optional webhook for notifications
   SLACK_HOOK=your_slack_webhook_url
   
   # Required for embeddings
   OPENAI_API_KEY=your_openai_key
   
   # Required for vector storage
   PINECONE_API_KEY=your_pinecone_key
   PINECONE_ENVIRONMENT=gcp-starter
   PINECONE_INDEX_NAME=dme-kb
   
   # Optional for text search
   TYPESENSE_API_KEY=your_typesense_key
   TYPESENSE_HOST=your_typesense_host
   TYPESENSE_PORT=8108
   TYPESENSE_PROTOCOL=http
   ```

## Usage

### Running the Pipeline Locally

1. Run the data sync:
   ```
   python dme_sync.py
   ```

2. Build the knowledge base:
   ```
   python kb_update.py
   ```

3. Embed and upload to vector stores:
   ```
   python embed_upsert.py
   ```

4. Start the API server:
   ```
   uvicorn main:app --reload
   ```

### Using Docker

Build and run the Docker container:
```
docker build -t dme-kb .
docker run -p 8000:8000 --env-file .env dme-kb
```

### GitHub Actions Automation

The repository includes two GitHub Action workflows:

1. **daily-sync.yml**:
   - Runs at 9:03 AM New York time
   - Scrapes website content to `dme.db`
   - Automatically triggers the KB build workflow

2. **build-kb.yml**:
   - Converts SQLite data to `master_kb.json`
   - Creates embeddings with OpenAI
   - Uploads to Pinecone (and optionally Typesense)
   - Runs daily at 03:00 UTC
   - Runs on push to main
   - Can be manually triggered

**Required GitHub Secrets:**
- `OPENAI_API_KEY`
- `PINECONE_API_KEY`
- `PINECONE_ENVIRONMENT` (defaults to `gcp-starter`)
- `PINECONE_INDEX_NAME` (defaults to `dme-kb`)
- `SLACK_HOOK` (optional)
- `NOTIFICATION_WEBHOOK_URL` (optional)
- Typesense related secrets (optional)

## API Usage

### Searching the Knowledge Base

```bash
curl -X 'GET' 'http://localhost:8000/search?q=basketball%20camps&top_k=3'
```

### Adding Content (Manually)

```bash
curl -X 'POST' 'http://localhost:8000/ingest' \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "Example Content",
    "content": "This is some example content.",
    "type": "manual",
    "url": "https://example.com"
  }'
```

## Vapi.ai Integration

The search API is designed to work with Vapi.ai. Configure your Vapi.ai function to call the `/search` endpoint.

# Handoff Checklist (update at end of each session)

- [ ] What was completed:
- [ ] What remains:
- [ ] Any blockers or questions:

