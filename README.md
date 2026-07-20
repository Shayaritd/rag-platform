# 🚀 RAG Platform

> A production-inspired Retrieval-Augmented Generation (RAG) platform that enables users to upload documents, perform semantic search, and generate context-aware answers using Large Language Models.

![Python](https://img.shields.io/badge/Python-3.11+-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-green)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-blue)
![Qdrant](https://img.shields.io/badge/Qdrant-red)
![Redis](https://img.shields.io/badge/Redis-red)
![Docker](https://img.shields.io/badge/Docker-blue)
![License](https://img.shields.io/badge/License-MIT-yellow)

---

# 📌 Overview

This project implements an end-to-end Retrieval-Augmented Generation (RAG) pipeline for enterprise document search. Users can upload PDFs, process them asynchronously, store embeddings in Qdrant, and query documents using semantic search powered by local or cloud LLMs.

The project follows production-ready backend practices including authentication, asynchronous processing, vector search, caching, monitoring, and containerized deployment.

---

# ✨ Features

- 🔐 JWT Authentication & Authorization
- 🏢 Multi-Tenant Workspace Support
- 📂 Project-Based Document Management
- 📄 PDF Upload & Processing
- ⚡ Asynchronous Ingestion with Celery
- 🧩 Intelligent Text Chunking
- 🧠 Embedding Generation
- 🔍 Semantic Search using Qdrant
- 🤖 RAG-based Question Answering
- 🔄 LLM Provider Routing & Fallback
- ⚡ Redis Response Caching
- 📊 Prometheus & Grafana Monitoring
- 🐳 Docker & Docker Compose
- 📡 REST API with FastAPI
- ❤️ Health Check Endpoints
- 🚀 CI/CD Ready

---

# 🛠 Tech Stack

| Category | Technology |
|-----------|------------|
| Backend | FastAPI |
| Database | PostgreSQL |
| Vector Database | Qdrant |
| ORM | SQLAlchemy |
| Authentication | JWT |
| Queue | Celery |
| Cache | Redis |
| Embeddings | Sentence Transformers |
| LLM | Ollama / Gemini |
| Monitoring | Prometheus, Grafana |
| Containerization | Docker |

---

# 🏗 Architecture

```text
                    Client
                      │
                      ▼
                 FastAPI API
                      │
        ┌─────────────┼─────────────┐
        │             │             │
        ▼             ▼             ▼
 PostgreSQL        Redis        Celery Worker
 Metadata          Cache      PDF Processing
                                      │
                                      ▼
                           Sentence Transformer
                                      │
                                      ▼
                                   Qdrant
                                      │
                                      ▼
                              Ollama / Gemini
                                      │
                                      ▼
                               Generated Answer
```

---

# 🔄 RAG Workflow

```text
Upload PDF
     │
     ▼
Extract Text
     │
     ▼
Chunk Document
     │
     ▼
Generate Embeddings
     │
     ▼
Store in Qdrant
─────────────────────────────
User Question
     │
     ▼
Generate Query Embedding
     │
     ▼
Semantic Search
     │
     ▼
Retrieve Relevant Chunks
     │
     ▼
LLM
     │
     ▼
Grounded Answer
```

---

# 📁 Project Structure

```text
rag-platform/

├── api/                 # FastAPI backend
├── worker/              # Celery background workers
├── dashboard/           # Streamlit dashboard
├── monitoring/          # Prometheus & Grafana
├── eval/                # RAG evaluation
├── shared/              # Shared utilities
├── docker-compose.yml
├── .env.example
└── README.md
```

---

# 🚀 Getting Started

### Clone Repository

```bash
git clone https://github.com/Shayaritd/rag-platform.git

cd rag-platform
```

### Start Services

```bash
docker compose up --build
```

### API Documentation

```
http://localhost:8000/docs
```

---

# 📡 API Endpoints

## Authentication

```
POST /auth/register
POST /auth/login
POST /auth/refresh
```

## Projects

```
POST /projects
GET  /projects
GET  /projects/{id}
DELETE /projects/{id}
```

## Documents

```
POST /documents/upload
GET  /documents
GET  /documents/{id}
```

## Chat

```
POST /chat
```

## Health

```
GET /health
GET /metrics
```

---

# 🔐 Security

- JWT Authentication
- Password Hashing
- Multi-Tenant Isolation
- Role-Based Access
- API Validation
- Rate Limiting
- Secure Environment Variables

---

# 📊 Monitoring

- Prometheus Metrics
- Grafana Dashboards
- Health Checks
- Worker Status
- Request Monitoring

---

# ⚙️ Design Decisions

### Why FastAPI?

- High-performance ASGI framework
- Automatic OpenAPI documentation
- Async support
- Type-safe request validation

### Why PostgreSQL?

- Stores users, projects, and metadata
- ACID compliance
- Reliable relational database

### Why Qdrant?

- Optimized vector similarity search
- Metadata filtering
- Scalable collections

### Why Redis?

- Celery broker
- Response caching
- High-performance in-memory storage

### Why Celery?

- Non-blocking document processing
- Retry support
- Scalable background workers

### Why Ollama?

- Local inference
- No API cost
- Privacy-focused deployment

---

# 📈 Future Improvements

- Streaming Responses
- BM25 + Dense Hybrid Retrieval
- Document Versioning
- Cross-Encoder Re-ranking
- Multi-Modal Document Support
- Kubernetes Deployment
- Auto Scaling
- Fine-Tuned Models

---

# 💼 Interview Talking Points

This project demonstrates experience with:

- Retrieval-Augmented Generation (RAG)
- Vector Databases
- Semantic Search
- Large Language Models
- FastAPI Backend Development
- Asynchronous Processing
- Docker & Containerization
- JWT Authentication
- System Design
- REST API Development
- PostgreSQL
- Redis
- Celery
- Monitoring & Observability
- Production-Oriented Backend Architecture

---

# 📄 License

This project is licensed under the MIT License.

---

<div align="center">

**⭐ If you found this project useful, consider giving it a star!**

Built with ❤️ by **Shayari Gowda**

</div>
