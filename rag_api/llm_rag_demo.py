#!/usr/bin/env python3
"""
llm_rag_demo.py - CLI for Retrieval-Augmented Generation (RAG) with OpenAI and Pinecone

Usage:
  poetry run python rag_api/llm_rag_demo.py --query "What sports programs are offered at DME Academy?" [--top_k 5]

- Retrieves top-k relevant chunks from Pinecone
- Assembles a prompt with system instructions, user query, and context
- Calls OpenAI GPT-4o (or gpt-4o-mini) asynchronously
- Prints the synthesized answer and the context used
"""
import os
import argparse
import asyncio
from dotenv import load_dotenv
import pinecone
import openai

# Load environment variables
load_dotenv()

PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME", "dme-kb")
PINECONE_NAMESPACE = os.getenv("PINECONE_NAMESPACE", "dme-kb")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o")

openai.api_key = OPENAI_API_KEY
client = openai.AsyncOpenAI(api_key=OPENAI_API_KEY)
pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
index = pc.Index(PINECONE_INDEX_NAME)

SYSTEM_PROMPT = (
    "You are a helpful assistant for DME Academy. "
    "Answer ONLY from the provided context. "
    "If the user asks for a list (e.g., sports programs), extract and list them clearly. "
    "Cite the source URL for each fact if possible."
)

async def embed_query(query):
    resp = await client.embeddings.create(input=query, model=EMBEDDING_MODEL)
    return resp.data[0].embedding

async def retrieve_context(query, top_k=5):
    embedding = await embed_query(query)
    results = index.query(
        vector=embedding,
        top_k=top_k,
        include_metadata=True,
        namespace=PINECONE_NAMESPACE
    )
    matches = results.get("matches", [])
    context_chunks = []
    for m in matches:
        text = m['metadata'].get('text', '')
        url = m['metadata'].get('canonical_url', '')
        context_chunks.append((text, url))
    return context_chunks

async def call_llm(system_prompt, user_query, context_chunks):
    context_text = "\n\n".join([
        f"[Source: {url}]:\n{text[:500]}{'...' if len(text) > 500 else ''}" for text, url in context_chunks if text
    ])
    prompt = f"{system_prompt}\n\nContext:\n{context_text}\n\nUser Query: {user_query}\n\nAnswer:"
    response = await client.chat.completions.create(
        model=LLM_MODEL,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        max_tokens=512,
        temperature=0.2
    )
    return response.choices[0].message.content.strip(), context_text

async def main():
    parser = argparse.ArgumentParser(description="RAG CLI for DME Academy")
    parser.add_argument('--query', type=str, required=True, help='User query for the knowledge base')
    parser.add_argument('--top_k', type=int, default=5, help='Number of context chunks to retrieve')
    args = parser.parse_args()

    print(f"\n[INFO] Query: {args.query}")
    print(f"[INFO] Retrieving top {args.top_k} context chunks from Pinecone...")
    context_chunks = await retrieve_context(args.query, args.top_k)
    if not context_chunks:
        print("[WARN] No relevant context found in Pinecone.")
        return
    print(f"[INFO] Retrieved {len(context_chunks)} context chunks.")
    print("[INFO] Calling OpenAI LLM for synthesis...")
    answer, context_text = await call_llm(SYSTEM_PROMPT, args.query, context_chunks)
    print("\n===== Synthesized Answer =====\n")
    print(answer)
    print("\n===== Context Used =====\n")
    print(context_text)

if __name__ == "__main__":
    asyncio.run(main()) 