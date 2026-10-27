# Smart Campus Lost & Found — Current Chat Transcript

> **Conversation ID:** `4fd51586-7d5f-411d-9ca0-bebdae25cae5` | **Total Turns:** 16 | **Workspace:** `Campus lost and found`

---

## Turn 1

**User Interaction:**
```
once completely go through tghis project
```

*Metadata:* `Timestamp: 2026-10-27T01:05:55+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


I will monitor the test execution.

I am monitoring the lint check.

I am monitoring the task.

I am waiting for the lint process.

I am waiting for the quality check.

I am checking the task status.

I have completed a thorough, end-to-end review of the entire project. Below is a comprehensive breakdown of the architecture, business logic, security safeguards, research evaluation framework, and current test/build health.

---

### 1. Executive Summary & Project Purpose

The **Smart Campus Lost-and-Found Network** is a full-stack, privacy-preserving web application designed for university campuses. It balances two equally important pillars:
1. **The Product System**: A production-grade operational workflow featuring campus email authentication, hierarchical location matching, a safe media processing pipeline, privacy-first found listings, human-in-the-loop claim adjudication, and single-use cryptographic desk handover codes.
2. **The Research Framework**: An empirical evaluation suite comparing keyword search (Okapi BM25), text embeddings (`all-MiniLM-L6-v2`), visual/cross-modal embeddings (`CLIP ViT-B/32`), and hybrid/learned fusion with bootstrap confidence intervals on a pre-registered hypothesis ($H_1$).

> **Core Philosophy**: **AI is strictly advisory** ([D-01](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/DECISIONS.md#L7)). No similarity score or automated algorithm ever automatically approves claims, changes status, or overrides human staff verification.

---

### 2. High-Level Architecture & Layering

The system is structured as a **modular monolith** with clean separation between pure domain rules, database/network operations, and presentation:

```
┌────────────────────────────────────────────────────────┐
│             Client SPA (React 18 + TypeScript)         │
│     Responsive (360px+), WCAG AA A11y, OpenAPI Client  │
└───────────────────────────┬────────────────────────────┘
                            │ Reverse Proxy / TLS
┌───────────────────────────▼────────────────────────────┐
│                    FastAPI Backend                     │
│  - Thin Routers (app/api/)                             │
│  - Strict Pydantic Schemas (extra="forbid")            │
│  - Anti-enumeration (404 on foreign private resources) │
│  - Default-Deny Whitelist Serializers                  │
└─────────────┬───────────────────────────┬──────────────┘
              │                           │
┌─────────────▼───────────────┐ ┌─────────▼──────────────┐
│  Pure Domain (app/domain/)  │ │ Services (app/services)│
│  - Pure functions only      │ │ - DB transactions      │
│  - 0 DB / Clock / Framework │ │ - Transactional Outbox │
│  - Scoring, PII, Handover   │ │ - Background Job Queue │
└─────────────────────────────┘ └─────────┬──────────────┘
                                          │
┌─────────────────────────────────────────▼──────────────┐
│            PostgreSQL 16 with pgvector                 │
│  - Relational Models & HNSW Cosine Index               │
│  - Transactional Jobs & Notification Outbox Tables     │
│  - Append-only Immutable Audit Log (Triggers)          │
└────────────────────────────────────────────────────────┘
```

---

### 3. Deep Dive into Core Modules

#### A. Security, Authentication & Privacy
* **Email Verification & Passwords**: Restricts signups to authorized campus domains (e.g. `@campus.edu`, `@student.campus.edu`). Passwords use **Argon2id**.
* **Session Management & CSRF**: Server-side revocable sessions using 64-character tokens stored in `HttpOnly`, `SameSite=Lax` cookies, paired with a double-submit `X-CSRF-Token` header.
* **Anti-Enumeration ([AC-14](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/test-plan.md#L24))**: Unauthorized access to private reports or claims returns `404 Not Found` (never `403 Forbidden`), preventing attackers from probing valid resource IDs.
* **Default-Deny Serializers ([P1](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/spec.md#L109))**: Public endpoints explicitly whitelist fields via schemas (`PublicFoundItemSummary`). Verification prompts, private details, finder IDs, and precise indoor locations are strictly stripped.
* **PII Scanner ([app/domain/pii.py](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/pii.py))**: Detects card numbers (Luhn check), long numeric sequences, phone numbers, and emails in public text before saving, rejecting with `422 pii_detected` without echoing the sensitive data.

#### B. Campus Location Hierarchy & Scoring
* **Tree Structure ([app/domain/location.py](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/location.py))**: Models campus geography into 5 levels (`campus` $\to$ `building` $\to$ `floor` $\to$ `room` $\to$ `area`) with cycle detection and symmetric building adjacency.
* **Calibrated Proximity Matrix**:
  * Identical location: `1.0`
  * Ancestor/descendant: `0.8`
  * Shared floor/area (LCA): `0.7`
  * Shared building: `0.6`
  * Adjacent building: `0.5`
  * Same campus: `0.2`
  * Missing location: `None` *(dynamically excluded, not penalized as zero)*

#### C. Multimodal Matching Engine & Explanations
* **Signals & Asymmetric Time Decay ([app/domain/matching.py](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/matching.py))**:
  * **Text Score**: $\max(0, \cos(\mathbf{u}, \mathbf{v}))$ using 384-d MiniLM vectors.
  * **Time Score**: Overlapping windows score `1.0`. Found after lost decays gradually as $\exp(-\Delta t / 48)$; found before lost penalizes steeply as $\exp(-\Delta t / 6)$.
  * **Image Score**: Direct image-to-image cosine if both have photos; cross-modal text-to-photo CLIP cosine if only one has photos; `None` if neither does.
* **Dynamic Weight Renormalization**: Hybrid score is computed as $\frac{\sum w_i s_i}{\sum w_i}$ only over available non-null signals.
* **Strict Additive Explanations ([AC-59](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/test-plan.md#L99))**: Signal contributions $c_i = \frac{w_i s_i}{\sum w_j}$ sum exactly to the final combined score ($| \sum c_i - s | < 10^{-9}$), translating to plain language (e.g. *"Similar description"*, *"Reported in a nearby building"*).

#### D. Claims & Single-Use Handover Codes
* **Claim Adjudication ([app/domain/claims.py](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/claims.py))**: Requires verification prompt answers and evidence. Moderators acquire exclusive 30-minute locks (`409 claim_locked` on collisions). Conflict-of-interest checks prevent staff from reviewing their own reports.
* **Crockford Base32 Handover Codes ([app/domain/handover.py](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/handover.py))**:
  * 8 characters from `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (40 bits entropy, collision probability $\approx 4.5 \times 10^{-12}$).
  * Normalizes optical confusions (`O` $\to$ `0`, `I/L` $\to$ `1`).
  * Only HMAC-SHA-256 is stored in the database; verification uses `hmac.compare_digest`.
  * Locks out after 5 failed attempts; expires in 48 hours; max 3 reissues.
  * Desk staff interface reveals only binary verification success/failure; the raw code is rendered strictly to the claimant.

#### E. Transactional Outbox & Background Jobs
* **Concurrency ([app/services/job_runner.py](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/services/job_runner.py))**: Workers poll using `SELECT ... FOR UPDATE SKIP LOCKED`, preventing race conditions without needing Redis or RabbitMQ.
* **Reliability**: Employs the Transactional Outbox pattern where report state changes, embedding jobs, and email notifications are committed within the exact same database transaction, eliminating ghost emails and orphaned states.

#### F. Research Evaluation Framework ([eval/](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/eval/))
* **Leakage Guard**: `TuningHarness` raises `DataLeakageError` if pointed at the test split.
* **Pre-registered Hypothesis ($H_1$)**: Evaluated on a 70% held-out test split (210 queries $\times$ 310 candidates) with paired bootstrap 95% confidence intervals:
  * **System A (BM25)**: MRR `0.120` [0.090, 0.153]
  * **System B (MiniLM)**: MRR `0.342` [0.293, 0.389]
  * **System D (Hybrid)**: MRR `0.959` [0.938, 0.979]
  * **System E (Learned Fusion)**: MRR `0.982` [0.966, 0.994]

---

### 4. Codebase Health & Verification Results

All static analysis and compilation checks were run and validated:

| Verification Suite | Target | Status | Result / Details |
| :--- | :--- | :---: | :--- |
| **Python Linting** | `backend/` | **PASSED** | `ruff check .` reported 0 issues |
| **Python Type Check** | `backend/` | **PASSED** | `mypy .` reported no issues across all 73 source files |
| **Architecture Quality** | `backend/tests/` | **PASSED** | `test_ac_132` verified pure domain layer isolation via AST |
| **Domain Logic Tests** | `backend/tests/` | **PASSED** | `test_ac_86_to_89_handover_domain.py` passed (6/6 tests) |
| **Frontend Linting** | `frontend/` | **PASSED** | `npm run lint` (ESLint) reported 0 errors/warnings |
| **Frontend Type Check** | `frontend/` | **PASSED** | `npx tsc --noEmit` passed with 0 errors |
| **Frontend Production Build** | `frontend/` | **PASSED** | `npm run build` compiled bundle in 1.77s (`dist/` ready) |

*(Note: End-to-end integration tests connecting to PostgreSQL require the Docker stack or local Postgres instance to be active).*

---

### 5. Key Documentation & Artifacts Reference

* **Main System Specification**: [`spec.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/spec.md) (All ACs from AC-01 to AC-149)
* **Architectural Decisions Log**: [`DECISIONS.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/DECISIONS.md) (D-01 to D-21)
* **Viva Q&A & Learning Log**: [`docs/learning-log.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/learning-log.md) (Step-by-step design rationale, potential failure modes, and viva self-quizzing questions)
* **Test Plan & Matrix**: [`docs/test-plan.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/test-plan.md)
* **Entity-Relationship Model**: [`docs/er-diagram.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/er-diagram.md)
* **Deployment Guide**: [`docs/deployment.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/deployment.md)

Let me know if you would like to run any specific module, inspect a particular feature, or prepare for any specific viva questions!


</details>

---

## Turn 2

**User Interaction:**
```
I have to prepare for viva
```

*Metadata:* `Timestamp: 2026-10-27T01:14:44+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


Here is your **Viva Preparation Guide**. It is structured around the core topics examiners grill students on, complete with the exact design rationales, mathematical formulas, and concrete examples.

---

### The 5 "Killer" Questions Every Examiner Asks

#### 1. "Why use `pgvector` inside PostgreSQL instead of a dedicated vector database like Pinecone, Milvus, or Qdrant?"
* **Answer**: **Transactional consistency (ACID) and zero operational overhead.**
* **Why**: In a lost-and-found system, item status, location, and embeddings must change atomically. With a separate vector database, you face the *dual-write problem*—if PostgreSQL commits a report but the external vector DB call fails, your database has an item with no searchable vector. With `pgvector`, embedding rows, metadata, and outbox jobs commit in the **exact same database transaction**.
* **Bonus**: PostgreSQL can easily handle hundreds of thousands of vectors on a single instance with sub-millisecond HNSW cosine search without requiring distributed cluster management.

---

#### 2. "Why is AI matching strictly advisory? Why not auto-approve claims with >95% match score?"
* **Answer**: **Because similarity is not proof of ownership, and false claims are the primary abuse vector.**
* **Concrete Example**: Alice reports a lost "Matte Black Lenovo ThinkPad" with photo. Bob sees the public listing, finds an identical ThinkPad photo online, and claims it. An automated system scoring text and photo would give 99% similarity and hand Alice’s laptop to Bob. Human moderators must verify non-public evidence (unique serial numbers, lock-screen stickers, or answers to finder verification prompts).

---

#### 3. "How does your location and time scoring work? Why isn't location just GPS distance?"
* **Location Score**: GPS fails indoors and lacks vertical resolution (cannot distinguish Floor 1 from Floor 4). We use a 5-level **Hierarchical Tree** (`campus` $\to$ `building` $\to$ `floor` $\to$ `room` $\to$ `area`) with Lowest Common Ancestor (LCA) + an **Adjacency Table**:
  * Identical room/area: `1.0`
  * Shared floor/area: `0.7`
  * Shared building: `0.6`
  * Adjacent buildings: `0.5`
  * Different campus: `0.0`
* **Time Score**: **Asymmetric Exponential Decay**.
  * If found *after* lost: $\exp(-\text{gap} / 48)$ (gradual decay; items can sit in lost bins for weeks).
  * If found *before* lost: $\exp(-\text{gap} / 6)$ (steep decay; an item cannot be found before it was lost except for slight human memory error).

---

#### 4. "How does the Handover Code work, and why store an HMAC instead of a plain hash or raw code?"
* **Structure**: 8-character Crockford-like Base32 (`0123456789ABCDEFGHJKMNPQRSTVWXYZ`), excluding confusing letters (`I`, `L`, `O`).
* **Entropy & Security**: $\log_2(32^8) = 40\text{ bits}$ of entropy. With a 5-attempt lock, brute-force probability is:
  $$\frac{5}{2^{40}} \approx 4.5 \times 10^{-12}$$
* **Why HMAC-SHA256**: If the database is leaked or accessed by a rogue staff member, standard SHA-256 can be brute-forced across $2^{40}$ states in a few hours on a modern GPU. A secret-keyed HMAC cannot be inverted without the server secret.
* **Why Normalization**: Normalizes optical mistakes (`O` $\to$ `0`, `I/L` $\to$ `1`) and compares using `hmac.compare_digest` to prevent **timing attacks**.
* **Zero-Knowledge Desk**: The desk interface shows **only** success or failure—moderators never see the code.

---

#### 5. "What is the Transactional Outbox pattern and `SELECT FOR UPDATE SKIP LOCKED`?"
* **The Problem**: If your API endpoint sends an email via SMTP or calls an ML embedding model during the HTTP request, slow network calls choke your server, or if the email succeeds but the database transaction aborts, you send a "ghost notification."
* **Outbox Pattern**: When a report or claim state changes, the notification and job row are inserted into PostgreSQL *in the exact same database transaction*.
* **`SELECT FOR UPDATE SKIP LOCKED`**: Background workers claim queue items atomically without locking each other or requiring Redis/RabbitMQ. Any row locked by Worker 1 is skipped by Worker 2 with zero concurrency collision.

---

### Key Numbers & Formulas to Know by Heart

| Metric / Parameter | Value / Formula | Rationale |
| :--- | :--- | :--- |
| **Hybrid Formula** | $\text{Score} = \frac{\sum w_i s_i}{\sum w_i}$ | Summed **only** over non-null signals. Missing signals (e.g. no photo) are never imputed as 0.0. |
| **Initial Weights** | Text: `0.40`, Image: `0.35`, Location: `0.15`, Time: `0.10` | Bins: $\ge 0.75$ High, $\ge 0.55$ Medium, else Low. |
| **Handover Expiry** | **48 Hours**, 5 attempts lock, max 3 reissues | Prevents stolen codes from remaining valid indefinitely. |
| **Retention Policy** | Found items expire after **90 days**; photos & claim evidence purged **30 days** post-closure; audit logs purged after **365 days** | Data minimization & GDPR compliance. |
| **Photo Pipeline Guards** | 5 MB max, $6000 \times 6000$ px guard, downscaled to 1600 px, EXIF stripped | Prevents decompression/pixel bombs and geolocation leakage. |
| **Research Results** | **MRR**: BM25: `0.120`, MiniLM: `0.342`, Hybrid: `0.959` | Text MiniLM roughly triples BM25 when different vocabulary is used. |

---

### Security Engineering Concepts

* **Anti-Enumeration ([AC-14](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/test-plan.md#L24))**: Foreign or non-existent IDs return `404 Not Found` (never `403 Forbidden`), preventing attackers from discovering which claim or report IDs exist.
* **Default-Deny Serializers ([P1](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/spec.md#L109))**: Responses use strict Pydantic schemas with whitelisted fields. Even if new columns are added to SQL tables, they never leak to public endpoints.
* **Immutable Audit Log ([D-14](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/DECISIONS.md#L20))**: PostgreSQL trigger (`audit_log_immutable_trigger`) blocks all raw `UPDATE` and `DELETE` queries on `audit_log`. Only privileged retention routines with a session flag can purge rows older than 365 days.
* **Leakage Guard in Research ([AC-111](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/test-plan.md#L162))**: `TuningHarness` throws `DataLeakageError` immediately if hyperparameter tuning ever attempts to read the test split.

---

### How would you like to practice?

1. **Mock Viva Mode**: I act as your examiner and ask you 1 realistic viva question at a time, critique your answer, and give you the model response.
2. **Deep-Dive a Specific Module**: Focus on any one module you feel less confident about (e.g. *The Evaluation Bootstrap*, *The Photo Pipeline*, or *The Matching Formulas*).
3. **Walk me through your code**: I can highlight specific lines of code in the repo that an examiner might ask you to point to on screen.


</details>

---

## Turn 3

**User Interaction:**
```
I wan to learn how it runs,what it uses and why it uses
```

*Metadata:* `Timestamp: 2026-10-27T01:15:56+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


Here is a complete breakdown of **How it runs**, **What it uses**, and **Why it uses each technology**, with concrete examples you can cite directly in your viva.

---

# Part 1: How It Runs

### 1. The Operational Lifecycle (Step-by-Step Flow)

```
[1. Student A reports Lost Item]
               │ (Private: only Student A & staff can see it)
               ▼
[2. Student B reports Found Item] ──► [3. Staff Moderator Approves]
                                                  │ (Becomes Public Listing)
                                                  ▼
                                      [4. Background Worker (async)]
                                       - Computes 384-d MiniLM text vector
                                       - Computes 512-d CLIP photo vector
                                       - Calculates Hybrid Similarity Score
                                                  │
                                                  ▼ (Score >= 0.65)
[6. Student A files Claim] ◄────────── [5. Match Notification dispatched]
   (Submits answers to finder's prompts)
               │
               ▼
[7. Moderator reviews & locks claim] ──► [8. Moderator Approves Claim]
                                                  │
                                                  ▼
[10. Handover at Campus Desk] ◄────── [9. 8-char Single-Use Code generated]
  - Staff enters code into desk UI       (Rendered ONLY to Student A)
  - System verifies HMAC constant-time
  - Records identity note
  - Found item -> 'returned'
  - Lost report -> 'resolved'
```

---

### 2. How the Components Talk to Each Other

1. **Client (Browser)**: Runs a single-page React application at `http://localhost:8080`.
2. **Reverse Proxy / Server**: Requests to `/api/...` route to the **FastAPI** backend (`:8000`).
3. **Database (PostgreSQL + pgvector)**: Stores relational data (users, reports, claims) and dense vector embeddings (`vector(384)`, `vector(512)`).
4. **Worker Loop**: Runs in the background (or in a separate container). It polls the PostgreSQL `jobs` table every few seconds using `SELECT ... FOR UPDATE SKIP LOCKED`:
   * Picks up pending embedding tasks (`embed_report_text`, `embed_report_image`).
   * Runs candidate matching and enqueues transactional notifications.
   * Delivers outgoing emails to the mail server (Mailpit at `:1025` in dev).
   * Runs hourly maintenance sweeps (expiring 48-hour codes and 90-day unclaimed items).

---

### 3. How to Launch It

There are two primary ways the application runs:

* **Docker Compose (Full Multi-Container Stack)**:
  ```bash
  docker compose up -d --build
  ```
  Spins up 5 containers: `db` (Postgres 16 + pgvector), `backend` (FastAPI), `worker` (async ML runner), `frontend` (Nginx + React SPA), and `mail` (Mailpit).

* **Cloud Unified Container Mode ([docs/deployment.md](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/deployment.md))**:
  On cloud platforms like Render or Railway, it uses [`Dockerfile.web`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/Dockerfile.web). The FastAPI server serves the API endpoints *and* mounts the static frontend bundle (`frontend/dist`), while running the worker loop in-process (`RUN_WORKER_IN_PROCESS=true`).

---

# Part 2: What It Uses & Why It Uses It

### 1. Database & Vector Storage

| Technology | What it is | Why this project uses it |
| :--- | :--- | :--- |
| **PostgreSQL 16** | Relational Database | ACID transactions guarantee state consistency across reports, claims, audit logs, and notifications. |
| **`pgvector`** extension | Vector extension for Postgres | Stores 384-dimensional text vectors and 512-dimensional image vectors. Allows vector cosine similarity searches alongside relational SQL joins in a single database. |
| **HNSW Index** (`vector_cosine_ops`) | Hierarchical Navigable Small World index | Sub-millisecond approximate nearest neighbor retrieval without table scans. |

* **Why not an external vector database (like Pinecone/Milvus)?**
  * *Eliminates the Dual-Write Problem*: If Postgres commits a report, but an external vector DB call fails, you have an orphaned record. In Postgres, the report metadata, vector, and job queue are written in the **exact same ACID transaction**.
  * *Zero extra operational complexity*: No extra SaaS bills, API tokens, or cluster management.

---

### 2. Backend & Domain Architecture

| Technology | What it is | Why this project uses it |
| :--- | :--- | :--- |
| **FastAPI** (Python 3.12) | Asynchronous Web Framework | High-performance async I/O; automatic OpenAPI 3.0 documentation (`/docs`); native integration with Pydantic v2. |
| **Pydantic v2** (`extra="forbid"`) | Data validation library | Enforces strict API schemas. Any unexpected payload field is rejected with `422 Unprocessable Entity`, preventing mass-assignment vulnerabilities. |
| **SQLAlchemy 2.0 (async)** | Object-Relational Mapper | Async database queries using `asyncpg` ensure high concurrency without thread pool starvation. |
| **Alembic** | Database Migration Tool | Tracks database schema evolution in versioned Python scripts (`backend/alembic/versions/`). |
| **Pure Domain Layer** (`app/domain/`) | Python functions with zero imports | Isolates mathematical and business rules (matching formulas, PII scanning, handover codes) from frameworks or databases. Ensures fast unit tests with zero mocks. |

---

### 3. Machine Learning & Retrieval Models

| Model | Dimensions | Purpose in this project | Why it was chosen |
| :--- | :---: | :--- | :--- |
| **`all-MiniLM-L6-v2`** | 384-d | Text embeddings (Title + Description + Category) | Extremely compact (~80 MB) and fast (sub-15ms CPU inference), yet achieves strong semantic retrieval (triples BM25 MRR when synonyms are used). |
| **`CLIP ViT-B/32`** | 512-d | Image-to-image and Text-to-image similarity | Places text and photos into a shared 512-d embedding space, allowing cross-modal comparison when only one report has a photo. |

* **Why models are baked into Docker images (`models.lock.json`)**:
  Weights and SHA-256 checksums are pinned at container build time. In production, containers run with `HF_HUB_OFFLINE=1`—the system operates **100% air-gapped without external network calls**.

---

### 4. Security, Cryptography & Image Processing

| Technology | What it does | Why this project uses it |
| :--- | :--- | :--- |
| **Argon2id** (`passlib`) | Password hashing | State-of-the-art memory-hard algorithm. Resistant to GPU and ASIC cracking attacks (unlike standard SHA256 or older bcrypt). |
| **HMAC-SHA256** | Secret-keyed hashing | Used for handover verification codes. Plain hashes can be brute-forced if the DB leaks; an HMAC cannot be reversed without the server's private key. |
| **Crockford Base32** | 32-character alphabet | Generates 8-character codes (`0123456789ABCDEFGHJKMNPQRSTVWXYZ`) without ambiguous characters (`I`, `L`, `O`) to prevent human transcription errors. |
| **`hmac.compare_digest`** | Constant-time comparison | Prevents timing attacks where an attacker measures response times to guess characters one-by-one. |
| **Pillow (PIL)** | Image processing pipeline | 1. **Magic Bytes Check**: Verifies real MIME type (rejects malicious files disguised as `.jpg`).<br>2. **Decompression Bomb Guard**: Rejects images $>6000 \times 6000$ px before full memory load.<br>3. **EXIF Stripping**: Deletes embedded GPS coordinates and camera serial numbers.<br>4. **64-bit dHash**: Detects duplicate or near-identical image submissions (Hamming distance $\le 10$). |

---

### 5. Frontend & UI Architecture

| Technology | What it is | Why this project uses it |
| :--- | :--- | :--- |
| **React 18 + TypeScript** | Frontend UI Framework | Static type checking prevents runtime `undefined` errors. Components consume types generated directly from backend OpenAPI specs (`npm run gen:api`). |
| **Vite** | Build tool and bundler | Instant Hot Module Replacement (HMR) in development; compiles production assets in under 2 seconds. |
| **Tailored Vanilla CSS** (`styles.css`) | Custom Design System | Zero bloated runtime CSS dependencies. Tailored specifically for mobile accessibility: responsive down to **360px viewport** with high-contrast `:focus-visible` indicators and WCAG AA contrast. |
| **Hash-based Router** | Client routing (`/#/found`, etc.) | Ensures seamless navigation on static hosting and behind reverse proxies without complex Nginx URL rewrites. |

---

### Quick Summary to Memorize for Viva

If the examiner asks: *"Summarize the architecture in three sentences"*:
> *"Our project is built as a modular monolith using **FastAPI** and **PostgreSQL with pgvector**, with business logic isolated into a framework-independent domain layer.*  
> *It processes multimodal text and visual signals offline via pinned **MiniLM** and **CLIP** models using a **Transactional Outbox** and lock-free workers (`SKIP LOCKED`).*  
> *All operational workflows enforce strict campus privacy through default-deny serialization, PII scanning, anti-enumeration, and cryptographically verified **HMAC-SHA256 Base32 handover codes**."*


</details>

---

## Turn 4

**User Interaction:**
```
what is FastAPI and what does it do
```

*Metadata:* `Timestamp: 2026-10-27T01:19:29+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


### What is FastAPI?

**FastAPI** is a modern, high-performance web framework for Python used to build **RESTful APIs** (Application Programming Interfaces). 

Think of it as the **receptionist and traffic controller** between your frontend (the React browser UI) and your backend (your Python algorithms and PostgreSQL database).

When a student clicks "Submit Claim" or "Search Found Items" in their browser, their browser sends an HTTP request across the network. **FastAPI catches that request, validates it, runs the Python code, and sends back a JSON response.**

---

### What Does FastAPI Actually Do? (Its 5 Main Jobs)

#### 1. Routing (Directing Traffic)
FastAPI maps URLs and HTTP methods (`GET`, `POST`, `PATCH`, `DELETE`) to Python functions:
```python
# In backend/app/api/found.py
@router.get("/api/found")
async def list_found_items(q: str = None, category: str = None):
    # Runs the search logic and returns matching items
```
When someone visits `http://localhost:8000/api/found`, FastAPI knows exactly which Python function to execute.

---

#### 2. Automatic Input Validation (Via Pydantic)
Before your code even touches the database, FastAPI inspects the incoming data to make sure it matches your required format. If a user sends a missing field or wrong type, FastAPI automatically rejects it with `422 Unprocessable Entity`:
* *Example*: If someone tries to submit a report without a `title`, or puts a text string into an integer field, FastAPI stops them at the door before any database errors occur.

In our project, we configure it with `extra="forbid"`, which means **any surprise or unknown fields injected by an attacker are instantly rejected**.

---

#### 3. Asynchronous Speed (`async` / `await`)
Traditional Python frameworks (like older Flask or Django) handle one request per thread at a time. If a request is waiting for the database, that thread sits idle. 

FastAPI is built on **ASGI (Asynchronous Server Gateway Interface)**. While one request is waiting for PostgreSQL to search 10,000 vector embeddings, the server can immediately start handling another student's login request without blocking.

---

#### 4. Automatic Interactive Documentation (`/docs`)
FastAPI reads the Python code and type annotations and **automatically generates interactive documentation** (Swagger UI).
* In our project, visiting `http://localhost:8000/docs` in your browser opens a live dashboard where you can test every single API endpoint without writing frontend code.

---

#### 5. Output Serialization & Security Filtering
FastAPI converts Python database objects into clean JSON sent back to the browser.
* In our project, it enforces **Default-Deny Serialization**: even if our database record contains a student's private phone number or the secret handover code, FastAPI strips those fields out based on our defined response schema so sensitive data never leaks over the network.

---

### Top Viva Question: *"Why did you choose FastAPI over Django or Flask?"*

| Feature | **FastAPI** (Our Choice) | **Flask** | **Django** |
| :--- | :--- | :--- | :--- |
| **Speed & Concurrency** | Native `async`/`await` (one of the fastest Python frameworks available) | Synchronous by default; slower under concurrent load | Heavier overhead; synchronous legacy architecture |
| **Data Validation** | Built-in via **Pydantic v2** (fast, strictly typed) | Requires manual libraries (like Marshmallow) | Form/Model serializers tied tightly to Django ORM |
| **API Documentation** | **Automatic OpenAPI/Swagger** generated on startup | Requires third-party plugins (e.g. Flasgger) | Requires Django REST Framework + swagger packages |
| **Fit for Modern SPAs** | Lightweight and perfect for connecting to a **React Single-Page App** | Minimal, but requires assembling many separate libraries | "Batteries-included" monolith that expects to render its own HTML templates |

**Your 10-Second Viva Answer**:
> *"We chose FastAPI because it provides native asynchronous I/O for high concurrency, built-in strict data validation via Pydantic to prevent injection attacks, and automatically generates the OpenAPI schema that our React TypeScript frontend uses for end-to-end type safety."*


</details>

---

## Turn 5

**User Interaction:**
```
i want a full clear deep explanation of this project
```

*Metadata:* `Timestamp: 2026-10-27T12:28:33+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


# Smart Campus Lost-and-Found Network
## Comprehensive Technical & Architectural Blueprint

---

## Table of Contents
1. **The Core Problem & Executive Summary**
2. **The Dual Architecture: Product vs. Research**
3. **System Architecture & Design Patterns**
4. **Subsystem 1: Identity, Authentication & Privacy Engineering**
5. **Subsystem 2: The Physical Campus Location Model**
6. **Subsystem 3: Report Lifecycles & State Machines**
7. **Subsystem 4: Safe Media Pipeline & Privacy Blurring**
8. **Subsystem 5: The Multimodal Matching Engine & Math**
9. **Subsystem 6: Claim Verification & Cryptographic Handover Desk**
10. **Subsystem 7: Transactional Outbox & Concurrency Architecture**
11. **Subsystem 8: The Empirical AI Research & Evaluation Framework**
12. **Subsystem 9: Frontend Architecture & Accessibility**
13. **Subsystem 10: Cloud & Local Deployment Mechanics**
14. **Examiner Viva Cheat Sheet (Quick-Fire Technical Answers)**

---

## 1. The Core Problem & Executive Summary

### The Real-World Challenge
Campus lost-and-found management is traditionally chaotic, insecure, and inefficient:
* **The "Noticeboard" Failure**: Students post on WhatsApp groups or Instagram pages (*"Lost black wallet in library"*). This creates two major problems:
  1. **Fraud**: Anyone can see the exact description and photo, walk up to the security desk, and falsely claim the item.
  2. **Privacy Violations**: Lost ID cards, room keys, and personal laptops with visible stickers or names are exposed publicly.
* **The Semantic Retrieval Failure**: A student reports a lost *"Black Lenovo ThinkPad"*, while the finder logs a *"Dark gray notebook computer"*. Traditional keyword searches (SQL `LIKE '%ThinkPad%'`) fail completely because the vocabularies do not overlap.
* **Indoor Positioning Failure**: GPS does not work inside multi-story university buildings. Lat/long coordinates cannot distinguish between Floor 1 and Floor 4, or adjacent lecture halls.

### The Solution Built in This Project
This project builds an end-to-end, privacy-preserving, accessible web platform that pairs a **hardened campus operational workflow** with a **rigorous AI/Data Science research framework**:
* **Privacy-First Public Browsing**: Only found items are publicly browsable; lost items remain strictly private. Public listings use **default-deny serializers** that strip finder identities, exact indoor locations, and verification prompts.
* **Multimodal Advisory Matching**: The system computes semantic text embeddings (`all-MiniLM-L6-v2`), cross-modal visual embeddings (`CLIP ViT-B/32`), hierarchical campus tree distance, and asymmetric time decay. **AI is strictly advisory**—scores never alter database states automatically.
* **Cryptographic Verification**: Replaces paper logbooks with **single-use 8-character Crockford Base32 codes**, hashed with server-secret HMAC-SHA256, with a 5-attempt lockout and 48-hour expiration.

---

## 2. The Dual Architecture: Product vs. Research

The project is deliberately split into two halves of equal academic and engineering weight:

```
                           CAMPUS LOST-AND-FOUND PROJECT
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 ▼                                               ▼
         THE PRODUCT HALF                               THE RESEARCH HALF
  (Operational Campus System)                     (Empirical AI Evaluation)
  • Privacy-preserving found listings             • Seeded synthetic benchmark (300 pairs)
  • 5-level hierarchical location tree            • Okapi BM25 keyword baseline
  • Safe photo pipeline (magic bytes, EXIF, dHash)• Dense sentence embeddings (MiniLM)
  • 30-min moderator claim locks                  • Cross-modal image retrieval (CLIP)
  • Single-use Base32 handover codes              • Grid-search hybrid & learned fusion
  • Transactional outbox notifications            • Pre-registered hypothesis (H1)
  • Database-level immutable audit logs           • Paired bootstrap 95% confidence intervals
```

---

## 3. System Architecture & Design Patterns

The backend follows a **Modular Monolith** architecture with clean, layered separation:

```
┌────────────────────────────────────────────────────────────────────────┐
│                   Web Client (React 18 + TypeScript)                   │
│          Accessible (WCAG AA), 360px+ Mobile Viewport, Tailored CSS    │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ HTTPS / REST (JSON)
┌───────────────────────────────────▼────────────────────────────────────┐
│                       FastAPI Web Layer (`app/api/`)                   │
│  - Thin controller routers                                             │
│  - Strict Pydantic v2 schemas (`extra="forbid"`)                       │
│  - Anti-enumeration (HTTP 404 for unauthorized foreign resources)      │
│  - Double-submit CSRF & HttpOnly session verification                  │
└───────────────────┬────────────────────────────────┬───────────────────┘
                    │                                │
┌───────────────────▼─────────────┐    ┌─────────────▼───────────────────┐
│   Pure Domain (`app/domain/`)   │    │     Services (`app/services/`)  │
│  - 100% Pure Python functions   │    │  - Database transactions (ACID) │
│  - ZERO framework/DB/clock deps │    │  - Transactional Outbox pattern │
│  - Formulas, PII, Handover math │    │  - ML embedder invocation       │
└─────────────────────────────────┘    └─────────────┬───────────────────┘
                                                     │
┌────────────────────────────────────────────────────▼───────────────────┐
│                 PostgreSQL 16 with `pgvector` Extension                │
│  - Relational tables: users, reports, claims, handovers, locations     │
│  - Dense vector columns: `vector(384)` (text), `vector(512)` (images)  │
│  - HNSW Indexing (`vector_cosine_ops`) for sub-millisecond retrieval   │
│  - Transactional tables: `jobs` (queue) & `notifications` (outbox)     │
│  - Immutable `audit_log` table protected by PostgreSQL triggers        │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │ `SELECT ... FOR UPDATE SKIP LOCKED`
┌───────────────────────────────────▼────────────────────────────────────┐
│                       Background Worker Loop                           │
│  - Lock-free concurrent job execution                                  │
│  - Offline embedding inference (baked model checkpoints)               │
│  - Outbox notification dispatch (SMTP / Mailpit)                       │
│  - Automated retention & code expiry sweeps                            │
└────────────────────────────────────────────────────────────────────────┘
```

### Architectural Principles Enforced:
1. **Pure Domain Isolation**: Everything in [`backend/app/domain/`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/) is pure Python. No imports from FastAPI, SQLAlchemy, or the system clock. An automated AST unit test ([`test_ac_131_to_137_quality_and_architecture.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_131_to_137_quality_and_architecture.py)) parses the syntax tree of this folder to verify that zero framework imports exist.
2. **Single Database Consistency**: PostgreSQL handles relational data, vectors, job queues, and audit logs. This prevents distributed state divergence (the "dual-write" problem).
3. **Air-Gapped Container Execution**: Pretrained model weights are downloaded and verified against cryptographic hashes (`models.lock.json`) during image build. Containers run with `HF_HUB_OFFLINE=1`—zero internet requests are made during inference.

---

## 4. Subsystem 1: Identity, Authentication & Privacy Engineering

### Campus Email Verification & Registration
* Registration requires an email matching configured university domains (e.g., `@campus.edu`, `@student.campus.edu`). Generic domains or spoofed subdomains (`@evilcampus.com`, `@campus.edu.attacker.net`) are strictly blocked.
* Passwords are encrypted using **Argon2id** (the winner of the Password Hashing Competition), configured to resist GPU/ASIC parallel dictionary attacks.
* Registration dispatches a cryptographically secure token via email (caught in development by **Mailpit**). Tokens are single-use with a 24-hour expiry; re-use returns `HTTP 410 Gone`.

### Session Architecture & CSRF Defense
* **Stateless JWT vs. State-Stored Sessions**: We chose **server-side revocable sessions** over stateless JWTs. If a student's phone is stolen, an administrator or the student can immediately revoke the session in PostgreSQL. With stateless JWTs, tokens remain valid until expiration.
* Tokens are stored in **64-character random hex** strings transmitted inside `HttpOnly`, `SameSite=Lax`, `Secure` cookies (scripts cannot read the cookie).
* State-changing requests (`POST`, `PATCH`, `DELETE`) require a double-submit `X-CSRF-Token` header matching the session’s CSRF secret, preventing cross-site request forgery.

### Anti-Enumeration Defense (HTTP 404 vs 403)
* Standard APIs return `403 Forbidden` if a user attempts to access a resource they do not own. This allows attackers to **enumerate** valid IDs (e.g., *"403 means report #1024 exists; 404 means #1025 does not"*).
* Our system returns a uniform **`404 Not Found`** whenever a non-staff user attempts to view a lost report or private claim that does not belong to them.

### Default-Deny Whitelisting (Canary-Tested)
* Public endpoints serialize data through explicit Pydantic models (such as `PublicFoundItemSummary`). Internal attributes like `private_details`, `verification_prompts`, `reporter_id`, or `phone_number` are excluded by default.
* In tests, automated canary strings (e.g., `"CANARY_PRIVATE_SECRET_12345"`) are injected into private fields; test assertions ensure the canary never appears in public responses, notifications, or logs.

---

## 5. Subsystem 2: The Physical Campus Location Model

### Why GPS Coordinates Fail on University Campuses
1. **Vertical Ambiguity**: GPS coordinates cannot distinguish between the Ground Floor and the 4th Floor of a science building.
2. **Indoor Signal Attenuation**: Concrete structures severely degrade satellite signals.
3. **Imprecise Human Memory**: A student remembers: *"I left my jacket in the 3rd floor study lounge of the Engineering Library"*, not *"lat 12.9716, lng 77.5946"*.

### The 5-Level Hierarchical Tree
Campus geography is modeled in [`backend/app/domain/location.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/location.py) as an acyclic graph:
$$\text{Campus} \longrightarrow \text{Building} \longrightarrow \text{Floor} \longrightarrow \text{Room} \longrightarrow \text{Area}$$

Every node points to a `parent_id`. When adding or editing locations, an algorithm traverses parent pointers to detect circular references, rejecting loops with `422 cannot_become_own_ancestor`.

```
                  Main Campus
                       │
        ┌──────────────┴──────────────┐
  North Hall                    South Hall (Adjacent)
        │
   Second Floor
        │
    Room 204
```

### Building Adjacency & The Location Scoring Matrix
Two physical buildings located next to each other have high spatial proximity even if they reside in different branches of the tree. We maintain a symmetric `location_adjacency` table.

The function `calculate_location_score(loc_a, loc_b)` computes similarity:

| Spatial Relationship | Score | Explanation |
| :--- | :---: | :--- |
| **Identical Node** | `1.0` | Exact same room or area |
| **Ancestor / Descendant** | `0.8` | One report says "North Hall", the other says "North Hall, Room 204" |
| **Lowest Common Ancestor is Floor/Area** | `0.7` | Different rooms on the exact same floor |
| **Lowest Common Ancestor is Building** | `0.6` | Different floors in the exact same building |
| **Adjacent Buildings** | `0.5` | Linked in the `location_adjacency` table |
| **Same Campus** | `0.2` | Different non-adjacent buildings on the same campus |
| **Different Campuses** | `0.0` | Completely separate campuses |
| **Missing Location** | `None` | Dynamically excluded from hybrid weighting |

---

## 6. Subsystem 3: Report Lifecycles & State Machines

### Found Report Lifecycle
To prevent spam, abuse, or public listings of sensitive stolen items, found reports require human moderation before public listing:

```
[User submits Found Report]
              │
              ▼
       pending_review ──────────► removed (by Moderator)
              │
              ▼ (Moderator approves)
            open ───────────────► unclaimed_expired (after 90 days retention)
              │
              ▼ (Claim approved by Moderator)
          reserved ─────────────► open (if Handover cancelled or code expires)
              │
              ▼ (Handover verified at desk)
          returned [TERMINAL STATE]
```

### Lost Report Lifecycle
Lost reports are never published to public listings:
```
[User submits Lost Report]
              │
              ▼
            open ───────────────► closed (by Owner)
              │
              ▼ (Handover verified on matching found item)
          resolved [TERMINAL STATE]
```

### Time Window Precision Engine
Reports support multiple time precisions converted into UTC intervals $[t_{\text{start}}, t_{\text{end}}]$ in [`backend/app/domain/time.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/time.py):
* `exact`: Point timestamp $\pm 2$ hours.
* `morning` (06:00–12:00), `afternoon` (12:00–17:00), `evening` (17:00–21:00).
* `night`: 21:00 to 06:00 (crosses midnight into the next calendar day).
* `day`: 00:00:00 to 23:59:59 in the reporter's IANA timezone (e.g., `Asia/Kolkata`).

---

## 7. Subsystem 4: Safe Media Pipeline & Privacy Blurring

Uploading images to a public platform introduces severe attack vectors (decompression bombs, geolocation leaks, malicious file extensions) and privacy risks (capturing faces or vehicle license plates).

### The Ingestion Pipeline ([`app/services/photo.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/services/photo.py))

```
[Raw Uploaded File]
         │
         ▼ 1. Magic Bytes Check (inspects file header, rejects spoofed .exe/.html)
         ▼ 2. Size Guard (rejects files > 5 MB)
         ▼ 3. Dimension Guard (inspects image header; rejects > 6000x6000 px decompression bombs)
         ▼ 4. EXIF Stripping (Pillow rebuilds image, wiping GPS & camera serials)
         ▼ 5. Normalization & Downscaling (long edge <= 1600 px; generates 256 px thumbnail)
         ▼ 6. Cryptographic Storage Key (saved under random UUIDv4; never uses user filename)
         ▼ 7. Perceptual Difference Hash (computes 64-bit dHash for duplicate detection)
```

1. **Magic Bytes MIME Validation**: File extensions can be forged (`malware.exe` renamed to `photo.jpg`). The pipeline inspects raw file header bytes:
   * JPEG: `\xFF\xD8\xFF`
   * PNG: `\x89PNG\r\n\x1a\n`
   * WebP: `RIFF....WEBP`
2. **Decompression Bomb Protection**: A compressed image can be 100 KB on disk but expand to 10 GB in RAM when uncompressed. Pillow checks the image dimension header before allocating pixel buffers.
3. **EXIF Metadata Stripping**: Smart phones record precise latitude, longitude, altitude, and device identifiers in EXIF headers. The pipeline strips these to prevent revealing where a student lives or studies.
4. **Perceptual dHash Duplicate Detection**: Resizes the image to $9 \times 8$ grayscale and compares adjacent pixel brightness to generate a 64-bit integer hash. Two photos with a **Hamming distance $\le 10$** are flagged as duplicate submissions in the moderation queue.
5. **Sensitive Category Guard**: Photos of items categorized as `id_card` or `wallet` are automatically flagged private and never shown on public browse screens.
6. **Privacy Blurring ([`app/domain/privacy_blur.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/privacy_blur.py))**: Applies localized Gaussian smoothing to bounding boxes around bystander faces or vehicle license plates before disk persistence.

---

## 8. Subsystem 5: The Multimodal Matching Engine & Math

The matching engine in [`backend/app/domain/matching.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/matching.py) compares active lost reports with active found reports across four distinct signals.

### 1. The Semantic Text Signal ($s_{\text{text}}$)
Concatenates: `category + " " + title + " " + description`.  
Passes text through `all-MiniLM-L6-v2` to produce a 384-dimensional unit-normalized vector $\mathbf{u}$.
$$s_{\text{text}} = \max(0, \cos(\mathbf{u}_{\text{lost}}, \mathbf{u}_{\text{found}}))$$

### 2. The Visual / Cross-Modal Image Signal ($s_{\text{image}}$)
Uses `CLIP ViT-B/32` (512 dimensions):
* **Both reports have photos**: Image-to-image cosine similarity between the most visually similar pair of photos.
* **Only one report has photos**: Compares the CLIP text vector of the non-photo report against the photo vector of the other report.
* **Neither report has photos**: Evaluates to `None` (missing signal).

### 3. The Asymmetric Time Signal ($s_{\text{time}}$)
Let $\Delta t$ be the gap in hours between the lost window $[L_{\text{start}}, L_{\text{end}}]$ and found window $[F_{\text{start}}, F_{\text{end}}]$:
* If windows overlap: $s_{\text{time}} = 1.0$
* If item was found **after** it was lost ($F_{\text{start}} > L_{\text{end}}$):
  $$s_{\text{time}} = \exp\left(-\frac{\Delta t}{48}\right)$$
  *(Gradual decay: an item may sit in a corner for days before someone picks it up).*
* If item was found **before** it was reported lost ($L_{\text{start}} > F_{\text{end}}$):
  $$s_{\text{time}} = \exp\left(-\frac{\Delta t}{6}\right)$$
  *(Steep decay: an item cannot be found before it was lost, except for slight human memory error).*

```
Time Score
 1.0 ┼──────┐
     │      │ (Overlapping window)
 0.8 │      │
 0.6 │     / ╲
 0.4 │    /   ╲  Found AFTER lost (half-life = 48h)
 0.2 │   /     '─.
 0.0 ┴──┴─────────┴─────────────► Time Gap (Hours)
   Found BEFORE lost
   (half-life = 6h)
```

### 4. Dynamic Weight Renormalization
Initial target weights are:
$$w_{\text{text}} = 0.40, \quad w_{\text{image}} = 0.35, \quad w_{\text{location}} = 0.15, \quad w_{\text{time}} = 0.10$$

**Crucial Viva Point**: What happens if a student does not upload a photo?
* If missing signals were treated as $0.0$, the maximum possible score would drop from $1.0$ to $0.65$, unfairly penalizing honest students who do not have a photo.
* **Our Approach**: We exclude `None` signals and **renormalize** active weights over their sum:
  $$\text{Score} = \frac{\sum_{i \in \text{available}} w_i \cdot s_i}{\sum_{i \in \text{available}} w_i}$$
  *Example*: If image is missing, remaining weights sum to $0.40 + 0.15 + 0.10 = 0.65$. Each weight is divided by $0.65$, scaling the remaining signals back to a full $1.0$ maximum.

### 5. Additive Plain-Language Explanations
For transparency, signal contributions $c_i$ are computed:
$$c_i = \frac{w_i \cdot s_i}{\sum_{j} w_j} \quad \implies \quad \sum c_i = \text{Combined Score} \quad (\pm 10^{-9})$$
The UI highlights any signal contributing $\ge 10\%$ of the score in plain language:
* *"Similar description (+0.42)"*
* *"Reported in an adjacent building (+0.12)"*
* *"Reported within 3 hours (+0.18)"*

---

## 9. Subsystem 6: Claim Verification & Cryptographic Handover Desk

### The Claim Lifecycle & 30-Minute Moderator Lock
When a user sees a found item matching their lost belonging, they submit a claim:
* Must provide between 20 and 2,000 characters of evidence.
* Must answer every verification question set by the finder (e.g. *"What charm is on the zipper?"*).
* **30-Minute Review Lock**: When a moderator opens a claim, the system sets `locked_by_id = moderator.id` and `lock_expires_at = now + 30m`. If another staff member opens it, they get `409 claim_locked`, preventing conflicting decisions. Expired locks automatically free up.
* **Conflict of Interest**: A moderator cannot review a claim on an item they reported finding, or a claim they filed themselves (`403 conflict_of_interest`).

### The Handover Code Cryptography ([`app/domain/handover.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/handover.py))

```
[Claim Approved by Moderator]
             │
             ▼
System generates 8-char random Base32: "7K9M-2P4X"
             │
             ├──────────────────────────────────────────┐
             ▼                                          ▼
Shown ONCE to Claimant (In-App & Email)       HMAC-SHA256(Secret, "7K9M2P4X")
             │                                          │
             ▼                                          ▼
   Claimant goes to desk                    Stored in PostgreSQL `handovers` table
             │                              (Raw code is NEVER stored)
             ▼
Moderator types code at desk
             │
             ▼ Normalization ("o" -> "0", "l" -> "1", strip hyphens)
             ▼ HMAC-SHA256 candidate
             ▼ Constant-time comparison (`hmac.compare_digest`)
             │
     ┌───────┴───────┐
     ▼               ▼
  Success         Failure (attempts incremented)
(Item returned)   (After 5 failed attempts -> 423 Handover Locked)
```

1. **Crockford Base32 Alphabet**: `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (32 characters). The letters `I`, `L`, and `O` are excluded to eliminate confusion with numbers `1` and `0`.
2. **Entropy & Brute Force Resilience**:
   $$\text{Entropy} = \log_2(32^8) = \log_2((2^5)^8) = 40\text{ bits} \quad (1,099,511,627,776\text{ permutations})$$
   With a strict **5-attempt lockout**, the probability of an attacker guessing a valid code is:
   $$P(\text{guess}) = \frac{5}{2^{40}} \approx 4.5 \times 10^{-12}$$
3. **Why HMAC-SHA256 instead of plain SHA-256?**: If a database dump is leaked, $2^{40}$ states can be precomputed or brute-forced in hours using a GPU rainbow table. With secret-keyed HMAC, an attacker cannot verify candidate codes without the server's private secret.
4. **Optical Normalization**: Automatically transforms `o`/`O` $\to$ `0`, and `i`/`I`/`l`/`L` $\to$ `1`, preventing innocent students from getting locked out due to handwriting or font confusion.
5. **Zero-Knowledge Desk**: The moderator desk screen displays only binary success/failure and attempts remaining. Staff never see the code or hash.
6. **Atomic Verification Transaction**: In a single database transaction, code verification:
   * Marks handover as `completed`.
   * Sets found item to `returned`.
   * Sets linked lost report to `resolved`.
   * Bulk-rejects competing open claims with reason `item_returned`.
   * Writes an immutable audit entry.

---

## 10. Subsystem 7: Transactional Outbox & Concurrency Architecture

### The Dual-Write Problem
When an API changes state (e.g., approves a claim) and needs to notify an external service (e.g., send an email via SMTP or trigger GPU embeddings):
* If you call SMTP *after* committing to Postgres and SMTP crashes $\implies$ the user never receives their handover code.
* If you call SMTP *before* committing to Postgres and Postgres aborts $\implies$ the user gets an email for an action that never happened (ghost notification).

### The Solution: Transactional Outbox Pattern
Instead of calling external services during the web request, the API writes a job row to the `jobs` table and a notification row to `notifications` **inside the exact same ACID transaction** as the business logic:

```
BEGIN TRANSACTION;
  UPDATE item_reports SET status = 'reserved' WHERE id = ...;
  UPDATE claims SET status = 'approved' WHERE id = ...;
  INSERT INTO jobs (task_name, payload) VALUES ('embed_report_text', ...);
  INSERT INTO notifications (user_id, event_key, body) VALUES (...);
COMMIT;
```
If the transaction fails, everything rolls back. If it commits, the job and notification are durably persisted in Postgres.

### Lock-Free Worker Concurrency (`SELECT FOR UPDATE SKIP LOCKED`)
The background worker executes this query to claim pending jobs:
```sql
SELECT id, task_name, payload
FROM jobs
WHERE status = 'pending' AND run_after <= NOW()
ORDER BY priority DESC, id ASC
LIMIT 10
FOR UPDATE SKIP LOCKED;
```
* `FOR UPDATE`: Locks the selected rows.
* `SKIP LOCKED`: Any rows currently locked by another worker instance are skipped immediately without blocking.
* **Advantage**: Multiple worker containers can run concurrently without distributed locking mechanisms like Redis, ZooKeeper, or Celery.

---

## 11. Subsystem 8: The Empirical AI Research & Evaluation Framework

### The Research Question
> *"Does combining dense text embeddings, cross-modal image similarity, hierarchical campus location, and time decay significantly improve lost-item retrieval over traditional keyword search (BM25)?"*

### Experimental Setup & Dataset Split
* **Synthetic Generator ([`eval/generator.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/eval/generator.py))**: Generates 300 ground-truth query-candidate pairs across 12 campus categories, 100 background unclaimed reports, and 40 leaf locations with calibrated spatial and temporal noise.
* **Stratified Split**:
  * **30% Development Set** (90 items): Used exclusively for tuning weights and training fusion models.
  * **70% Test Set** (210 queries $\times$ 310 candidates): Evaluated exactly once.
* **Programmatic Leakage Prevention ([`eval/protocol.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/eval/protocol.py))**: The `TuningHarness` raises a `DataLeakageError` immediately if hyperparameter tuning code attempts to access the test split. The tuned configuration is hashed with SHA-256 and frozen before running on test data.

### Evaluated Systems & Metrics

| System ID | Retrieval Engine | Description |
| :--- | :--- | :--- |
| **System A** | **BM25** | Okapi BM25 keyword search baseline (lexical matching) |
| **System B** | **Text Embedding** | Semantic text similarity using `all-MiniLM-L6-v2` |
| **System C** | **Image Similarity** | Visual similarity using `CLIP ViT-B/32` (unvalidated; no photos collected) |
| **System D** | **Hand-Weighted Hybrid** | Grid-search tuned weights: text 0.40, location 0.30, time 0.30 |
| **System E** | **Learned Fusion** | Logistic regression trained on the dev set to predict relevance from signals |

### Benchmark Results (Seed 42, Test Split)

| System | Mean Reciprocal Rank (MRR) | 95% Confidence Interval | Recall@1 | Recall@10 |
| :--- | :---: | :---: | :---: | :---: |
| **System A (BM25)** | `0.120` | [0.090, 0.153] | 6.2% | 23.3% |
| **System B (MiniLM)** | `0.342` | [0.293, 0.389] | 19.5% | 65.7% |
| **System D (Hybrid)** | `0.959` | [0.938, 0.979] | 93.3% | 99.5% |
| **System E (Learned)** | `0.982` | [0.966, 0.994] | 97.1% | 100.0% |

### Scientific Rigor & Pre-Registered Hypothesis ($H_1$)
* **Hypothesis $H_1$**: Hybrid retrieval (System D) achieves a statistically significant improvement in MRR over text-only embeddings (System B).
* **Statistical Method**: **Paired Bootstrap Resampling** (1,000 resamples across queries).
* **Result**: **Hypothesis Supported**. $\Delta \text{MRR} = 0.618$, paired 95% CI $[0.568, 0.669]$ (interval strictly excludes 0).
* **Honest Scientific Disclosure**: As documented in [`eval/HYPOTHESES.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/eval/HYPOTHESES.md), most of the jump between System B (0.342) and System D (0.959) is **by construction**—the synthetic generator places items according to physical assumptions (same building, within hours) that the scoring formulas reward. The most informative semantic result is that **MiniLM roughly triples BM25 (0.342 vs 0.120)** when lost and found reports use different words.

---

## 12. Subsystem 9: Frontend Architecture & Accessibility

* **Framework**: React 18 + TypeScript + Vite.
* **End-to-End Type Safety**: Frontend API types are generated directly from the backend's OpenAPI specification (`npm run gen:api`). If a backend schema changes, TypeScript compiler catches mismatched fields at build time.
* **Zero Mock UI**: The client never fabricates mock data; every screen is wired directly to backend endpoints.
* **Accessibility (WCAG AA Compliance)**:
  * **360px Viewport Support**: Handled via CSS flexbox/grid without horizontal scrolling (`overflow-x: hidden`), allowing seamless use on small budget smartphones.
  * **Visible Focus Indicators**: High-contrast outline on all interactive buttons and inputs (`:focus-visible`).
  * **Screen Reader Associations**: Form errors are programmatically linked to inputs using `aria-describedby` and `aria-invalid`.
  * **No Color-Only Information**: Status badges combine distinct colors with descriptive text labels and icons.

---

## 13. Subsystem 10: Cloud & Local Deployment Mechanics

### Multi-Container Stack (Docker Compose)
* [`docker-compose.yml`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docker-compose.yml) orchestrates 5 services:
  1. `db`: PostgreSQL 16 with `pgvector` pre-installed.
  2. `backend`: FastAPI running under Uvicorn.
  3. `worker`: Background Python process running `run_worker_loop()`.
  4. `frontend`: Nginx serving compiled static assets and reverse-proxying `/api` to the backend.
  5. `mail`: Mailpit running SMTP server (`:1025`) and web UI (`:8025`).

### Unified Cloud Production Deployment ([`Dockerfile.web`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/Dockerfile.web))
For platforms like Render or Railway:
1. **Multi-stage Docker Build**:
   * Stage 1: Builds the React client using Node.js (`npm run build`), generating static HTML/CSS/JS in `frontend/dist`.
   * Stage 2: Installs Python dependencies, copies backend code, and copies `frontend/dist` into the backend container.
2. **Execution**:
   * FastAPI mounts `frontend/dist` as static files and serves `index.html` on root routes.
   * Runs database migrations (`alembic upgrade head`) and seeds demo accounts on startup.
   * Runs the background worker in an async task within the same process (`RUN_WORKER_IN_PROCESS=true`), enabling full functionality on a single free-tier cloud instance.

---

## 14. Examiner Viva Cheat Sheet (Quick-Fire Technical Answers)

If asked these common viva questions, deliver these precise technical answers:

| Question | Model Answer |
| :--- | :--- |
| **Q1: Why did you not use a pre-built search service like ElasticSearch?** | *"ElasticSearch adds another heavy Java service to maintain and introduces the dual-write problem. PostgreSQL provides full-text search (`tsvector` + GIN index) and vector similarity (`pgvector` + HNSW index) in a single ACID database alongside our application data."* |
| **Q2: Why use asymmetric time decay instead of standard symmetric decay?** | *"Because time in physical reality has a causal direction. An item cannot be found before it was lost, except for slight human memory error (penalized steeply with a 6-hour half-life). An item can easily be found days or weeks after it was lost (penalized gradually with a 48-hour half-life)."* |
| **Q3: What prevents an attacker from guessing an 8-character handover code?** | *"The Crockford Base32 alphabet provides $32^8 = 2^{40}$ permutations (40 bits of entropy). Combined with our 5-attempt lockout, the odds of a random guess succeeding are $5 / 2^{40} \approx 4.5 \times 10^{-12}$. The codes expire after 48 hours."* |
| **Q4: Why store an HMAC of the code instead of the plain code or a simple SHA-256?** | *"Storing plain text exposes the code to any database administrator or SQL injection. A plain SHA-256 hash of a 40-bit space can be brute-forced with GPU rainbow tables in hours. HMAC-SHA256 requires the secret key held only in server environment variables, making offline cracking impossible."* |
| **Q5: Why is the AI matching score strictly advisory?** | *"Similarity is not ownership. An attacker could find a public photo of an identical laptop and submit a claim with a 99% similarity score. Human staff must verify unique, non-public details (serial numbers, engravings, or answers to verification prompts) before handing over the item."* |
| **Q6: How do you prevent data leakage during research evaluation?** | *"Our `TuningHarness` raises a `DataLeakageError` if tuning code attempts to access the 70% test split. Weights and hyperparameters are tuned strictly on the 30% development split, frozen with a SHA-256 hash, and evaluated once on the test split."* |
| **Q7: What is the benefit of `SELECT FOR UPDATE SKIP LOCKED`?** | *"It allows multiple background workers to pull jobs from a relational table concurrently without race conditions, deadlocks, or needing an external message broker like Redis or RabbitMQ."* |
| **Q8: Why does the API return 404 instead of 403 on private resources?** | *"To prevent resource ID enumeration. A 403 tells an attacker that the private report or claim ID exists. A 404 makes unauthorized resources indistinguishable from non-existent resources."* |


</details>

---

## Turn 6

**User Interaction:**
```
what models are used in this project
```

*Metadata:* `Timestamp: 2026-10-27T16:31:59+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


In this project, two primary deep learning neural networks are used in the core matching engine, alongside two classical machine learning / information retrieval models in the research evaluation suite:

---

### 1. The Core Deep Learning Models (In Production)

#### A. Text Semantic Model: `all-MiniLM-L6-v2`
* **Type**: Dense Sentence-Transformer (BERT-based bi-encoder).
* **Embedding Dimension**: **384 dimensions**.
* **Model Size**: ~80 MB (extremely lightweight).
* **What it does**: 
  * Converts the item's text string (`category + " " + title + " " + description`) into a normalized 384-dimensional vector.
  * Calculates semantic cosine similarity between lost reports and found reports.
* **Why it was chosen**:
  * Lightning fast CPU inference (<15 ms per query), meaning it does not require an expensive GPU server.
  * Captures synonyms that keyword searches miss (e.g., matches *"laptop"* with *"ThinkPad notebook"*). In the benchmark evaluation, it roughly **triples the retrieval performance of keyword search** (MRR 0.342 vs 0.120).

---

#### B. Visual & Cross-Modal Model: `CLIP ViT-B/32`
* **Type**: Vision Transformer (Contrastive Language-Image Pre-training by OpenAI).
* **Embedding Dimension**: **512 dimensions**.
* **Model Size**: ~350 MB.
* **What it does**:
  * Projects **both images and text into the exact same 512-dimensional vector space**.
  * **Image-to-Image Matching**: Compares photo vectors when both reports include pictures.
  * **Text-to-Image Cross-Modal Matching**: When a student reports a lost item with text only, but the finder uploaded a photo without a detailed description, CLIP compares the lost report's text vector directly against the found item's photo vector.
* **Why it was chosen**:
  * Enables zero-shot visual similarity and cross-modal search without training a custom campus image classifier from scratch.

---

### 2. Classical Machine Learning & Retrieval Models (In Research / Eval)

#### C. Lexical Keyword Baseline: `Okapi BM25`
* **Type**: Probabilistic Information Retrieval ranking function (BM25 with Robertson-Spärck Jones IDF).
* **What it does**: 
  * Acts as the baseline (System A) in the benchmark evaluation to represent traditional keyword search engines.
  * Proves empirically why modern semantic vectors outperform keyword matching in real-world scenarios with vocabulary mismatches.

#### D. Learned Fusion Model: `Logistic Regression` (`scikit-learn`)
* **Type**: Supervised classification model.
* **What it does**:
  * Powers **System E (Learned Fusion)** in the benchmark.
  * Instead of hand-picked heuristic weights (e.g., 0.40 text, 0.35 image, 0.15 location, 0.10 time), it is trained strictly on the 30% development split to learn the optimal mathematical weighting of all signals to predict true matches (achieving an MRR of **0.982**).

---

### 3. Auxiliary Image Hashing Algorithm

#### E. Perceptual Difference Hashing (`64-bit dHash`)
* **Type**: Perceptual image hashing algorithm (implemented using Pillow).
* **What it does**:
  * Converts uploaded photos into 64-bit binary integers based on relative gradient brightness across an $8 \times 8$ grid.
  * Detects duplicate or near-identical image submissions (Hamming distance $\le 10$) to flag spam or repeated submissions in the staff queue.

---

### 4. Fast Testing Model: `StandinEmbedder`

* **What it is**: A deterministic SHA-256 hash-based vector generator.
* **Why it exists**: Running PyTorch or downloading 400 MB of model weights during automated CI tests would make test suites slow and dependent on external networks. The `StandinEmbedder` generates deterministic 384-d and 512-d unit vectors instantly in tests with **zero network calls and zero GPU/CPU load**.

---

### How These Models are Deployed (Key Viva Point)

* **Pinned Checksums**: Model weights are pinned by exact git commit hash and SHA-256 checksum in [`backend/models.lock.json`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/models.lock.json).
* **100% Offline / Air-Gapped**: The weights are downloaded and verified **at Docker build time** and baked directly into the image at `/models`. At runtime, the application runs with `HF_HUB_OFFLINE=1`—it never connects to HuggingFace or third-party cloud APIs.
* **Stored in pgvector**: Vectors are stored in PostgreSQL using the `pgvector` extension and queried via an **HNSW (Hierarchical Navigable Small World) index** using cosine distance (`vector_cosine_ops`).


</details>

---

## Turn 7

**User Interaction:**
```
where does A and B work
```

*Metadata:* `Timestamp: 2026-10-27T16:38:48+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


Depending on whether you mean **the two AI models**, **the research benchmark systems**, or **the two demo students**, here is exactly where each one works:

---

### 1. If you mean the two AI Models:
* **Model A: `all-MiniLM-L6-v2` (Text Embeddings)**
* **Model B: `CLIP ViT-B/32` (Vision & Cross-Modal Embeddings)**

Here is their exact lifecycle and where they execute in the system:

```
[User submits Report or Photo via FastAPI]
                   │
                   ▼ (1. Writes job to PostgreSQL `jobs` table)
[Background Worker Process: app/worker/main.py]
                   │
                   ▼ (2. Calls app/services/embedder.py)
   ┌────────────────────────────────────────────────────────┐
   │ Model A (MiniLM): Encodes (category + title + desc)   │
   │ Model B (CLIP):   Encodes uploaded photo & text       │
   └────────────────────────────────────────────────────────┘
                   │
                   ▼ (3. Writes vectors to PostgreSQL)
   ┌────────────────────────────────────────────────────────┐
   │ PostgreSQL pgvector:                                   │
   │  - Model A vectors -> `text_embeddings` table (384-d)  │
   │  - Model B vectors -> `image_embeddings` table (512-d) │
   └────────────────────────────────────────────────────────┘
                   │
                   ▼ (4. Computes Similarity in app/services/matching.py)
   Uses HNSW cosine distance (`vector_cosine_ops`) to find nearest neighbors!
```

#### Where they live in the Codebase:
1. **Execution**: [`backend/app/services/embedder.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/services/embedder.py) loads both models into memory using `sentence-transformers` and `open-clip-torch`.
2. **Background Worker**: [`backend/app/services/job_runner.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/services/job_runner.py) executes the inference asynchronously so the web API never freezes.
3. **Weights on Disk**: Baked into `/models` inside the Docker image (configured in [`backend/models.lock.json`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/models.lock.json)).
4. **Database Tables**:
   * Model A stores in table `text_embeddings` (`column: vector(384)`).
   * Model B stores in table `image_embeddings` (`column: vector(512)`).

---

### 2. If you mean the Research Evaluation Systems:
* **System A: Okapi BM25 (Keyword Baseline)**
* **System B: MiniLM (Dense Semantic Text Baseline)**

These work inside the **Evaluation Benchmark Framework** ([`eval/`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/eval/)):
* **System A (BM25)** works in [`eval/bm25.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/eval/bm25.py):
  * Builds an inverted token index from item titles and descriptions.
  * Scores matches using classical term frequency (TF) and inverse document frequency (IDF).
* **System B (MiniLM)** works in [`eval/systems.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/eval/systems.py):
  * Computes 384-d sentence embeddings for the same reports.
  * Ranks candidates purely by vector cosine similarity.
* Both are executed by the runner ([`eval/runner.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/eval/runner.py)) against the held-out 70% test split to prove that **System B roughly triples the retrieval accuracy of System A** (MRR 0.342 vs 0.120).

---

### 3. If you mean Student A and Student B (The Demo Users):
In the project blueprint and end-to-end demo test ([`test_ac_146_demo_journey.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_146_demo_journey.py)):

* **Student A (Alice - `student1@campus.edu`)**:
  * **Role**: The person who **lost an item**.
  * **Where she acts**: Reports her lost "Matte Black ThinkPad X1" with a photo $\to$ receives match notification $\to$ reviews match explanation $\to$ submits a claim with private serial number $\to$ receives the single-use 8-character handover code $\to$ collects the laptop at the campus desk.
* **Student B (Bob - `student2@campus.edu`)**:
  * **Role**: The person who **found an item**.
  * **Where he acts**: Reports finding a "Black Lenovo Notebook" in the campus library $\to$ adds verification question (*"What OS sticker is on the lid?"*) $\to$ hands the laptop over to the campus desk. Once verified, Bob receives a notification that the item was successfully returned.


</details>

---

## Turn 8

**User Interaction:**
```
how does FASTAPI work
```

*Metadata:* `Timestamp: 2026-10-27T16:44:40+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


To understand **how FastAPI works**, think of it as an assembly line made of **4 interconnected layers**:

```
[Browser / Frontend Request: JSON]
               │
               ▼
   1. UVICORN (The ASGI Web Server)
      Listens on port 8000, accepts raw network bytes
               │
               ▼
   2. MIDDLEWARES & STARLETTE (The Gateway)
      Checks security headers, body size (1 MB limit), CORS
               │
               ▼
   3. PYDANTIC (The Validator / Translator)
      Parses raw JSON, validates types, blocks malicious extra fields
               │
               ▼
   4. FASTAPI ROUTE & DEPENDENCY INJECTION (Your Python Code)
      Verifies user session, runs database queries, calls domain logic
               │
               ▼
[Browser receives clean, filtered JSON Response]
```

---

### Step-by-Step: The Journey of a Request

Let’s trace a real example from this project: **A student submits a lost report (`POST /api/reports/lost`)**.

#### Step 1: Uvicorn Receives the Raw Network Traffic
FastAPI doesn't listen to network ports by itself. It needs an **ASGI Server** called **Uvicorn**:
* Uvicorn listens on port `8000` (`http://localhost:8000`).
* When the browser sends raw HTTP text across the network, Uvicorn accepts the connection and converts it into a standard Python dictionary called the **ASGI scope**.

---

#### Step 2: Middlewares Process the Request First
Before your route code is touched, the request flows through FastAPI middlewares configured in [`backend/app/main.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/main.py):
1. **`MaxBodySizeMiddleware`**: Checks the `Content-Length` header. If an attacker sends a 50 MB payload, FastAPI rejects it instantly with `413 Request Entity Too Large` before server memory is wasted.
2. **`CORSMiddleware`**: Checks if the request is coming from an allowed origin (`http://localhost:8080`).
3. **`SecurityHeadersMiddleware`**: Prepares required security headers (`X-Content-Type-Options: nosniff`, `Content-Security-Policy`).

---

#### Step 3: Dependency Injection (`Depends`)
FastAPI has a built-in **Dependency Injection** system. Before calling your route function, it automatically resolves whatever your function needs:

```python
# In backend/app/api/reports.py
@router.post("/reports/lost")
async def create_lost_report(
    payload: CreateLostReportRequest,
    current_user: User = Depends(get_current_user), # <--- Dependency 1
    db: AsyncSession = Depends(get_db),             # <--- Dependency 2
):
```
* **Authentication**: `Depends(get_current_user)` reads the `session_token` cookie, queries PostgreSQL, and checks if the session is valid and not expired. If invalid, FastAPI automatically halts and returns `401 Unauthorized`.
* **Database Connection**: `Depends(get_db)` automatically checks out an async database connection from the connection pool and closes/cleans it up when the request finishes.

---

#### Step 4: Automatic Validation via Pydantic
FastAPI uses **Python Type Hints** and **Pydantic** to inspect the incoming JSON body:

```python
class CreateLostReportRequest(BaseModel):
    model_config = ConfigDict(extra="forbid") # Rejects unexpected fields
    title: str
    description: str
    category: str
    location_id: UUID
```
* **Type Conversion**: Converts incoming strings like `"2026-10-27"` into Python `datetime` objects and `"a1b2c3..."` into UUID objects.
* **Instant Error Catching**: If the user misses the `title` or passes an invalid `category`, FastAPI halts execution and returns a detailed `422 Unprocessable Entity` JSON error explaining exactly which line failed. Your business code never receives corrupt data!
* **`extra="forbid"`**: If an attacker tries to inject `{ "is_admin": true }`, Pydantic sees it's not in the schema and rejects the entire request.

---

#### Step 5: The Non-Blocking Async Event Loop (`async` / `await`)
This is the secret to FastAPI’s speed. 

In traditional Python frameworks (like older Flask/Django), the server uses threads. When a request asks PostgreSQL to run a query, the thread freezes and sits idle waiting for the disk.
FastAPI runs on a single **Asynchronous Event Loop**:
```python
# The 'await' keyword pauses this function and frees the CPU
report = await db.execute(select(ItemReport)...)
```
While waiting 10 milliseconds for PostgreSQL to find matching items, FastAPI immediately pauses that request and uses the CPU to process another student’s login request.

---

#### Step 6: Response Serialization & Security Whitelisting
When your function returns a Python object, FastAPI formats it using the endpoint's `response_model`:
```python
@router.get("/found", response_model=PublicFoundListResponse)
```
* Even if the database object contains secret columns (like `verification_prompts`, `reporter_id`, or `claim_evidence`), FastAPI strips them out unless they are explicitly declared in `PublicFoundListResponse`. 
* This enforces **Default-Deny Privacy** across the entire application.

---

### Summary: Why is FastAPI So Popular? (The "Triad")

| Component | What it does under the hood |
| :--- | :--- |
| **Starlette** | Handles the web mechanics: routing, HTTP requests/responses, cookies, and CORS. |
| **Pydantic (v2)** | Written in **Rust** for maximum speed. Handles all data parsing, type-checking, and schema validation. |
| **Uvicorn** | The lightning-fast ASGI web server that handles the raw TCP network traffic. |

**Your 15-Second Viva Answer**:
> *"FastAPI works by combining **Starlette** for async HTTP routing with **Pydantic** for schema validation and data serialization.*  
> *When a request arrives through the **Uvicorn** ASGI server, FastAPI automatically authenticates the user via dependency injection, validates the JSON payload against strict type hints, executes non-blocking database queries on the async event loop, and filters outgoing data through default-deny response schemas."*


</details>

---

## Turn 9

**User Interaction:**
```
how does the encryption code work
```

*Metadata:* `Timestamp: 2026-10-27T16:50:07+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


In cryptography, there is a fundamental rule that examiners love to test:
> **Crucial Viva Distinction**: We do **not** use two-way *encryption* (which can be decrypted back to plaintext). Instead, we use **One-Way Cryptographic Hashing and HMAC** (Hash-based Message Authentication Codes). Once hashed, **nobody—not even the database administrator—can reverse it back to the original text**.

The project uses cryptographic security in two key places:
1. **The Handover Verification Code** (HMAC-SHA256 with Crockford Base32)
2. **User Password Security** (Argon2id + Timing Attack Defense)

Here is a full breakdown of how each one works under the hood.

---

### Part 1: The Handover Verification Code (HMAC-SHA256)

When a student’s claim is approved, the system generates an **8-character code** (e.g., `7K9M-2P4X`) that the student shows at the physical campus desk. 

Here is the exact 5-step cryptographic pipeline implemented in [`backend/app/domain/handover.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/handover.py):

```
Step 1: Cryptographic Random Generation
        Alphabet: 32 chars (no I, L, O) ──► "7K9M-2P4X"
                           │
                           ├──────────────────────────────────┐
                           ▼                                  ▼
                Sent ONLY to Claimant            Step 2: Normalization
                (Displayed on phone screen)      Strips '-' and spaces
                                                 Replaces 'O'->'0', 'I'->'1'
                                                              │
                                                              ▼
                                                 Step 3: HMAC-SHA256 Hash
                                                 HMAC(SECRET_KEY, "7K9M2P4X")
                                                              │
                                                              ▼
                                                 Stored in Database
                                                 (Raw code is NEVER stored!)
```

#### Step 1: Cryptographically Secure Random Generation
Standard random functions (like Python's `random.choice`) use pseudo-random seeds that can be predicted by attackers. We use Python’s hardware-level **`secrets`** module:
```python
HANDOVER_ALPHABET = "0123456789ABCDEFGHJKMNPQRSTVWXYZ" # 32 characters

def generate_handover_code(length=8) -> str:
    return "".join(secrets.choice(HANDOVER_ALPHABET) for _ in range(length))
```
* **Why 32 characters?** Letters like `I`, `L`, and `O` are excluded so users don't confuse them with digits `1` and `0`.
* **Entropy**: Each character carries $\log_2(32) = 5\text{ bits}$ of entropy. For 8 characters:
  $$5 \times 8 = 40\text{ bits of entropy} \quad (1,099,511,627,776\text{ possible codes})$$

---

#### Step 2: Optical Normalization
When a student types the code or dictates it to staff at a physical desk, human error happens. The normalization function cleans the input before any cryptographic checks:
```python
def normalize_handover_code(raw: str) -> str:
    cleaned = re.sub(r"[\s\-]+", "", raw.strip()).upper()
    cleaned = cleaned.replace("O", "0")
    cleaned = cleaned.replace("I", "1")
    cleaned = cleaned.replace("L", "1")
    return cleaned
```
* Typing `7k9m-2p4x`, `7K9M 2P4X`, or mistyping `O` instead of `0` all resolve to the exact same clean string: `7K9M2P4X`.

---

#### Step 3: Secret-Keyed HMAC-SHA256 Storage
```python
def compute_code_hmac(secret: str, normalized_code: str) -> str:
    key_bytes = secret.encode("utf-8")
    msg_bytes = normalized_code.encode("utf-8")
    return hmac.new(key_bytes, msg_bytes, hashlib.sha256).hexdigest()
```
* **Why HMAC instead of standard SHA-256?**
  * A 40-bit search space has $\approx 1.1 \text{ trillion}$ possibilities. If an attacker stole a SQL database dump containing plain `sha256(code)`, a modern GPU could pre-compute a rainbow table and reverse all codes in a few hours.
  * **HMAC requires a private server secret (`SECRET_KEY`)**. Even with a full database dump, the attacker cannot reverse or verify any code without stealing the server's private environment variable.

---

#### Step 4: Constant-Time Verification (`hmac.compare_digest`)
When staff enter the code at the desk, the system checks it:
```python
def verify_code_constant_time(secret: str, raw_input_code: str, stored_hmac: str) -> bool:
    normalized = normalize_handover_code(raw_input_code)
    candidate_hmac = compute_code_hmac(secret, normalized)
    return hmac.compare_digest(stored_hmac, candidate_hmac)
```
* **What is a Timing Attack?** Standard string comparison (`if a == b:`) compares characters one-by-one and stops at the first mismatch. An attacker with a high-precision timer could guess character-by-character based on whether the response took 2 microseconds or 4 microseconds.
* `hmac.compare_digest` runs in **constant time** regardless of where a mismatch occurs, preventing timing attacks.

---

#### Step 5: Lockout & Expiration Bounds
* **5-Attempt Lockout**: If an attacker attempts to brute force codes at the desk, the handover locks on the 5th failed attempt (`HTTP 423 Handover Locked`).
  $$\text{Probability of guessing correctly} = \frac{5}{2^{40}} \approx 4.5 \times 10^{-12}$$
* **48-Hour Lifetime**: Codes automatically expire after 48 hours. If unclaimed, the found item reverts back to `open`.

---

### Part 2: Password Cryptography (Argon2id)

Passwords in [`backend/app/core/auth.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/core/auth.py) are hashed with **Argon2id**:
* **Why not bcrypt or SHA-256?**
  * SHA-256 is designed to be fast, making it easy to crack at billions of guesses per second on GPUs.
  * **Argon2id** is a **memory-hard algorithm**. It forces the CPU to allocate several megabytes of RAM and run multiple iterations for a single hash, making GPU/ASIC parallel cracking economically impossible.
* **Mitigating User Enumeration via `verify_dummy_password`**:
  * If a user tries to log in with an email that doesn't exist, a naive system returns immediately (`<1 ms`), but if the email exists and the password is wrong, Argon2 takes `50 ms` to check.
  * Attackers use this time difference to find out which emails are registered on campus.
  * Our system runs `verify_dummy_password()` even when the email does not exist, ensuring **every failed login takes the exact same amount of time**.

---

### Quick Viva Summary to Memorize

> *"We do not use reversible encryption because plaintext codes and passwords should never be recoverable. Instead, we use **one-way cryptographic primitives**:*
> 1. *For passwords, we use **Argon2id**, a memory-hard algorithm resistant to GPU cracking.*
> 2. *For handovers, we generate **8-character Crockford Base32 codes** (40 bits of entropy), store only their **HMAC-SHA256 digests**, and verify them in **constant time** with a **5-attempt lockout** ($4.5 \times 10^{-12}$ collision odds)."*


</details>

---

## Turn 10

**User Interaction:**
```
what is hashing
```

*Metadata:* `Timestamp: 2026-10-27T17:03:09+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


### What is Hashing?

**Hashing** is a mathematical process that takes an input of **any size** (a single letter, a password, or an entire encyclopedia) and converts it into a **fixed-length fingerprint** of characters (called a **hash**, **digest**, or **checksum**).

---

### The Real-World Analogy: The Blender

Think of hashing like making a smoothie:
* You put a strawberry, a banana, and milk into a blender $\implies$ you get a specific pink smoothie.
* It is **one-way**: You can easily turn the fruit into the smoothie, but you **can never turn the smoothie back into an intact strawberry and banana**.
* It is **deterministic**: If you put the exact same ingredients in, you will always get the exact same smoothie.
* If you change just one tiny ingredient (add a single blueberry) $\implies$ the color and taste completely change (**The Avalanche Effect**).

```
   INPUT                       HASH FUNCTION                    OUTPUT HASH (Fixed Length)
"secret"          ──► [ SHA-256 Algorithm ] ──► 2bb80e14... (64 hex characters)
"secret1"         ──► [ SHA-256 Algorithm ] ──► 65427131... (Completely different!)
"Entire Book"     ──► [ SHA-256 Algorithm ] ──► 9f86d081... (Still 64 hex characters!)
```

---

### The 4 Golden Rules of Hashing

1. **One-Way (Irreversible)**:
   Given the output hash, it is mathematically impossible to calculate what the original input was.
2. **Deterministic**:
   Hashing `"Campus2026!"` today, tomorrow, or in 10 years will always produce the exact same sequence of characters.
3. **Fixed Length**:
   Whether the input is 4 letters or a 10 GB video, the resulting hash length is always fixed (e.g., SHA-256 is always **256 bits / 64 hexadecimal characters**).
4. **The Avalanche Effect**:
   Changing even a single punctuation mark, space, or capitalization completely scrambles the output hash beyond recognition.

---

### Top Viva Question: *"What is the difference between Hashing and Encryption?"*

Examiners ask this question constantly because students often confuse the two:

| Feature | **Hashing** | **Encryption** |
| :--- | :--- | :--- |
| **Direction** | **One-way** (Cannot be reversed) | **Two-way** (Can be decrypted back to plaintext) |
| **Purpose** | Verification, integrity, storing passwords | Confidentiality, sending private messages |
| **Keys** | Does not require a key to compute | Requires an encryption key and a decryption key |
| **Example** | Storing passwords in a database | Sending encrypted messages over WhatsApp |

---

### Where is Hashing Used in THIS Project?

Your project uses hashing in 4 different places:

1. **User Passwords (`Argon2id`)**:
   When you register with password `"CampusPass2026!"`, the database never stores that string. It stores an Argon2id hash. When you log in, the system hashes what you typed and checks if the two hashes match.
2. **Handover Codes (`HMAC-SHA256`)**:
   The single-use 8-character handover code (`7K9M-2P4X`) is hashed with a server secret before being saved in PostgreSQL. If an attacker hacks the database, they cannot read the codes.
3. **Duplicate Photo Detection (`64-bit dHash`)**:
   Instead of comparing large image files byte-by-byte, Pillow converts each photo into a 64-bit integer hash based on pixel gradient brightness. If two photos have nearly identical hashes (Hamming distance $\le 10$), they are flagged as duplicate submissions.
4. **Model & Benchmark Integrity (`SHA-256`)**:
   In [`backend/models.lock.json`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/models.lock.json), the exact SHA-256 checksums of the pretrained ML weights are saved to guarantee the model files have not been modified or corrupted.

---

### Your 15-Second Viva Answer

> *"Hashing is a one-way mathematical function that converts arbitrary-length input data into a unique, fixed-length digest.*  
> *Unlike two-way encryption, hashing cannot be reversed. In our project, it is used with Argon2id for secure password storage, HMAC-SHA256 for tamper-proof handover codes, and 64-bit perceptual dHash for duplicate photo detection."*


</details>

---

## Turn 11

**User Interaction:**
```
Which campus email domain or domains will you allow, and who will be the moderators and admins in the demo?
```

*Metadata:* `Timestamp: 2026-10-27T17:06:10+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


Here are the exact configurations for allowed campus email domains and the pre-seeded demo accounts in the project:

---

### 1. Allowed Campus Email Domains

The application strictly validates the domain of any registering user using **exact domain matching** (configured in [`.env`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/.env) and [`backend/app/core/config.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/core/config.py)):

* **`campus.edu`** (Main university domain for staff and faculty)
* **`student.campus.edu`** (Official student email domain)
* **`iisc.ac.in`** (Institutional campus domain added for demo and testing)

> **Security Note**: The system uses exact domain matching, not keyword heuristics. Attackers attempting to register with spoofed domains like `evilcampus.com` or `campus.edu.attacker.net` are automatically rejected with `422 Unprocessable Entity`.

---

### 2. Moderators, Admins & Demo Accounts

All accounts are populated automatically by the idempotent seed script ([`backend/app/seed.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/seed.py)) and use Argon2id password hashing:

| Role | Email | Password | Display Name | Permissions & Intended Actions in Demo |
| :--- | :--- | :--- | :--- | :--- |
| **Admin** | `admin@campus.edu` | `CampusAdmin2026!` | Campus Administrator | • Activate/manage text and vision ML models in the Model Registry.<br>• Manage the hierarchical location tree and building adjacency pairings.<br>• Inspect the background job queue and trigger manual retries for failed jobs.<br>• Review immutable audit logs and manual retention sweeps.<br>• View the research benchmark evaluation results page. |
| **Moderator** | `moderator@campus.edu` | `CampusMod2026!` | Staff Moderator | • Access the Moderation Queue (reviewing pending found reports, duplicate photo flags, and escalated claims).<br>• Acquire exclusive 30-minute locks on student claims.<br>• Approve or reject claims with mandatory decision notes.<br>• Verify 8-character single-use codes at the physical Handover Desk.<br>• Monitor the Operational Analytics Dashboard (recovery rate, queue age). |
| **Student 1** *(User)* | `student1@campus.edu` | `StudentPass2026!` | Alice Student | • Reports lost belongings (e.g., lost Lenovo ThinkPad laptop).<br>• Views personalized match suggestions and additive explanations.<br>• Files claims on found items and receives the single-use handover code. |
| **Student 2** *(User)* | `student2@campus.edu` | `StudentPass2026!` | Bob Student | • Reports found items with verification questions.<br>• Browses the public found item catalog. |

*(Note: In the React frontend, the login page features 1-click demo buttons that automatically prefill these accounts for easy viva demonstrations).*


</details>

---

## Turn 12

**User Interaction:**
```
What stops a false claim, and what stops a dishonest moderator
```

*Metadata:* `Timestamp: 2026-10-27T17:08:50+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


This is one of the best questions an examiner can ask because it probes **threat modeling and trust boundaries**. The system was designed under the assumption that **both claimants and staff could act dishonestly or collude**.

Here is how the architecture defends against both threat vectors:

---

### Part 1: What Stops a False Claim? (Adversarial Claimants)

A malicious student tries to claim a valuable laptop or wallet they did not lose:

#### 1. Default-Deny Information Hiding
* **What they can’t see**: Public browse screens ([`PublicFoundItemSummary`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/schemas/report.py)) display only broad building-level locations (e.g. *"Engineering Library"*) and general descriptions.
* **What is hidden**: The exact floor, room number, finder identity, private descriptions (e.g. *"small dent on the HDMI port"*), and the finder’s secret verification questions are **completely stripped**. An attacker cannot claim what they cannot see.
* **Sensitive Categories**: Wallets and student ID cards **never show photos publicly** ([`S4`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/spec.md#L119)).

#### 2. The Finder's Verification Prompts
* To submit a claim, the claimant **must answer specific secret questions** set by the finder (e.g. *"What stickers are on the laptop lid?"*, *"What keychain is attached?"*).
* A random student guessing cannot answer these specific prompts.

#### 3. Strict Claim Throttling & Reputation Flagging
* **Hard Active Limits**: Normal users are capped at **3 active claims** at a time.
* **No Self-Claims**: A user cannot file a claim on an item they reported finding.
* **Repeat Offender Flagging ([`AC-84`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/test-plan.md#L125))**: If a user has 3 claims rejected within 30 days:
  * Their active claim limit is cut to **1 claim**.
  * Their account is automatically flagged with `claimant_flagged = True`.
  * In the staff moderation queue, their claims appear with a prominent **red warning badge**, alerting staff to scrutinize serial claimants.

#### 4. AI is Strictly Advisory
* An attacker might generate text with 99% semantic similarity to the found listing. **The system never auto-approves claims based on AI similarity**. Only human staff can approve a claim after reviewing non-public evidence (serial numbers, purchase receipts, lock-screen photos).

---

### Part 2: What Stops a Dishonest Moderator? (Rogue Staff)

A corrupt staff member wants to approve a friend's false claim, or take a valuable MacBook from the lost-and-found locker for themselves:

#### 1. Zero-Knowledge Handover Codes (The Physical Handover Barrier)
* Even if a corrupt moderator approves a false claim, **they cannot complete the handover by themselves**.
* The single-use 8-character code (`7K9M-2P4X`) is rendered **strictly to the claimant's phone screen**.
* The database stores only an **HMAC-SHA256 digest** under a server secret.
* The moderator’s desk screen shows **only an empty input box** with verification success/failure—**it never reveals the expected code or hash**. 
* **The Result**: A moderator cannot self-verify a handover in the office. They must have the physical presence of the claimant with the code.

#### 2. Conflict of Interest Enforcement ([`AC-80`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/test-plan.md#L118))
* A moderator **cannot review or decide a claim** on an item they reported finding (`403 conflict_of_interest`).
* A moderator **cannot approve a claim they filed themselves**.

#### 3. Mandatory Justification Notes
* A moderator cannot approve, reject, or verify handovers with a single click:
  * Claim decision: Requires a written decision note ($\ge 10$ characters, e.g. *"Verified student ID and matching serial number"*).
  * Desk handover: Requires an **identity verification note** ($\ge 10$ characters, e.g. *"Inspected physical student ID ending in 8421"*).

#### 4. Database-Level Immutable Audit Log ([`D-14`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/DECISIONS.md#L20))
* Every action—who locked a claim, who approved it, what notes were written, what IP address was used, and who typed the handover code—is written to `audit_log`.
* **PostgreSQL Trigger Protection**: The table is guarded by a PostgreSQL database trigger (`audit_log_immutable_trigger`):
  ```sql
  CREATE TRIGGER trg_audit_log_immutable
  BEFORE UPDATE OR DELETE ON audit_log
  FOR EACH ROW EXECUTE FUNCTION audit_log_immutable_trigger();
  ```
  Any raw SQL `UPDATE` or `DELETE` attempt fails with an exception. **A rogue moderator or DBA cannot edit or erase their footprints from the audit history.**

---

### Your 30-Second Viva Answer

> *"Against **false claimants**, we hide private item details through default-deny serializers, require answers to the finder's secret prompts, cap users to 3 active claims, and automatically flag repeat rejected claimants in the staff queue.*  
>  
> *Against **dishonest moderators**, we use **zero-knowledge handover codes** where staff never see the plaintext code or hash, enforce **strict conflict-of-interest checks** preventing staff from approving their own items, require **mandatory identity audit notes**, and protect the entire audit trail with a **PostgreSQL trigger that makes audit rows strictly immutable**."*


</details>

---

## Turn 13

**User Interaction:**
```
are personal ids get blurred automatically
```

*Metadata:* `Timestamp: 2026-10-27T17:52:59+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


The answer depends on whether you mean **Photos of ID Cards** or **Personal ID Numbers in Text**:

---

### 1. In Photos: Physical ID Cards are Completely Hidden from Public View

Photos of ID cards are not just blurred—**they are completely blocked from the public automatically**:

1. **Automatic Sensitive Category Classification**:
   In [`backend/app/domain/categories.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/categories.py), items categorized as **`id_card`** or **`wallet`** are defined as `SENSITIVE_CATEGORIES`.
2. **Forced Private Status**:
   In [`backend/app/api/reports.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/api/reports.py#L477), when a photo is uploaded to an `id_card` or `wallet` report, the system automatically sets:
   ```python
   is_public = False if is_sensitive_category(report.category) else True
   ```
3. **Hidden from Public Browse & Listings**:
   * The public search and browse endpoints ([`backend/app/api/found.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/api/found.py#L154)) automatically replace the thumbnail URL with `None`.
   * On the frontend card, the photo is replaced with a lock icon and the message: **`"Photo hidden for privacy"`**.
4. **Anti-Enumeration Image Route**:
   If an unauthorized student tries to directly download the photo URL (`GET /api/images/{key}`), the server returns **`404 Not Found`**. Only authorized campus staff and the original reporter can view the image.

---

### 2. Privacy Blurring in Photos: Faces, Plates & Badges

Under **Step 15** ([`backend/app/domain/privacy_blur.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/privacy_blur.py) and [`backend/app/services/photo.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/services/photo.py#L104)):
* If an uploaded photo contains bystander faces, vehicle license plates, or visible student badges, the photo pipeline applies **Gaussian smoothing (`radius=15`)** across those bounding boxes.
* **Why it blurs before saving**: The blur is applied **before the image is written to disk and before thumbnails are generated**. This ensures the unblurred raw biometric or identity data is never stored on the server.

---

### 3. In Text: Student ID Numbers, Cards & Phones (The PII Scanner)

If a user tries to type a student ID number, national ID, phone number, or credit card into a public field (`title` or `description`):

* The system does **not** silently blur it; **it completely rejects the submission** before saving to the database ([`backend/app/domain/pii.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/domain/pii.py)).
* **How it works**:
  * Scans for runs of 9 or more digits (`long_number`), credit card numbers passing the Luhn checksum (`card_number`), phone numbers (`phone`), and emails (`email`).
  * If detected, the API returns `HTTP 422 Unprocessable Content` with error `pii_detected`.
* **Security Rule ([P1](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/spec.md#L109))**: The error message tells the user the *kind* of PII detected (`"kind": "long_number"`), but **never echoes back the detected number**, preventing data exfiltration or reflection attacks.
* Personal identification numbers are **only allowed in the `private_details` field**, which is strictly visible to the reporter and staff.

---

### Quick Viva Summary

> *"For **photos**, any item categorized as an `id_card` or `wallet` has its photos automatically marked private and hidden from public browse views, while sensitive bounding boxes are redacted using Gaussian blur before disk persistence.*  
> *For **text**, the PII Scanner detects student IDs and long numbers, immediately rejecting public submissions with `422 pii_detected` without echoing back the sensitive numbers."*


</details>

---

## Turn 14

**User Interaction:**
```
wahat backend and frontend it is using
```

*Metadata:* `Timestamp: 2026-10-27T21:21:44+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


Here is the exact tech stack used for the **Backend** and **Frontend** in this project:

---

### 1. Backend Stack

| Component | Technology | Purpose in Project |
| :--- | :--- | :--- |
| **Language** | **Python 3.12+** | Core programming language for all business logic, data models, and ML. |
| **Web Framework** | **FastAPI** | High-performance asynchronous REST API framework running on the **Uvicorn** ASGI server. |
| **Database** | **PostgreSQL 16 + `pgvector`** | Stores relational data (users, claims, reports) and dense vector embeddings (`vector(384)` and `vector(512)`). |
| **ORM / DB Driver** | **SQLAlchemy 2.0 (async)** with **`asyncpg`** | Handles asynchronous database queries and connection pooling. |
| **Database Migrations** | **Alembic** | Version-controlled schema migrations (`alembic upgrade head`). |
| **Data Validation** | **Pydantic v2** (`extra="forbid"`) | Strictly validates request payloads and serializes response data to prevent injection attacks. |
| **AI / ML Models** | **Sentence-Transformers** & **OpenCLIP** | Powers semantic text search (`all-MiniLM-L6-v2`) and visual/cross-modal matching (`CLIP ViT-B/32`). |
| **Security & Cryptography** | **Argon2id** & **HMAC-SHA256** | Argon2id for password hashing; HMAC-SHA256 for 8-character Base32 handover codes. |
| **Image Processing** | **Pillow (PIL)** | EXIF metadata stripping, dimension guards, 64-bit perceptual dHash, and Gaussian privacy blurring. |

---

### 2. Frontend Stack

| Component | Technology | Purpose in Project |
| :--- | :--- | :--- |
| **Library / Framework** | **React 18** | Component-based Single-Page Application (SPA) UI. |
| **Language** | **TypeScript 5** | Strict type-safety across all components and state management. |
| **Build Tool / Bundler** | **Vite 5** | Ultra-fast development server with Hot Module Replacement (HMR) and optimized production asset bundling (`dist/`). |
| **Styling** | **Custom Vanilla CSS** ([`styles.css`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/frontend/src/app/styles.css)) | A custom design system built with CSS variables. Tailored specifically for **mobile accessibility down to 360px viewport**, high-contrast focus rings (`:focus-visible`), and zero bloat. |
| **API Client & Types** | **`openapi-typescript`** | Generates TypeScript interfaces directly from the backend's OpenAPI contract (`openapi.json`), ensuring the frontend and backend are 100% in sync. |
| **Routing** | **Hash Router** (`/#/found`, etc.) | Client-side SPA routing that works seamlessly behind reverse proxies without complex Nginx URL rewrite rules. |
| **Web Server (Production)** | **Nginx** (Docker) or **FastAPI Static Mount** (Cloud) | Serves the pre-compiled HTML, CSS, and JS bundle. |

---

### Quick 10-Second Viva Answer

> *"The **backend** is built with **Python 3.12, FastAPI, and PostgreSQL 16 with the `pgvector` extension**, using SQLAlchemy async, Pydantic v2, and Sentence-Transformers (`all-MiniLM-L6-v2`) + CLIP (`ViT-B/32`) for offline multimodal matching.*  
>  
> *The **frontend** is a single-page application built with **React 18, TypeScript, and Vite**, styled with a custom accessible vanilla CSS design system, and type-synchronized directly with the backend via OpenAPI."*


</details>

---

## Turn 15

**User Interaction:**
```
(The chat transcript of your discussion with Claude Code or Codex must be converted to an HTML page using the following steps:
At the end of the development session (reuse the same session for the multiple sittings that you do), perform \export transcript.md
Then ask Claude or Codex to convert the turn by turn conversation in the transcript.md to a clickable HTML standalone page that shows the user interactions as Turn 1, 2, 3 etc and below each turn, the response is a collapsed text block.)
extarct this conversation and push it to git and give me html link
```

*Metadata:* `Timestamp: 2026-10-27T21:24:07+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


The conversation transcript has been converted into a standalone interactive HTML page, committed, and pushed to your GitHub repository.

---

### Links to Access Your Transcript

* **Live Interactive HTML Page (View in Browser)**:  
  👉 **[HTML Preview Link (Rendered Standalone Page)](https://htmlpreview.github.io/?https://github.com/abhiramreddypasam18243-lab/campus-lost-and-found/blob/master/transcript.html)**

* **Local Offline File (Instant Browser View on your PC)**:  
  👉 **[transcript.html](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/transcript.html)**

* **GitHub Repository File**:  
  👉 **[transcript.html on GitHub](https://github.com/abhiramreddypasam18243-lab/campus-lost-and-found/blob/master/transcript.html)**

* **Raw HTML Source**:  
  👉 **[Raw GitHub Link](https://raw.githubusercontent.com/abhiramreddypasam18243-lab/campus-lost-and-found/master/transcript.html)**

* **Markdown Version (as required by assignment guidelines)**:  
  👉 **[transcript.md on GitHub](https://github.com/abhiramreddypasam18243-lab/campus-lost-and-found/blob/master/transcript.md)** or locally at [`transcript.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/transcript.md)

---

### Features Built into Your `transcript.html`:

1. **Turn-by-Turn Collapsible Structure**:
   * All **32 User Interaction Turns** are labeled clearly (**Turn 1**, **Turn 2**, **Turn 3**, ... **Turn 32**).
   * Below each turn, the complete assistant response, actions, tool calls, and code snippets are housed in a **clean collapsed text block** (`<details>` / `<summary>`).
2. **Global Controls Bar (Sticky Header)**:
   * **`[+] Expand All`**: Expands all 32 assistant response blocks at once.
   * **`[-] Collapse All`**: Collapses all responses for fast skimming.
   * **Live Search**: Filter turns in real-time by typing keywords, commands, or file names.
   * **Jump-to-Turn Dropdown**: Select any turn from the dropdown to instantly scroll to and highlight it.
3. **Turn Copy Action**:
   * Every turn includes a `📋 Copy Response` button to copy the response to the clipboard.
4. **100% Standalone**:
   * All CSS styling and JavaScript are embedded directly inside `transcript.html` with zero external CDN dependencies—it opens and functions offline in any browser.

---

### Git Commit Verification:
```bash
commit: f3e937e
Branch: master -> master
Remote: https://github.com/abhiramreddypasam18243-lab/campus-lost-and-found.git
Files pushed:
  - transcript.html (Standalone Interactive Turn-by-Turn Viewer)
  - transcript.md   (Markdown export)
  - build_transcript.py (Automated parser & generator script)
  - campuslostandfound1.txt (Source transcript archive)
```


</details>

---

## Turn 16

**User Interaction:**
```
I only want transcript of this particular chat
```

*Metadata:* `Timestamp: 2026-10-27T21:36:38+05:30.`


<details>
<summary><b>🤖 Click to view Assistant Response & Explanation</b></summary>


Generated standalone interactive HTML transcript of this current pair-programming session, committed to Git repository, and provided GitHub and local browser links.


</details>

---
