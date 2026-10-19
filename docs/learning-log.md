# Learning Log

This log tracks the build rationale, architectural decisions, failure modes, and self-assessment quiz questions for each development step to prepare for the oral viva.

---

## Step 1: Walking Skeleton & Repository Foundation
* **Acceptance Criteria:** AC-131 (start), AC-138 (skeleton)
* **What was built:**
  * Multi-service project skeleton: `backend` (FastAPI modular monolith), `frontend` (React + TypeScript), `worker` (async job runner), and `eval` (evaluation package).
  * PostgreSQL setup with `pgvector` extension and initial migration scaffolding via Alembic.
  * Health check endpoint `/api/health` reporting database connectivity and worker status.
  * Docker Compose configuration with `db`, `backend`, `worker`, `frontend`, and Mailpit mail catcher.
  * Continuous Integration (CI) configuration for automated linting, typechecking, and test execution.
* **Why it is designed that way:**
  * Having a functional "walking skeleton" that runs end-to-end from day one proves containerization, database drivers, vector extensions, and inter-service networking before adding domain complexity.
  * The pure domain package separation (`app/domain`) isolates mathematical and business rules from frameworks and ORMs, keeping business logic cleanly testable without mocks.
* **One thing that could go wrong:**
  * If the PostgreSQL container initializes before the `pgvector` extension is installed or enabled, vector columns and HNSW indexes will fail during migration execution (`UndefinedObjectError`).
* **Quiz Questions (for viva preparation):**
  1. *Why is `pgvector` chosen over a standalone external vector database (like Pinecone or Qdrant) for this campus system?*
  2. *What is the purpose of the `/api/health` endpoint in a containerized environment, and why should it probe both the database and background worker?*
  3. *Why does the architecture separate pure domain logic from FastAPI router and database models?*
