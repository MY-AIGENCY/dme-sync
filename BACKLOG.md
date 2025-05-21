# Project Backlog

> **For real-time project status, see [CURRENT_STATUS.md](./CURRENT_STATUS.md)**

This document tracks future development tasks, improvements, and technical debt for the DME Knowledge Base Pipeline.

## Open Tasks

- [ ] Retrieval Pipeline: Integrate enrichment fields, validate in test mode, prepare for production rollout
- [ ] API: Expose enriched fields in search results
- [ ] Evaluation: Add precision/recall/latency metrics and feedback logging
- [ ] Add more real-data integration tests for edge cases
- [ ] Add automated data parity audits between S3, Postgres, and Pinecone
- [ ] Review and optimize all pipeline logging for clarity and completeness
- [ ] (Add more as needed)

## Recently Completed

- [x] AI-driven enrichment, chunking, and test-mode pipeline (validated)
- [x] Entity Extraction: Integrate NER (e.g., spaCy) into normalization ([docs](./docs/HANDOFF_BRIEF_2025-05-20.md))
- [x] Entity Typing/Linking: Add canonical typing and optional Wikidata linking
- [x] Relationship Extraction: Add OpenIE or dependency parsing for triples
- [x] Ontology/Graph Schema: Define and document minimal ontology ([docs/schema_v1.md](./docs/schema_v1.md))
- [x] Graph Construction: Upsert nodes/edges into Neo4j
- [x] Metadata Enrichment: Attach metadata to chunks
- [x] Re-index: Re-chunk, re-embed, and upsert with new metadata
- [x] Hybrid Retrieval: Fuse vector and graph search
- [x] Re-ranking: Implement metadata and graph-based re-ranking
- [x] Migrated to src/ layout
- [x] Removed legacy/obsolete files
- [x] Enforced cloud-only development protocol
- [x] Updated dev rules for real-data testing 