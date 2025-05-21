
# CLOUD_ONLY_DEVELOPMENT.md

**Policy Version:** 1.0  
**Last updated:** 2025-05-21

DME Sync is **100 % cloud‑native**. All coding, testing, and data processing
**must occur in managed remote environments** — never on a developer’s local
machine.

---
## Why Cloud‑Only?

* **Data security** — student data & embeddings never land on unsecured laptops.  
* **Parity** — everyone runs the same container images & infra; “works on my
  machine” is impossible.  
* **Scalability** — heavy embedding jobs rely on GPU nodes unavailable
  locally.  
* **Auditability** — CI/CD logs every build, test, and deployment.

---
## Approved Environments

| Environment | Purpose |
|-------------|---------|
| GitHub Codespaces | Day‑to‑day dev container |
| Remote Docker (+ VS Code dev‑container) | Self‑hosted alternative |
| AWS ECS “dev” cluster | Long‑running NLP / crawling jobs |
| GitHub Actions | CI, nightly indexing |

---
## Prohibited

* Running `poetry install` or databases on a local OS.  
* Local copies of production `.env` or datasets.  
* Direct laptop → Pinecone traffic; always tunnel through the container.

---
## Secrets Handling

* Placeholders live in `.env.template`.  
* Real values injected via GitHub Secrets or AWS Parameter Store.  
* Containers mount `/secrets` (tmpfs) at runtime and delete on exit.

---
## Enforcement

* Pre‑commit hook aborts if `$(pwd)` is not `/workspaces/*` or `/workspace`.  
* CI job “local‑lint” scans PRs for committed secrets or large binary blobs.  
* Violations trigger Slack alert to `#dme-sync-maintainers`.

---
## FAQ

**Q:** Can I test a quick script locally?  
**A:** Spin up `docker compose` in Codespaces or use the lightweight
“dev‑mini” container; do not bypass the policy.

**Q:** Offline travel coding?  
**A:** Not supported. Create a PR with description “offline work needed”, the
maintainer will approve a temporary local exemption and provide sanitized
dummy data.
