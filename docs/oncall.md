# On-Call Runbook

## Common Issues
- 

## Troubleshooting Steps
- 

## Escalation Contacts
- 

## Neo4j Batching & Retry Logic (Relationship Graph)

- The relationship graph pipeline upserts nodes and relationships to Neo4j in batches (default: 50 records per batch).
- If a transient connection error occurs (e.g., ServiceUnavailable, SessionExpired), the batch is retried up to 3 times with exponential backoff (default: 2s, 4s, 8s).
- All session/transaction management is per-batch for stability.
- Environment variables for tuning:
  - `NEO4J_BATCH_SIZE` (default: 50)
  - `NEO4J_MAX_RETRIES` (default: 3)
  - `NEO4J_RETRY_BACKOFF` (default: 2.0)
- Logs indicate batch progress, errors, and retries. See `relationship_graph.log` for details.
- If persistent errors occur, check Neo4j service health, credentials, and network connectivity. Review logs for skipped batches.

<!-- TODO: Complete runbook for failures and incident response --> 