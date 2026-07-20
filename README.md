# RAG-as-a-Service — Multi-Tenant Retrieval-Augmented Generation Platform

A production-shaped API platform where tenants sign up, create projects, upload PDFs, and
query them through a hybrid-retrieval RAG pipeline with model fallback, usage quotas, and
observability. Built to be **free-to-run** for a portfolio/demo deployment while following
patterns you'd defend in a system-design interview.

---
![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-green)
![Docker](https://img.shields.io/badge/Docker-ready-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)
## 1. Architecture

```
                          ┌─────────────────┐
                          │  Streamlit       │  admin dashboard (login, upload,
                          │  Dashboard       │  ingestion status, test queries)
                          └────────┬─────────┘
                                   │ HTTPS (same public API contract as any client)
                                   ▼
                          ┌─────────────────┐        ┌──────────────┐
                          │  FastAPI API     │──────▶ │  PostgreSQL   │ tenants, users,
                          │  (/api/v1)       │        │  (or Supabase)│ projects, documents,
                          │  JWT auth, rate  │        └──────────────┘ jobs, logs, audit
                          │  limit, quotas   │
                          └───┬─────────┬────┘
                              │         │
                enqueue job   │         │  publish metrics
                              ▼         ▼
                    ┌──────────────┐  ┌────────────┐
                    │ Redis /      │  │ Prometheus │──▶ Grafana dashboards
                    │ Celery       │  └────────────┘
                    │ broker       │
                    └──────┬───────┘
                           ▼
                  ┌─────────────────┐        ┌──────────────┐
                  │  Celery Worker   │───────▶│   Qdrant      │ vector index
                  │  extract→chunk→  │        │ (per-project  │ (dense + payload
                  │  embed→index     │        │  collection)  │  for keyword filter)
                  └─────────────────┘        └──────────────┘

Query path: API → hybrid_search (Qdrant dense + keyword) → rerank hook →
prompt assembly → provider_router (Gemini primary, circuit breaker,
Llama 3 fallback) → cached in Redis → response with cited source chunks.
```

**Why this shape:** the API never does heavy CPU/IO work (PDF parsing, embedding) inline —
that's Celery's job, so upload requests return in milliseconds and retries/backoff live in
one place. The vector store is wrapped behind `services/vector_store.py` so Qdrant could be
swapped for Pinecone/pgvector without touching routers or the ingestion task. The LLM call
is wrapped behind `services/provider_router.py` so Gemini and Llama are interchangeable and
a provider outage degrades the answer quality, not availability.

### Domain layers
`auth` · `tenants` · `projects` · `documents` (+ versioning) · `ingestion_jobs` ·
`retrieval` (hybrid search + rerank hook) · `generation` (provider router) ·
`evaluation` (RAGAS) · `monitoring` (Prometheus/Grafana)

---

## 2. Database schema (Postgres / Supabase-compatible)

| Table | Purpose | Key columns |
|---|---|---|
| `tenants` | top-level workspace | `id`, `name`, `plan` |
| `users` | tenant members | `id`, `tenant_id`, `email`, `hashed_password`, `role` |
| `projects` | isolated RAG namespace, maps 1:1 to a Qdrant collection | `id`, `tenant_id`, `qdrant_collection`, `daily_query_quota` |
| `documents` | uploaded PDFs | `id`, `project_id`, `storage_path`, `status`, `current_version` |
| `document_versions` | re-upload history for rollback/diff | `id`, `document_id`, `version_number`, `checksum` |
| `ingestion_jobs` | async pipeline state machine | `id`, `document_id`, `status`, `attempt`, `chunks_indexed`, `error_message` |
| `query_logs` | usage tracking, token estimates, latency | `id`, `project_id`, `user_id`, `provider_used`, `latency_ms` |
| `audit_logs` | append-only sensitive-action trail | `id`, `tenant_id`, `actor_user_id`, `action`, `resource_type` |

All tenant-scoped tables carry `tenant_id` (directly or via `project_id`) and every query
filters on it — that's the multi-tenancy boundary, enforced in the service layer today and
a natural fit for Postgres Row-Level Security later if you migrate to Supabase auth.

---

## 3. Key API endpoints (`/api/v1`)

```
POST   /auth/register                      create tenant + owner user, returns tokens
POST   /auth/login                         returns access + refresh tokens
POST   /auth/refresh                       rotate access token

POST   /projects                           create project (provisions Qdrant collection)
GET    /projects                           list tenant's projects

POST   /projects/{id}/documents            upload PDF, enqueues ingestion job
GET    /projects/{id}/documents            list documents + status
GET    /projects/{id}/documents/{doc}/status   poll ingestion job state

POST   /projects/{id}/query                hybrid-search + generate answer with citations

GET    /health/live | /health/ready        liveness/readiness probes
GET    /metrics                            Prometheus scrape endpoint
```

---

## 4. Background job flow (Celery)

```
uploaded → queued → extracting → chunking → embedding → indexing → done
                                                              ↘ failed (after max_attempts)
```
Each transition is written to `ingestion_jobs` so the dashboard polls real state, not a
guess. Failures use Celery's `autoretry`/`self.retry` with backoff; after 3 attempts the
job and document are marked `failed` and counted in the `ingestion_jobs_failed_total`
Prometheus metric so failures are visible on the Grafana board, not just in logs.

---

## 5. Deployment architecture

- **Local / free tier:** `docker-compose up` runs Postgres, Redis, Qdrant, API, worker,
  dashboard, Prometheus, Grafana on a single machine or a free-tier VM.
- **Cost-aware swap-ins:** replace the `postgres` service with a Supabase project
  (just change `DATABASE_URL`), use Qdrant Cloud's free tier or keep it self-hosted, and
  run Llama 3 fallback locally via Ollama instead of a paid endpoint.
- **Path to cloud:** each service is already a separate Dockerfile/image, so API and
  worker deploy independently on ECS/Cloud Run/Fly.io, Postgres moves to managed
  Supabase/RDS, and Qdrant moves to Qdrant Cloud — no code changes, only environment
  variables and a registry push step in CI (stubbed in `.github/workflows/ci.yml`).
- Horizontal scaling knobs: add more `worker` replicas for ingestion throughput; API is
  stateless behind any load balancer since JWTs carry auth state.

---

## 6. Cost-conscious design decisions

- Local `sentence-transformers` embeddings by default — zero marginal cost per chunk.
- Gemini is primary for generation quality; Llama 3 (local/self-hosted) is the fallback,
  which also caps worst-case spend if Gemini rate-limits you.
- Redis-backed response cache on `(project_id, question)` avoids paying for repeated
  identical questions — usually the single biggest cost lever in a RAG demo.
- Per-project daily query quotas prevent a runaway loop (or an unauthenticated leak)
  from generating a surprise bill.

---

## 7. Running locally

```bash
cp .env.example .env               # fill in GEMINI_API_KEY if you want live generation
docker compose up --build
# API:        http://localhost:8000/docs
# Dashboard:  http://localhost:8501
# Grafana:    http://localhost:3000
# Prometheus: http://localhost:9090

# first-time DB migration
docker compose exec api alembic upgrade head
```

To use **Supabase** instead of local Postgres: create a project, copy its connection
string into `DATABASE_URL` in `.env`, remove the `postgres` service from
`docker-compose.yml`, and run the same `alembic upgrade head` step pointed at Supabase.

---

## 8. Interview talking points

- **Multi-tenancy boundary:** every table is scoped by `tenant_id`/`project_id`; explain
  the tradeoff between shared-schema-with-tenant-column (chosen here, cheap, works at this
  scale) vs. schema-per-tenant or DB-per-tenant (better isolation, more ops overhead).
- **Why Celery, not inline processing:** PDF parsing + embedding is unpredictable in
  duration and can fail transiently — decoupling it means the upload endpoint stays fast
  and failures are retryable without re-uploading.
- **Provider router + circuit breaker:** be ready to explain why a circuit breaker beats
  naive per-request retries — it stops hammering a degraded provider and gives it a
  cooldown window before trying again, versus retrying every request individually.
- **Hybrid retrieval:** dense embeddings catch semantic matches, keyword/full-text catches
  exact terms (IDs, names, acronyms) that embeddings often miss — explain the weighted
  merge and where a real cross-encoder reranker would slot in.
- **RAGAS in CI:** treats retrieval/generation quality as a regression-testable property,
  not a one-time eyeball check — explain faithfulness vs. answer relevancy vs. context
  precision/recall and why each catches a different failure mode.
- **Observability:** Prometheus histograms give p95/p99 latency, not just averages;
  explain why queue depth and ingestion failure rate are the two leading indicators of a
  RAG pipeline falling over before users notice.

---

## 9. Resume bullet points

- Designed and built a multi-tenant RAG-as-a-Service platform (FastAPI, Celery, Qdrant,
  PostgreSQL) supporting async PDF ingestion, hybrid dense+keyword retrieval, and
  citation-backed answer generation.
- Implemented a provider-fallback router with circuit-breaker logic between Gemini and a
  self-hosted Llama 3, keeping the query path available through upstream API outages or
  rate limits.
- Built an async ingestion pipeline (Celery + Redis) with per-stage status tracking,
  automatic retries, and failure alerting, processing PDF extraction, chunking, embedding,
  and vector indexing.
- Integrated RAGAS evaluation (faithfulness, relevancy, context precision/recall) into
  GitHub Actions CI to gate merges on retrieval/generation quality regressions.
- Added Prometheus/Grafana observability covering request latency, queue depth, and
  ingestion failure rate; instrumented JWT auth with access/refresh tokens, role-based
  access, and per-project rate limiting and usage quotas.
- Reduced generation cost by ~majority of repeat traffic via a Redis response cache and
  local embedding models, with an explicit cost-aware architecture for free-tier
  deployment (Supabase/Qdrant Cloud/Ollama-compatible).

---

## 10. What's intentionally left as a stub / next step

- Reranker (`services/retrieval.py::rerank`) — currently a no-op; swap in a cross-encoder.
- Object storage for uploaded PDFs is local disk (`UPLOAD_DIR`) — swap for S3/GCS/Supabase
  Storage behind the same `storage_path` field for real multi-instance deployments.
- Alembic has the environment wired but no initial revision generated — run
  `alembic revision --autogenerate -m "init"` once models stabilize for your fork.
- CI's `build-and-push` job builds images but doesn't push — wire in your registry.
