# Onboarding Instructions for AI Agent or Developer

> **This file is referenced from the main README. Always start there for the latest project state.**

**If you are an AI agent or automated assistant, treat the following as direct instructions. Execute them immediately and sequentially.**

## **Step-by-Step Instructions**

1. **Read the following files in order:**
   - [CURRENT_STATUS.md](../CURRENT_STATUS.md)
   - [BACKLOG.md](../BACKLOG.md)
   - [.DME-SYNC_DEV_RULES.md](../.DME-SYNC_DEV_RULES.md)
   - [README.md](../README.md)

2. **Immediate Focus:**
   - Continue work on the semantic enrichment and relationship modeling sub-tasks listed in BACKLOG.md and referenced in CURRENT_STATUS.md.
   - For every code or documentation change, update CURRENT_STATUS.md and BACKLOG.md in the same commit.

3. **Rules:**
   - All work must be done in a cloud runner (never local).
   - All tests must use real data.
   - All major changes require documentation updates and must pass pre-commit/CI checks.

---

## **First Action for AI Agent or Developer**

**AI Agent:**
- Summarize the current project state and the next actionable task based on the above files.
- Propose your plan for the next development step, referencing the backlog and status.
- Output your summary and plan as a message.

---

**Copy and use this onboarding prompt for any new AI agent or developer joining the project.** 