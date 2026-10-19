# Smart Campus Lost-and-Found Network

An AI-assisted, privacy-preserving campus lost-and-found system featuring explainable multimodal retrieval, evidence-based claim verification, single-use expiring handover desk codes, immutable audit logging, and empirical benchmark evaluation.

---

## 1. Overview
The platform combines a reliable campus operational workflow with a controlled retrieval research framework:
* **Product:** Privacy-safe found item listings, hierarchical campus location tree, safe image pipeline (magic byte verification, pixel guards, EXIF metadata stripping, 64-bit dHash duplicate detection), moderator claim locks, single-use 8-character handover codes (HMAC-SHA256, 5-attempt lock, 48-hour expiry), transactional outbox notifications, and retention rules.
* **Research:** Controlled evaluation comparing BM25 keyword search, text embeddings (`all-MiniLM-L6-v2`), CLIP ViT-B/32 image embeddings, hand-weighted hybrid, and learned fusion across 400 benchmark items with bootstrap confidence intervals and paired hypothesis testing ($H_1$).

---

## 2. Project Architecture & Directory Layout

```
.
├── backend/                  # FastAPI application & workers
│   ├── app/
│   │   ├── api/              # Thin HTTP routers (health, auth, reports, claims, etc.)
│   │   ├── core/             # Configuration, database session, security middleware
│   │   ├── domain/           # Pure domain logic (scoring, lifecycle, PII, metrics)
│   │   ├── models/           # SQLAlchemy database models
│   │   ├── schemas/          # Strict Pydantic schemas (extra="forbid")
│   │   └── worker/           # Background async worker (FOR UPDATE SKIP LOCKED)
│   ├── alembic/              # Database migrations (including pgvector extension)
│   ├── tests/                # Automated pytest suite (named after AC IDs)
│   └── Dockerfile
├── frontend/                 # React 18 + TypeScript + Vite SPA
│   ├── src/                  # Components, design system, API client
│   ├── nginx.conf            # Reverse proxy configuration
│   └── Dockerfile
├── eval/                     # Offline benchmark generator, metrics, data card
├── docs/                     # Architecture, ER diagram, learning logs, test plans
├── docker-compose.yml        # Multi-container orchestration (db, backend, worker, frontend, mail)
├── .env.example              # Environment variable template
├── DECISIONS.md              # Architectural Decisions Log (D-01 through D-17)
└── README.md
```

---

## 3. Quick Start (Walking Skeleton)

### Prerequisites
* Docker & Docker Compose (or local Python 3.12+ and Node.js 20+)
* Git

### Running with Docker Compose
1. Copy the environment configuration:
   ```bash
   cp .env.example .env
   ```
2. Build and launch all services:
   ```bash
   docker compose up -d --build
   ```
3. Open the applications in your browser:
   * **Web Application:** `http://localhost:8080`
   * **Backend API Docs:** `http://localhost:8000/docs`
   * **Mailpit (Email Catcher):** `http://localhost:8025`

### Running Locally for Development

#### Backend
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Or on Windows: .\.venv\Scripts\activate
pip install -r requirements.txt
pytest -v
```

#### Frontend
```bash
cd frontend
npm install
npm run dev
```

---

## 4. Verification and Quality Checks

```bash
# Backend Quality Checks
cd backend
ruff check .
mypy .
pytest -v

# Frontend Quality Checks
cd frontend
npm run lint
npx tsc --noEmit
```

---

## 5. Known Limitations
1. **AI is Advisory:** Match scores are strictly suggestions for human review. No match score ever alters a report or claim status automatically.
2. **Synthetic Benchmark:** Benchmark text and spatial/temporal noise are generated synthetically; empirical results do not prove real-world recovery gains on living campus deployments without pilot field testing.
3. **Email Deliverability:** Self-hosted development environments use Mailpit; production SMTP deliverability depends on institutional DKIM/SPF network policies.
4. **Data Minimization:** No GPS or indoor positioning tracking is used; campus locations use hierarchical topological trees and building adjacency.
