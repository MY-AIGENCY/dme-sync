# DME-SYNC RAG Pipeline — Project Brief & Handoff

## Project Overview
This repository implements a modular, production-grade Retrieval-Augmented Generation (RAG) pipeline for knowledge base construction, designed for rapid onboarding of new clients and scalable, cloud-native operation. The pipeline is structured for maximum automation, auditability, and future SaaS extensibility.

---

## Current Status

### 1. Repository Structure
- `scraper/`: Automated content discovery and ingestion (sitemap, WordPress API, or crawl).
- `indexer/`: Normalization, chunking, and vector indexing (Section 4 complete and verified; 3200+ vectors in Pinecone).
- `processor/`: Data processing and enrichment (Section 2 complete and verified).
- `rag_api/`: API serving and retrieval (next steps: Section 5+).
- `tests/`: Automated testing (core pipeline covered).
- `legacy_build/`: Contains old/legacy files, not part of the current build.

### 2. Core Functionality
- **Discovery & Capture (Section 1 Complete):**
  - Sitemap, WordPress API, or crawl; uploads raw JSON to S3; manifests and run logs maintained.
- **Normalize & Canonicalize (Section 2 Complete):**
  - Stable doc IDs, text cleaning, entity detection, JSONSchema validation, Postgres persistence, and S3 manifest.
- **Chunk, Embed, Index (Section 4 Complete):**
  - 499 docs processed, 3200+ vectors upserted to Pinecone (namespace: dme-kb), with audit manifests in S3. End-to-end pipeline execution verified.

### 3. Security & Best Practices
- All secrets are removed from git history.
- `.env` and `.env-e` are ignored; a clean `.env.template` is provided.
- `.gitignore` is up to date, covering all sensitive, system, and legacy files.
- No unnecessary files are tracked; legacy and tool files are excluded.

### 4. Deployment & Environment
- **Docker Compose** and **Dockerfile** are provided for local/cloud orchestration.
- **Poetry** is used for Python dependency management.
- **AWS S3** is used for storage; credentials are loaded from environment variables.
- No Heroku/Render Procfile is present (can be added if needed).

---

## Next Steps for Development

1. **Section 5: Retrieval Pipeline**
   - Implement and test retrieval logic (BM25, embedding search, RRF fusion, metadata filtering).

2. **Section 6+:**  
   - Continue modular implementation of the RAG pipeline as described in the dev rules.

3. **Testing & CI:**  
   - Expand test coverage in `tests/` as new modules are developed.
   - Ensure CI workflows are updated for new modules.

4. **Frontend/Onboarding Automation (Future Vision):**
   - Plan for API-driven client onboarding and infrastructure provisioning.
   - Design a simple frontend/dashboard for rapid client setup and monitoring.

---

## How to Resume

- Review the latest manifest and run log in S3 for context on the most recent scrape and upsert.
- Use `.env.template` to configure your environment.
- All code is on the branch: `rag-pipeline-upgrade/2025-05-18`.
- Continue development per the modular sections in `.DME-SYNC_DEV_RULES.md`.

---

## Contacts & Support

- For any questions about the pipeline, code structure, or next steps, refer to `.DME-SYNC_DEV_RULES.md` and this brief.
- All legacy files are in `legacy_build/` for reference if needed.

---

**This project is ready for seamless handoff and further development.**  
All best practices for security, modularity, and auditability have been followed. 