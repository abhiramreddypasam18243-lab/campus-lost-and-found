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




