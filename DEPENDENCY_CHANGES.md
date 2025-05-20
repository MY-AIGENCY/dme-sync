## [2025-05-20] Pinecone Hybrid Blocker
- **Change:** Attempted to upgrade to pinecone-client >=3.0 for hybrid index support.
- **Reason:** Pinecone-client >=3.0 only supports Python <3.13. Current environment is Python 3.13.x.
- **Impact:** Hybrid index and in-cluster embedding features are unavailable. Must use legacy pipeline or downgrade Python.
- **Next Steps:** Monitor Pinecone releases for 3.13+ support, or set up a Python 3.12.x environment for hybrid features. 