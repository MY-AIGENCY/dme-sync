# DME Knowledge Base Pipeline — Living History & Development Guide

## Next Steps (as of May 2025)

- Branch from the current commit and begin the package refactor (move code to `src/dme_sync/`, update imports, enable Poetry packaging).
- Always update this guide and the README with the latest project status, handoff notes, and any changes made.
- If you are picking up this project, review both this file and the README before making changes, and document your starting point and all updates.

---

## Table of Contents
1. [Project Overview & Background](#project-overview--background)
2. [Current Status & Backlog](#current-status--backlog)
3. [Development Rules & Workflow](#development-rules--workflow)
4. [Onboarding & Kickoff Context](#onboarding--kickoff-context)
5. [Style, Personality & Collaboration](#style-personality--collaboration)
6. [Schema & Architecture](#schema--architecture)
7. [Runbook & Troubleshooting](#runbook--troubleshooting)
8. [Handoff Checklist](#handoff-checklist)
9. [References & Archives](#references--archives)

---

## 1. Project Overview & Background
- **Goal:** Build a modular, cloud-native, AI-enriched RAG pipeline for DME Academy, supporting robust retrieval, semantic enrichment, and production-grade reliability.
- **Tech Stack:** Python 3.11+, Poetry, Docker Compose, Postgres, Neo4j, Pinecone, Weaviate, AWS S3, GitHub Actions.
- **Pipeline:** Discovery → Normalize → Relationship Graph → Chunk/Embed/Index → Retrieval → LLM Prompting → Feedback/Monitoring → Security/Compliance.
- **History:** See [References & Archives](#references--archives) for detailed logs and prior handoff briefs.

---

## 2. Current Status & Backlog
- **Status:**
  - Completed: Normalize & Canonicalize, Chunk/Embed/Index (AI-driven enrichment, test-mode validated)
  - In Progress: Retrieval Pipeline (integration of enrichment fields, test-mode validation)
  - Next: Integrate enrichment fields into retrieval pipeline and API, prepare for production rollout
  - Blockers: None
- **Backlog:**
  - [ ] Integrate enrichment fields into retrieval pipeline, validate in test mode
  - [ ] Expose enriched fields in API
  - [ ] Add evaluation metrics and feedback logging
  - [ ] Add more real-data integration tests
  - [ ] Automate data parity audits (S3, Postgres, Pinecone)
  - [ ] Optimize pipeline logging
  - [ ] See [BACKLOG.md](./BACKLOG.md) for full list

---

## 3. Development Rules & Workflow
- All work is cloud-only (no local execution).
- All code changes must be tested with real data and committed with documentation updates.
- Use Python 3.11, Poetry, Docker Compose, remote containers.
- All scripts/tests run as modules from project root with `PYTHONPATH=.`
- After each major step: update status, verify outputs, and complete the handoff checklist.
- See [Full Dev Rules](./.DME-SYNC_DEV_RULES.md) for details.

---

## 4. Onboarding & Kickoff Context
- **For new contributors (human or AI):**
  - Read this document fully.
  - Review [README.md](./README.md) for high-level intro and quickstart.
  - See [ONBOARDING_PROMPT_FOR_AI.md](./docs/ONBOARDING_PROMPT_FOR_AI.md) for AI-specific onboarding.
  - Announce your persona and ask for the user's preferred name.
  - Summarize current state and propose your next step before coding.
  - **To run all tests, use the `run_tests.sh` script in the repo root. This ensures the correct environment and import path are set.**

---

## 5. Style, Personality & Collaboration
- **Tone:** Professional, direct, and friendly. Mirror the user's style and maintain a collaborative, transparent spirit.
- **Communication:** All proposals end with 'My Suggestion:' and a clear recommendation.
- **Documentation:** Brevity is valued—summarize challenges and solutions, but link to detailed logs if needed.
- **Culture:** Encourage curiosity, proactive problem-solving, and clear handoffs.

---

## 6. Schema & Architecture
- **Schema:** See [schema_v1.md](./docs/schema_v1.md) for JSONSchema v1.0 and examples.
- **Architecture:** See [architecture.svg](./docs/architecture.svg) (diagram placeholder).
- **Pipeline Steps:**
  1. Discovery & Capture
  2. Normalize & Canonicalize
  3. Relationship Graph
  4. Chunk, Embed, Index
  5. Retrieval Pipeline
  6. Prompt Assembly & LLM Call
  7. Feedback & Monitoring
  8. Security & Compliance
  9. Documentation
- **Runbook:** See [oncall.md](./docs/oncall.md) for troubleshooting and incident response.

---

## 7. Runbook & Troubleshooting
- **Common Issues:** See [oncall.md](./docs/oncall.md)
- **Test Running:** Always use `./run_tests.sh` to run tests. This script sets `PYTHONPATH=src` and runs pytest, preventing import errors. If you encounter import errors, verify you are using this script and that your venv/Poetry environment is active.
- **Dependency Changes:** See [DEPENDENCY_CHANGES.md](./DEPENDENCY_CHANGES.md)
- **Cloud-Only Policy:** See [CLOUD_ONLY_DEVELOPMENT.md](./CLOUD_ONLY_DEVELOPMENT.md)

---

## 7a. Common Pitfalls & Dependency Issues
- **Pinecone Python Package:**
  - The official Pinecone package is now `pinecone` (not `pinecone-client`). If you see errors about missing `pinecone` or deprecation warnings, run:
    ```sh
    poetry remove pinecone-client && poetry add pinecone@latest
    ```
- **Python Version:**
  - The project requires Python 3.12.x. Do not use 3.10 or 3.13+.
  - If you see errors about unsupported Python versions, ensure your Poetry environment is using 3.12 and recreate it if needed.
- **General Troubleshooting:**
  - If you see missing dependency errors, always run `poetry install` and ensure you are using the Poetry-managed environment.
  - If you see import errors for your own modules, make sure to set `PYTHONPATH=src` when running tests or scripts.

Reference this section in onboarding and troubleshooting for all future contributors.

---

## 8. Handoff Checklist
- [ ] What was completed
- [ ] What remains
- [ ] Any blockers or questions

---

## 9. References & Archives
- [README.md](./README.md) — High-level intro, setup, and API usage
- [BACKLOG.md](./BACKLOG.md) — Full backlog and completed tasks
- [CURRENT_STATUS.md](./CURRENT_STATUS.md) — Status at last update
- [.DME-SYNC_DEV_RULES.md](./.DME-SYNC_DEV_RULES.md) — Full dev rules
- [ONBOARDING_PROMPT_FOR_AI.md](./docs/ONBOARDING_PROMPT_FOR_AI.md) — AI onboarding
- [HANDOFF_BRIEF_2025-05-20.md](./docs/HANDOFF_BRIEF_2025-05-20.md) — Last handoff summary
- [schema_v1.md](./docs/schema_v1.md) — Field definitions
- [oncall.md](./docs/oncall.md) — Runbook
- [DEPENDENCY_CHANGES.md](./DEPENDENCY_CHANGES.md) — Dependency history
- [CLOUD_ONLY_DEVELOPMENT.md](./CLOUD_ONLY_DEVELOPMENT.md) — Cloud-only policy
- [RAG-Ready Knowledge-Base Pipeline (v1.1)](./docs/RAG-Ready%20Knowledge-Base%20Pipeline%20(v1.1)) — Pipeline details

---

**This document is the single source of truth for onboarding, development, and handoff. Update it with every major change. Archive detailed logs or legacy docs as needed, but keep this file concise and current.** 