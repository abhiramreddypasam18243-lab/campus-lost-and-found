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

---

## Step 4: Item Reports, Lifecycle Tables, PII Scanner, and Photo Pipeline
* **Acceptance Criteria:** AC-21 to AC-37
* **What was built:**
  * Core lost and found report models (`item_reports`) and photo metadata (`item_images`) with PostgreSQL ENUMs (`report_type`, `report_status`, `time_precision`, `image_role`).
  * Strict schema validation (`extra="forbid"`) enforcing required title, description, category, and date constraints.
  * Maximum 3 verification questions/prompts on found items to prevent student friction while verifying rightful owners.
  * Initial lifecycle state separation: lost reports start in `open`, found reports in `pending_review` until approved.
  * Pure domain Asia/Kolkata time window computation (`day`, `morning` 06:00-12:00, `afternoon` 12:00-17:00, `evening` 17:00-21:00, `night` 21:00-06:00 crossing midnight, and `exact` +/- 2 hours) returning UTC timestamp ranges.
  * Exhaustive finite state machine `validate_status_transition` enforcing legitimate state transitions: found (`pending_review` -> `open`/`removed`, `open` -> `in_claim`/`returned`/`archived`/`removed`, `in_claim` -> `open`/`returned`, `returned` = terminal irreversible), lost (`open` -> `matched`/`closed`, `matched` -> `open`/`closed`, `closed` -> `open`).
  * User closure endpoint allowing reporters to close their own reports; returns HTTP 404 anti-enumeration for non-owners.
  * Server-side PII Scanner (`backend/app/domain/pii.py`) detecting credit cards via Luhn checksum, 13-19 digit number runs, international & domestic phone numbers, and email addresses in public fields. On detection, rejects with HTTP 422 `pii_detected` without echoing back the sensitive input. Allows PII only in private details fields.
  * Photo processing pipeline (`backend/app/services/photo.py`): content-type magic bytes verification (ignoring spoofed extensions), 5MB file size limit, 6000x6000 px dimension guard against decompression/pixel bombs, EXIF metadata stripping (including GPS and camera identifiers) using Pillow, image downscaling to <= 1600 px long edge, 256 px thumbnail generation, random UUID storage keys, and 64-bit difference hashing (dHash) for duplicate detection.
  * Sensitive category protection (`id_card`, `wallet`): photos are automatically marked private and protected from unauthorized public viewing (HTTP 404).
* **Why it is designed that way:**
  * Decompression bombs (e.g., a heavily compressed 10000x10000 image taking only 100KB on disk but over 300MB uncompressed in RAM) can quickly exhaust worker memory; inspecting image dimensions before reading full pixel buffers prevents denial-of-service.
  * EXIF metadata frequently retains exact home/work GPS coordinates and phone camera identifiers; stripping EXIF server-side prevents accidental location disclosure.
  * When PII is detected in public fields, the API response must NEVER echo the offending number or value back in the error payload, preventing data exfiltration or reflection attacks.
  * Enforcing explicit `Asia/Kolkata` timezone calculations avoids UTC date truncation bugs where an item lost at 11:00 PM IST is categorized on the wrong UTC calendar day.
* **One thing that could go wrong:**
  * If photo files are saved using user-supplied filenames, path traversal attacks (`../../etc/passwd`) or file overwrite vulnerabilities can compromise the host; utilizing UUIDv4 keys and serving images strictly through authenticated streaming endpoints completely decouples user filenames from storage.
* **Quiz Questions (for viva preparation):**
  1. *What is a pixel/decompression bomb, and how does the image ingestion pipeline protect server memory before resizing images?*
  2. *How does the PII scanner detect credit card numbers accurately using the Luhn algorithm, and why must the error response NEVER echo back the detected value?*
  3. *Why is `returned` modeled as a strictly irreversible terminal state in the found-item lifecycle finite state machine?*

---

## Step 5: Browsing, Search, and Whitelisted Public Views
* **Acceptance Criteria:** AC-38 to AC-44
* **What was built:**
  * Whitelisted public found-item listing (`GET /api/found`) showing strictly `open` found items (excluding `pending_review`, `removed`, `returned`, `archived`, `closed`, and all lost reports) with building-level locations, public descriptions, category, dates, and public photo thumbnails.
  * Strict Default-Deny Serializers (`PublicFoundItemSummary` and `PublicReportDetailResponse`) with `extra="forbid"`, verified by automated canary contract testing ensuring zero leakage of private details, verification prompts, reporter identities (ID/email/name), finer-than-building locations (room/floor), or private images.
  * Role-based report detail routing (`GET /api/reports/{id}`): returns full staff report view (`FullStaffReportResponse`) to moderators, admins, and the report's owner; returns whitelisted public detail view to non-owner student users for open found reports; and returns HTTP 404 anti-enumeration on lost reports or non-open found reports accessed by other users.
  * PostgreSQL full-text search across `title` and `description` via `to_tsvector` and `plainto_tsquery`, backed by an indexed GIN expression (`0005_search_index.py`).
  * Hierarchical building filter resolving all descendant locations (floors, rooms, areas) via recursive Common Table Expression (CTE).
  * Multi-attribute filtering combining full-text search, category, building descendants, and date ranges with `AND`.
  * Stable cursor pagination encoding `(created_at, id)` as an opaque base64 string with configurable limit (default 20, max 100) guaranteeing no skipped or duplicated items across pages during real-time writes.
  * Per-user browse rate limiting via `BrowseRateLimiter` allowing 120 requests/minute and returning HTTP 429 with standard `Retry-After` header when exceeded.
  * Strict campus authentication (401 for anonymous) and UUIDv4 identifier enforcement across all browse endpoints.
* **Why it is designed that way:**
  * A default-deny serializer ensures that even if developers add new internal or sensitive columns to the database model in future steps, those columns will never accidentally leak to public API callers unless explicitly whitelisted in the response schema.
  * Resolving locations to building-level for public viewers protects student safety by preventing stalkers or opportunistic claimants from learning the exact room or floor where an item was lost or found.
  * Stable cursor pagination based on `(created_at, id)` avoids the offset pagination trap (e.g., `OFFSET 20`), where items inserted while a user is browsing cause page drift and duplicate or missing items.
  * Opaque cursor strings prevent clients from relying on internal database sorting implementations, allowing future backend optimizations without breaking client contracts.
* **One thing that could go wrong:**
  * If a user passes dates with ambiguous timezone offsets or plain calendar dates `YYYY-MM-DD`, naive parsing can truncate queries at midnight `00:00:00`, excluding all items found during the daytime on the end date; explicitly expanding `date_to` to `23:59:59.999999 UTC` guarantees inclusive date window filtering.
* **Quiz Questions (for viva preparation):**
  1. *What is a "default-deny serializer", and how does contract testing with canary strings guarantee that sensitive student data cannot leak into public API responses?*
  2. *Why is cursor-based pagination using a composite tuple `(created_at, id)` preferred over traditional `OFFSET`/`LIMIT` pagination in high-frequency lost-and-found databases?*
  3. *How does the building filter use a recursive Common Table Expression (CTE) to include items located on lower hierarchical levels (such as specific rooms or floors) without exposing those finer locations to the public?*

## Step 6: Background Jobs, Model Registry, and Notification Outbox
* **Acceptance Criteria:** AC-45 to AC-50, AC-68 to AC-74
* **What was built:**
  * **Database Infrastructure & Migration (`0006_jobs_embed_notifs.py`):**
    * Background job queue table (`jobs`) with composite index `(status, run_after)` supporting worker polling and exponential retry backoff.
    * Model registry (`model_registry`) and pgvector tables (`report_text_embeddings` with `vector(384)`, `report_image_embeddings` with `vector(512)`) enforcing unique version constraints `(entity_id, model_name, model_version)`.
    * Transactional notification outbox table (`notifications`) with unique constraint `uq_notifications_event_key` and per-user index.
  * **Transactional Background Job Enqueueing (AC-45):**
    * Saving a lost or found report transactional-enqueues `embed_report_text`, and uploading a photo transactional-enqueues `embed_report_image`.
    * Fast return latency (< 300 ms with models off or mock embeddings).
  * **Concurrent Lock-Free Queue Workers (AC-46):**
    * `claim_jobs()` worker engine using PostgreSQL `SELECT FOR UPDATE SKIP LOCKED` ensuring multiple concurrent workers never process or duplicate the same job (verified with 2 concurrent workers claiming 200 jobs with zero overlap).
  * **Retry Backoff & Admin Controls (AC-47):**
    * Structured exponential backoff retry policy (`[1, 2, 4, 8]` minutes, max 5 attempts); transitions to `failed` upon the 5th failure.
    * Admin job inspection (`GET /api/admin/jobs`) and manual retry (`POST /api/admin/jobs/{id}/retry`) resetting attempts and status for failed jobs.
  * **Embedding Model Registry & Backfill (AC-48, AC-49, AC-50):**
    * Idempotent vector insertion (`upsert_report_text_embedding` / `upsert_report_image_embedding`).
    * Model activation workflow (`activate_model_version` and `POST /api/admin/models/activate`) that sets the active version and enqueues backfill jobs across all open reports.
    * Database-level pgvector dimension validation (verifying PostgreSQL strictly rejects mismatched vector dimensions).
  * **Transactional Notification Outbox & Deduplication (AC-68, AC-69, AC-70):**
    * Transactional consistency: rolling back a business transaction automatically aborts notification creation, preventing ghost emails.
    * Idempotent deduplication on `event_key` guaranteeing duplicate events produce a single notification record.
    * Deterministic RFC 5322 `Message-ID` generation (`<event_key@campus.domain>`) enabling client-side email threading and duplicate suppression.
    * SMTP delivery error handling with retry backoff and failure state logging.
  * **Notification Privacy & User Preferences (AC-71, AC-72, AC-73):**
    * Whitelisted notification template rendering with automated canary verification: private details, verification prompts, and student PII are never leaked in email subjects or bodies.
    * Preference enforcement: user opt-out (`notify_matches: false`) skips match emails while preserving critical claim/handover communications.
    * Spam protection: hard cap of 5 match suggestion emails per user per 24-hour window.
  * **In-App Notification API (AC-74):**
    * Paginated, owner-only notification inbox (`GET /api/notifications`) with filters (`status=all|unread|read`) and stable cursor pagination.
    * Read receipt tracking (`POST /api/notifications/{id}/read`) with 404 anti-enumeration against other users' notifications.
* **Why it is designed that way:**
  * **Transactional Outbox Pattern:** By writing job records and notifications into PostgreSQL within the same database transaction as reports and claims, we solve the dual-write problem. If the transaction aborts, no orphaned jobs or emails are sent. If external systems (SMTP, embedding inference) are temporarily offline, the persistent queue ensures durable delivery without data loss.
  * **`SELECT FOR UPDATE SKIP LOCKED`:** PostgreSQL natively coordinates concurrent workers without distributed locking (Redis, ZooKeeper). Unclaimed jobs are locked and handed to the requesting worker, while other workers skip already locked rows without waiting, achieving maximum concurrency and zero duplicates.
  * **Model Registry Decoupling:** Storing model names, versions, and embedding dimensions in a model registry decouples ML model lifecycle from application code. Activating a newer embedding model automatically triggers background backfilling for historical records while preserving existing vectors.
  * **Canonical Event Keys:** Using deterministic event keys (e.g., `match_suggested:reportA:reportB`) prevents notification floods caused by worker restarts, duplicate webhooks, or retry loops.
* **One thing that could go wrong:**
  * **Alembic Revision ID Column Width:** PostgreSQL `alembic_version.version_num` is a `VARCHAR(32)` column. Migration revision IDs exceeding 32 characters (e.g. `0006_jobs_embeddings_notifications`) trigger database-level string truncation errors. Keeping revision identifiers concise (e.g., `0006_jobs_embed_notifs`) prevents deployment failures.
  * **ORM ID Population Timing:** In SQLAlchemy, auto-generated UUIDs on models are populated only upon database insert or flush. Accessing `model.id` before flush produces `None`. Explicitly passing `id=uuid.uuid4()` at instantiation ensures `entity_id` is never null when enqueuing background jobs.
* **Quiz Questions (for viva preparation):**
  1. *How does PostgreSQL's `SELECT ... FOR UPDATE SKIP LOCKED` provide a reliable, concurrent work queue without requiring an external message broker like Redis or RabbitMQ?*
  2. *What is the Transactional Outbox Pattern, and how does it prevent the "dual-write" consistency hazard between relational databases and external services like email or ML workers?*
  3. *Why should background job retry intervals use exponential backoff (e.g., 1, 2, 4, 8 minutes) instead of immediate or fixed-interval retries?*

## Step 7: The Matching Engine (Signals, Hybrid, Retrieval, and Explanations)
* **Acceptance Criteria:** AC-51 to AC-67
* **What was built:**
  * **Pure Domain Scoring & Candidate Logic (`app/domain/matching.py`):**
    * Text score (AC-51): $\max(0, \text{cosine})$ of normalized embeddings (tested on cosine 0.82 $\to$ 0.82, -0.10 $\to$ 0.0).
    * Time score (AC-52): Overlapping windows score 1.0; asymmetric exponential decay if found after lost ($\exp(-\text{gap}/48)$; 12h $\to$ 0.7788, 48h $\to$ 0.3679) and if found before lost ($\exp(-\text{gap}/6)$; 6h $\to$ 0.3679, 12h $\to$ 0.1353).
    * Hybrid score with dynamic weight renormalization (AC-53, AC-54): Sums $\frac{\sum w_i s_i}{\sum w_i}$ strictly over non-null signals, never treating missing signals as zero (signals 0.8, 0.6, 0.7, 0.5 score 0.685; with image missing, weights renormalize over 0.65 yielding 0.7308; a text-only pair scores exactly its text score).
    * Image signal determination (AC-55): Image-to-image similarity when both have photos, text-to-image cross-similarity when exactly one has photos, and null when neither does.
    * Candidate constraints validation (AC-56): Both reports `open`, reporters differ, pair not dismissed, found item not reserved or returned, found time between 6 hours before lost window starts and 30 days after it ends.
    * Deterministic tie-breaking (AC-57): Sorts by `score DESC`, then `found.created_at ASC` (older found item first), then `found.id ASC`.
    * Explainability & Exact Additivity (AC-59): Signal contributions $c_i = \frac{w_i s_i}{\sum w_j}$ sum to the combined score within $10^{-9}$; plain language explanations for signals contributing $\ge 10\%$ of score (or top 3).
  * **Database Infrastructure & Migrations (`0007_match_candidates.py`, `0008_hnsw_indexes.py`):**
    * Tables `match_candidates` and `match_feedback` with unique constraint `(lost_id, found_id, weights_version)` and status indexes.
    * pgvector HNSW vector cosine indexes (`vector_cosine_ops`) created on `text_embeddings` and `image_embeddings` for approximate nearest-neighbor search.
  * **Matching Services & API (`services/matching.py`, `api/matches.py`):**
    * `compute_matches_for_report`: Bidirectional candidate scoring (lost triggers found, found triggers lost), idempotent upsert, and transactional match suggestion notification creation for top 3 candidates scoring $\ge 0.65$ (AC-63, AC-65).
    * `GET /api/reports/{id}/matches` (AC-58): Owner-only matching endpoint (404 anti-enumeration for foreign users) returning score, bin, signals, explanations, and strictly whitelisted public found item summaries (`PublicFoundItemSummary`).
    * Privacy Canary Contract (AC-60): Canary string in private details never appears in explanations, responses, notifications, or logs.
    * Permanent Dismissal (AC-61): `POST /api/matches/{id}/dismiss` marks candidate as dismissed, records feedback, and prevents dismissed pairs from reappearing.
    * AI Advisory Enforcement (AC-62): Verified that artificial score updates (e.g. 0.99) never alter report or claim status.
    * Model & Weights Versioning (AC-64): Stores `weights_version` and `model_versions`; changing weights preserves historical runs.
    * HNSW Recall & Latency Verification (AC-66, AC-67): Verified HNSW recall@10 $\ge 90\%$ against exact flat search and retrieval/scoring latency $< 200$ ms at p50 and $< 800$ ms at p95.
* **Why it is designed that way:**
  * **Dynamic Weight Renormalization:** Treating missing signals (such as an absent photo) as zero would severely penalize honest reporters who lost an item for which they had no picture. Renormalizing remaining weights preserves fairness across varying signal availability.
  * **Asymmetric Time Decay:** While an item cannot physically be found before it was lost (except for slight human reporting errors in timestamps, allowing a steep 6-hour half-decay), lost items commonly sit undetected in campus hallways or lost-and-found bins for days or weeks (represented by a gradual 48-hour decay).
  * **Layering & Separation of Concerns:** Domain matching calculations contain zero database or framework imports, allowing the exact formulas and worked numbers from the specification to be tested with high-speed, deterministic unit tests.
  * **AI as Advisory Only:** Under campus policy and ethical guidelines, automated similarity scores serve exclusively to surface candidate suggestions to human owners and staff, never triggering automated lifecycle or claim decisions.
* **One thing that could go wrong:**
  * **HNSW Index Autogenerate Drift:** Creating pgvector HNSW indexes in raw SQL without declaring them in SQLAlchemy model `__table_args__` causes `alembic check` to flag unmanaged indexes as dropped. Explicitly declaring `Index("ix_text_embeddings_hnsw", "vector", postgresql_using="hnsw", postgresql_ops={"vector": "vector_cosine_ops"})` in the model metadata keeps database state and Python schema in lockstep.
* **Quiz Questions (for viva preparation):**
  1. *Why must missing multimodal signals be dynamically excluded and weights renormalized rather than imputed as 0.0 in lost-and-found matching?*
  2. *What is the mathematical justification for an asymmetric exponential decay function in the time similarity score?*
  3. *How does the explanation generator guarantee that the sum of individual signal contributions strictly equals the combined hybrid score?*

### Step 8: Claims and Moderation (AC-75 to AC-85)
* **What was built:**
  * **Pure Domain Logic (`app/domain/claims.py`):**
    * Exhaustive lifecycle transitions (AC-76): `submitted` $\to$ `under_review`, `withdrawn`; `under_review` $\to$ `approved`, `rejected`, `needs_more_info`, `withdrawn`; `needs_more_info` $\to$ `submitted`, `withdrawn`; `approved` $\to$ `completed`, `expired`, `withdrawn`; terminal states `rejected`, `completed`, `expired`, `withdrawn`.
    * Validation & Prompt Answers (AC-75): Evidence text strictly 20 to 2000 characters; answers to every verification prompt; anti-self-claim; prevention of duplicate claims on the same found item.
    * Abuse Prevention & Active Claim Limits (AC-84): Normal limit of 3 active claims; users with 3 rejected claims within 30 days are automatically limited to 1 active claim and flagged as `claimant_flagged=True` for staff.
    * Concurrency & Review Locks (AC-78): Opening a claim assigns an exclusive 30-minute lock (`lock_expires_at = now + 30m`, `locked_by_id = mod.id`); prevents concurrent moderator decisions with HTTP 409 `claim_locked`; expired locks automatically become available to other staff.
    * Conflict of Interest (AC-80): A moderator cannot decide a claim on an item they reported, or a claim they filed themselves (HTTP 403 `conflict_of_interest`).
    * Escalation (AC-85): Unreviewed claims older than 14 days are marked `escalated=True` and prioritized first in the queue.
  * **Database Infrastructure & Migrations (`0009_claims_table.py`):**
    * Table `claims` with foreign keys to `item_reports` (found and optional lost) and `users` (claimant, reviewer, locked_by), JSONB answers and image_ids, timestamps, and composite performance indexes (`(claimant_id, status)`, `(found_id, status)`, `(status, submitted_at)`).
  * **Services & API Endpoints (`services/claims.py`, `api/claims.py`, `api/moderation.py`):**
    * `POST /api/claims`: Secure claim creation with CSRF, prompt validation, and active-claim limits.
    * `GET /api/claims/{id}`: Privacy-enforced claim detail (AC-77); visible strictly to claimant and moderators (404 anti-enumeration for finder and other users).
    * `POST /api/claims/{id}/withdraw` (AC-83): Claimant withdrawal; withdrawing an approved claim cancels the handover and reverts the found item back to `open`.
    * `PATCH /api/claims/{id}/evidence` (AC-82): Allows claimants to amend evidence when in `needs_more_info`, transitioning back to `submitted` and re-entering the queue.
    * `GET /api/mod/queue` (AC-78, AC-85): Unified moderator queue displaying pending reports, duplicate images, and active claims, ordered with escalated claims first, then submission time ascending.
    * `POST /api/mod/claims/{id}/open`: Moderator lock acquisition for 30 minutes.
    * `POST /api/mod/claims/{id}/approve` (AC-79, AC-81): Decision note $\ge 10$ characters, reserves found item (`item_reports.status = "reserved"`), blocks conflicting approvals (HTTP 409 `item_already_reserved`), creates transactional notification, and logs `claim.approved`.
    * `POST /api/mod/claims/{id}/reject` (AC-79): Decision note $\ge 10$ characters, marks claim `rejected`, logs `claim.rejected`, and notifies claimant.
    * `POST /api/mod/claims/{id}/request-info`: Decision note $\ge 10$ characters, transitions claim to `needs_more_info`, releases review lock, and notifies claimant.
* **Why it is designed that way:**
  * **Default-Deny Claim Privacy:** Claimants submit sensitive evidence (e.g., distinguishing engravings, unique scratches, purchase receipts, answers to private verification prompts). If this evidence were visible to the item finder or other campus users, malicious actors could copy those details and file fraudulent counter-claims.
  * **Time-Bound Exclusive Review Locks:** In campus facilities with multiple staff members on duty, concurrent reviews without locking cause race conditions where two moderators approve competing claims simultaneously or issue duplicate handover instructions. The 30-minute lock prevents collision while an automatic expiration ensures that an abandoned review session does not lock a student's claim indefinitely.
  * **Strict Conflict-of-Interest Controls:** Academic integrity and asset security require that staff members cannot self-certify ownership of items they reported finding or approve items they claim to have lost.
  * **Reversible Reservation on Withdrawal:** When a claimant withdraws after approval (for example, if they locate their misplaced item at home), the found report is automatically returned to `open` so other students or queued claims can be evaluated without manual administrator intervention.
* **One thing that could go wrong:**
  * **Orphaned Locks on Abandoned Sessions:** If a moderator opens a claim and closes their tab or browser without making a decision, the claim remains locked until the 30-minute window expires. Handled by checking `lock_expires_at > now` in real time: once expired, any authorized moderator can re-open and acquire the review lock without manual unlock actions.
* **Quiz Questions (for viva preparation):**
  1. *Why must the finder of a found item be prevented from seeing claim evidence and prompt answers submitted by claimants?*
  2. *How does the system enforce concurrency control and prevent duplicate decisions when multiple moderators review claims simultaneously?*
  3. *What happens to a found report's status and subsequent claims if an approved claimant withdraws their claim prior to handover?*
