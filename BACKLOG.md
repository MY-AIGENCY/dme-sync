# Project Backlog

This document tracks future development tasks, improvements, and technical debt for the DME Knowledge Base Pipeline.

## Open Tasks

- [ ] Add checkpointing and resumable processing to normalization/canonicalization pipeline
- [ ] Incremental manifest writing for long-running jobs
- [ ] Complete docs/oncall.md with full incident response runbook
- [ ] Add more real-data integration tests for edge cases
- [ ] Implement semantic relationship & metadata enrichment layer (see HANDOFF_BRIEF_2025-05-20.md)
- [ ] Add automated data parity audits between S3, Postgres, and Pinecone
- [ ] Review and optimize all pipeline logging for clarity and completeness
- [ ] (Add more as needed)

## Recently Completed

- [x] Migrated to src/ layout
- [x] Removed legacy/obsolete files
- [x] Enforced cloud-only development protocol
- [x] Updated dev rules for real-data testing 