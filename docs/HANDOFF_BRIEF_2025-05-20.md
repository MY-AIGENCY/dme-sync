
# Voice‑Agent Knowledge Base — Handoff Brief (2025-05-20)

This brief accelerates onboarding for a **new AI developer** taking over the voice‑agent knowledge‑base project.

---

## 1 · Project Snapshot

| Aspect | Status |
|--------|--------|
| **Purpose** | Voice agent that answers company questions via LLM → TTS |
| **Strengths** | End‑to‑end pipeline for data ingestion, chunking, embedding, and Pinecone indexing is operational |
| **Weak Link** | Retrieved answers lack precision; needs semantic relationship modeling & metadata enrichment |
| **Current Branch** | `rag-pipeline-upgrade/2025-05-18` |
| **Tech Stack** | Python 3.11 · Poetry · Docker Compose · AWS S3 · Postgres · Neo4j · Pinecone · GitHub Actions |

---

## 2 · Recent History

- **Discovery & Capture**: sitemap / API crawler uploads raw content to S3.  
- **Normalize & Canonicalize**: cleans text, assigns `doc_id`, stores in Postgres (Section 2 completed).  
- **Chunk → Embed → Index**: creates hierarchical chunks, embeds via OpenAI, upserts to Pinecone (dry‑run validated; full scale pending).  
- **Pinecone blocker**: resolved by upgrading client & adding `__init__.py` packages.  
- **Dev Rules**: rigorous, test‑driven workflow established.citeturn3file1

---

## 3 · Identified Gap

The pipeline lacks a **semantic‑relationship & metadata‑enrichment** layer:

1. Entity extraction & typing.  
2. Relationship graph (e.g., staff → program, FAQ → topic).  
3. Rich metadata (dates, tags, source reliability) for filtered retrieval.  
4. Re‑ranking that fuses vector + graph proximity.

---

## 4 · Immediate Next Step

Run the prompt below to generate the concise development plan, then implement it.

```
You are KnowledgeGraph Architect, an expert in building high‑precision, low‑latency retrieval pipelines for conversational AI.

Task: Devise a concise, step‑by‑step development plan that adds a semantic‑relationship & metadata‑enrichment layer to an existing Pinecone‑backed RAG pipeline, so answers become both highly accurate and fast.

Essential context (verbatim):
"""
• Current pipeline: ingest → chunk → embed → index → store in Pinecone → retrieve → summarize → TTS.  
• Weak link: retrieved answers lack relevance/coverage; likely missing deep relationship modeling & rich metadata.  
• Goal: auto‑generate an “optimized knowledge base” from any data source whose records can be queried with near‑100 % accuracy and minimal latency.  
• You may propose code, off‑the‑shelf tools, or hybrid approaches.
"""

Output constraints
- Format: numbered steps (≤ 12), each with **Action**, **Why**, **Tool/Code Hint**.
- Include specific libraries/services (Python preferred) and schema examples where helpful (≤ 15 lines of code each).
- Cover: entity extraction, ontology/graph building, metadata generation, re‑indexing, evaluation metrics.
- Tone: direct, engineering‑focused, no fluff.
- Length: ≤ 450 words.

```

---

## 5 · Handoff Checklist (filled)

- **What was completed**: Sections 1‑2 fully implemented; Pinecone integration fixed; dev rules & tests consolidated.  
- **What remains**: Graph/metadata enrichment, retrieval re‑rank, final evaluation dashboard.  
- **Blockers / questions**: None; awaiting enrichment plan & execution.

---

*Welcome aboard—start by executing the prompt above, then follow the universal dev rules.*
