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

---

## Step 2: Accounts, Roles, Sessions, Security & Audit Writer
* **Acceptance Criteria:** AC-01 to AC-16, AC-131
* **What was built:**
  * User registration restricted to allowed campus email domains (`@campus.edu`, `@student.campus.edu`), Argon2id password hashing, and case-insensitive email normalization.
  * Cryptographically secure email verification tokens with single-use consumption, 24-hour expiry, and HTTP 410 Gone on reuse or expiration.
  * Session-based authentication stored in PostgreSQL with 64-character hex tokens transmitted via `HttpOnly`, `SameSite=Lax`, `Secure` cookies.
  * Timing-attack mitigation via `verify_dummy_password` and rate limiting (5 failed attempts per 15-minute window per IP/email).
  * Strict double-submit CSRF protection requiring `X-CSRF-Token` on state-changing methods (POST, PUT, PATCH, DELETE).
  * TLS enforcement rejecting unencrypted non-localhost traffic with 403 `tls_required`.
  * Role-based access control matrix (anonymous, user, moderator, admin) and anti-enumeration resource ownership checks returning HTTP 404 instead of 403.
  * Strict schema parsing (`extra="forbid"`) rejecting unexpected payload fields with HTTP 422.
  * Security response headers (Content-Security-Policy, X-Content-Type-Options: nosniff, X-Frame-Options: DENY), request body size limiting (1MB max), and immutable audit log data model.
* **Why it is designed that way:**
  * Argon2id provides state-of-the-art resistance against GPU/ASIC offline dictionary attacks.
  * Returning HTTP 404 instead of 403 on private resources prevents malicious users from discovering whether an ID exists (anti-enumeration).
  * Enforcing `extra="forbid"` on Pydantic schemas prevents mass-assignment vulnerabilities where attackers inject administrative flags into user payloads.
* **One thing that could go wrong:**
  * If the rate-limiting key relies exclusively on client IP, a campus network where thousands of students share an egress NAT gateway could lead to collective denial-of-service; indexing rate limits by composite `(IP, email)` protects legitimate users while throttling targeted attacks.
* **Quiz Questions (for viva preparation):**
  1. *How does verifying a dummy password hash protect against timing attacks during authentication, and why is constant-time execution critical?*
  2. *Why does the access control layer return HTTP 404 (Not Found) rather than HTTP 403 (Forbidden) when a user attempts to access a resource belonging to someone else?*
  3. *Why are session tokens kept in `HttpOnly` cookies rather than `localStorage`, and how does double-submit CSRF defense work with them?*

---

## Step 3: Campus Locations and Adjacency
* **Acceptance Criteria:** AC-17 to AC-20
* **What was built:**
  * Hierarchical location model (`campus_locations`) supporting 5 distinct levels (`campus`, `building`, `floor`, `room`, `area`), parent pointers, optional coordinates stored rounded to 3 decimal places (`NUMERIC(8, 3)`), and case-insensitive sibling uniqueness index `uq_locations_parent_name_ci`.
  * Symmetric building adjacency table (`location_adjacency`) linking adjacent buildings with distinct checks.
  * Tree hierarchy cycle detection preventing any node from becoming its own ancestor (HTTP 422 `cannot_become_own_ancestor`).
  * Administrative endpoints for tree CRUD, delete protection on in-use locations (HTTP 409), and adjacency pairing.
  * Pure domain location scoring function `calculate_location_score` in `backend/app/domain/location.py` [LEARN] implementing the exact scoring matrix: identical (1.0), ancestor (0.8), lowest common ancestor floor/area (0.7), building (0.6), adjacent buildings (0.5), same campus (0.2), different campus (0.0), and missing location (`null`).
* **Why it is designed that way:**
  * Physical campus environments feature multi-story buildings and indoor rooms where GPS signals degrade or lack vertical resolution; a discrete hierarchical tree paired with building adjacency reflects real-world proximity accurately.
  * Isolating `calculate_location_score` as a pure function with zero database or framework dependencies keeps mathematical scoring lightning-fast, reproducible, and testable without database overhead.
  * Missing locations return `null` (None) rather than `0.0` so the hybrid matching engine can normalize weights across active signals instead of unfairly penalizing reports without indoor details.
* **One thing that could go wrong:**
  * If cyclic parent references are permitted in the location tree (e.g. node A made child of node B while B is already a child of A), ancestor traversals and lowest common ancestor searches would loop infinitely, causing server worker starvation; enforcing cycle detection on every `parent_id` mutation neutralizes this hazard.
* **Quiz Questions (for viva preparation):**
  1. *Why is campus location scoring modeled as a hierarchical tree and adjacency graph rather than pure Euclidean distance between GPS coordinates?*
  2. *How does the Lowest Common Ancestor (LCA) algorithm determine the similarity score between two locations on campus, and how are adjacent buildings handled?*
  3. *Why must missing signals return `null` (None in Python) rather than `0.0` when computing similarity scores in a multimodal retrieval system?*


