<!-- README.md -->
<div align="center">
  <h1>🚀 RAG-as-a-Service Platform</h1>
  <p><strong>Production-Grade Multi-Tenant Retrieval-Augmented Generation</strong></p>
  
  ![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
  ![FastAPI](https://img.shields.io/badge/FastAPI-0.115.0-green)
  ![Docker](https://img.shields.io/badge/Docker-ready-blue)
  ![License](https://img.shields.io/badge/License-MIT-yellow)
  ![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen)
  
  <p>
    <a href="#-features">Features</a> •
    <a href="#-architecture">Architecture</a> •
    <a href="#-quick-start">Quick Start</a> •
    <a href="#-api-endpoints">API</a> •
    <a href="#-deployment">Deployment</a> •
    <a href="#-interview-talking-points">Interview Prep</a>
  </p>
</div>

---

## 📖 Table of Contents

- [🎯 Why This Project?](#-why-this-project)
- [✨ Features](#-features)
- [🏗️ Architecture](#️-architecture)
- [📁 Repository Structure](#-repository-structure)
- [🛠️ Tech Stack](#️-tech-stack)
- [🚀 Quick Start](#-quick-start)
- [📋 API Endpoints](#-api-endpoints)
- [🗄️ Database Schema](#️-database-schema)
- [📊 Monitoring](#-monitoring)
- [💰 Cost-Conscious Design](#-cost-conscious-design)
- [🔐 Security](#-security)
- [🤝 Contributing](#-contributing)
- [📄 License](#-license)
- [💼 Interview Talking Points](#-interview-talking-points)
- [📝 Resume Bullet Points](#-resume-bullet-points)

---

## 🎯 Why This Project?

This project demonstrates a **production-grade RAG (Retrieval-Augmented Generation) platform** built with enterprise patterns and interview-ready design decisions.

### Key Highlights:
- ✅ **Multi-tenancy** with JWT authentication and role-based access
- ✅ **Hybrid search** (dense + sparse vectors) for better retrieval
- ✅ **Cost-aware architecture** with local embeddings and LLM fallback
- ✅ **Async document processing** with Celery + Redis
- ✅ **Full observability** with Prometheus + Grafana
- ✅ **RAGAS evaluation** in CI/CD pipeline
- ✅ **Ready for cloud deployment** (AWS/GCP/Fly.io)

### What Makes This Special:
- **Interview-ready**: Every architectural decision has a clear trade-off explanation
- **Free to run**: Use local models and embeddings to avoid API costs
- **Production patterns**: Circuit breakers, retries, health checks, and monitoring
- **Portfolio-ready**: Complete documentation, tests, and deployment scripts

---

## ✨ Features

### Core Capabilities

| Feature | Description |
|---------|-------------|
| **Multi-Tenancy** | Isolated workspaces with JWT authentication |
| **Hybrid Search** | Dense (semantic) + Sparse (keyword) retrieval |
| **Async Ingestion** | Celery-powered PDF processing with retries |
| **LLM Fallback** | Gemini primary → Llama 3 fallback with circuit breaker |
| **Response Caching** | Redis cache for repeated queries |
| **Usage Quotas** | Per-project daily query limits |
| **RAGAS Evaluation** | Faithfulness, relevancy, context precision/recall |
| **Monitoring** | Prometheus metrics + Grafana dashboards |

### Technical Capabilities

```mermaid
graph LR
    A[User Query] --> B[FastAPI]
    B --> C[Hybrid Search]
    C --> D[Qdrant]
    D --> E[Context Retrieved]
    E --> F[LLM Router]
    F --> G[Gemini Primary]
    F --> H[Llama 3 Fallback]
    G --> I[Answer + Citations]
    H --> I

┌─────────────────────────────────────────────────────────────────────┐
│                    RAG Platform Architecture                        │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐          │
│  │  Streamlit   │───▶│   FastAPI    │───▶│   Qdrant     │          │
│  │  Dashboard   │    │   Backend    │    │  Vector DB   │          │
│  └──────────────┘    └──────────────┘    └──────────────┘          │
│         │                   │                    │                   │
│         │                   ▼                    │                   │
│         │            ┌──────────────┐            │                   │
│         │            │  PostgreSQL  │            │                   │
│         │            │  (Metadata)  │            │                   │
│         │            └──────────────┘            │                   │
│         │                   │                    │                   │
│         │                   ▼                    │                   │
│         │            ┌──────────────┐            │                   │
│         │            │   Celery     │            │                   │
│         │            │   Worker     │            │                   │
│         │            └──────────────┘            │                   │
│         │                   │                    │                   │
│         │                   ▼                    │                   │
│         │            ┌──────────────┐            │                   │
│         │            │   Ollama     │            │                   │
│         │            │  Llama 3.2   │            │                   │
│         │            └──────────────┘            │                   │
│         │                                         │                   │
│         └────────────────┬────────────────────────┘                   │
│                          │                                             │
│                    ┌──────────────┐                                  │
│                    │   Grafana    │                                  │
│                    │  Monitoring  │                                  │
│                    └──────────────┘                                  │
└─────────────────────────────────────────────────────────────────────┘


auth/          → JWT, refresh tokens, role-based access
tenants/       → Multi-tenant isolation
projects/      → RAG namespaces, Qdrant collections
documents/     → Upload, versioning, status tracking
ingestion/     → Async pipeline with retries
retrieval/     → Hybrid search + reranking
generation/    → Provider router with fallback
evaluation/    → RAGAS metrics
monitoring/    → Prometheus + Grafana

sequenceDiagram
    participant User
    participant API
    participant Celery
    participant Qdrant
    participant Ollama

    User->>API: Upload PDF
    API->>Celery: Queue ingestion
    API-->>User: 202 Accepted

    Celery->>Celery: Extract text
    Celery->>Celery: Chunk document
    Celery->>Celery: Generate embeddings
    Celery->>Qdrant: Index vectors
    Celery-->>API: Update status

    User->>API: Query
    API->>Qdrant: Hybrid search
    Qdrant-->>API: Retrieved chunks
    API->>Ollama: Generate answer
    Ollama-->>API: Response
    API-->>User: Answer + Citations

rag-platform/
├── api/                         # FastAPI Backend
│   ├── app/
│   │   ├── api/v1/              # Route handlers
│   │   │   ├── auth.py          # JWT authentication
│   │   │   ├── projects.py      # Project CRUD
│   │   │   ├── documents.py     # Document upload
│   │   │   └── query.py         # RAG queries
│   │   ├── core/                # Core functionality
│   │   │   ├── config.py        # Settings
│   │   │   ├── security.py      # Auth logic
│   │   │   └── database.py      # DB connection
│   │   ├── models/              # SQLAlchemy models
│   │   │   ├── tenant.py
│   │   │   ├── user.py
│   │   │   └── document.py
│   │   └── services/            # Business logic
│   │       ├── vector_store.py  # Qdrant wrapper
│   │       ├── provider_router.py # LLM routing
│   │       └── retrieval.py     # Hybrid search
│   ├── requirements.txt
│   ├── Dockerfile
│   └── alembic.ini
│
├── dashboard/                   # Streamlit Admin UI
│   ├── app.py
│   ├── requirements.txt
│   └── Dockerfile
│
├── worker/                      # Celery Tasks
│   ├── tasks/
│   │   ├── ingestion.py         # PDF processing
│   │   └── maintenance.py       # Scheduled tasks
│   ├── Dockerfile
│   └── requirements.txt
│
├── eval/                        # RAGAS Evaluation
│   ├── ragas_eval.py
│   ├── dataset.json
│   └── requirements.txt
│
├── monitoring/                  # Observability
│   ├── grafana/
│   │   └── dashboard.json       # Pre-configured dashboards
│   └── prometheus.yml
│
├── shared/                      # Shared utilities
│   └── schemas/
│
├── .github/
│   └── workflows/
│       ├── ci.yml               # GitHub Actions CI
│       └── cd.yml               # Deployment pipeline
│
├── docker-compose.yml           # Multi-container setup
├── .env.example                 # Environment template
├── README.md                    # This file
└── LICENSE                      # MIT License

Access Services
Service	URL	Credentials
Dashboard	http://localhost:8501	Register new user
API Docs	http://localhost:8000/docs	-
Grafana	http://localhost:3000	admin/admin
Prometheus	http://localhost:9090	-
Qdrant UI	http://localhost:6333/dashboard	-
Pull Llama 3 (Optional)
bash
# Pull the model for local LLM
docker-compose exec ollama ollama pull llama3.2:1b

# Test it
docker-compose exec ollama ollama run llama3.2:1b "Hello"
📋 API Endpoints
Authentication
text
POST /api/v1/auth/register     - Register new user
POST /api/v1/auth/login        - Login with email/password
POST /api/v1/auth/refresh      - Refresh JWT token
Projects
text
POST /api/v1/projects          - Create project
GET  /api/v1/projects          - List projects
GET  /api/v1/projects/{id}     - Get project details
Documents
text
POST /api/v1/documents/upload  - Upload PDF
GET  /api/v1/documents/{id}    - Get document status
GET  /api/v1/documents         - List documents
Search
text
POST /api/v1/search            - Hybrid search
POST /api/v1/search/chat       - Chat with RAG
Health
text
GET  /health/live              - Liveness check
GET  /health/ready             - Readiness check
GET  /metrics                  - Prometheus metrics
💰 Cost-Conscious Design
Component	Free Option
Embeddings	Local sentence-transformers ($0)
LLM	Ollama (Llama 3) ($0)
Database	PostgreSQL (Docker) or Supabase (free)
Vector DB	Qdrant (Docker) ($0)
Hosting	Local or free-tier VM
Key savings features:

✅ Response caching for repeated queries

✅ Local embeddings (no API cost)

✅ LLM fallback uses free models

🔐 Security
JWT authentication with short-lived tokens

Multi-tenant isolation

Password hashing with bcrypt

Rate limiting per API key

Audit logging for sensitive actions

🤝 Contributing
Fork the repository

Create a feature branch (git checkout -b feature/amazing)

Commit your changes (git commit -m 'Add feature')

Push to the branch (git push origin feature/amazing)

Open a Pull Request

📄 License
MIT License - see LICENSE file for details.

📫 Contact
GitHub: Shayaritd/rag-platform

Issues: Open an issue

<div align="center"> Built with ❤️ by Shayari Gowda </div> ```
