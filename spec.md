# SPEC.md: Smart Campus Lost-and-Found Network

**Version:** 1.0 (draft, based on *Smart Campus Lost-and-Found Network: Project Blueprint*)
**Last updated:** 2026-10-18
**Methodology:** Spec-Driven Development. Every requirement has an ID, and every acceptance criterion (AC) becomes at least one automated test or one recorded measurement.

> Numbers marked *initial* (thresholds, weights, targets) are starting values. If you change one after measuring, record the change in the Decisions Log (section 20). The results of the evaluation are **findings**, not targets: report whichever way they fall.

---

## 1. Overview

A full-stack web application where campus users report lost and found belongings, the system suggests likely matches using text, photos, campus location and time, and campus staff verify claims and complete handovers with a one-time code. AI suggestions are **advice for humans**: no score ever approves a claim or changes a status.

The project has two halves of equal weight. The **product** half is a trustworthy workflow: privacy-aware public listings, evidence-based claims, moderator review, expiring single-use handover codes, an audit trail, and retention rules. The **research** half asks a measurable question: *does combining text, image, location and time signals retrieve lost items better than keyword search?* It is answered on a controlled benchmark with proper splits, confidence intervals and ablations.

The blueprint itself notes that AI-assisted lost-and-found systems already exist. This project does not claim a novel idea. Its contribution is a careful, secure, explainable campus workflow and an honestly measured comparison.

### Aim

Build a secure, campus-aware lost-and-found platform with explainable multimodal matching, a verified claim and handover process, and a reproducible evaluation of hybrid retrieval against keyword and single-signal baselines, deployed as a service you can open in a browser on your computer or local network.

### Inputs

| Input | Details |
| --- | --- |
| Accounts | Campus email, password, display name (optional) |
| Reports | Lost or found: title, description, category, time (with precision), campus location (any level) and/or a typed place (D-22), up to 3 photos, optional private details and verification prompts (found reports) |
| Claims | Evidence text, answers to verification prompts, up to 3 private evidence photos |
| Moderator actions | Approve or remove reports, decide claims, issue and verify handover codes |
| Campus data | A location tree and building adjacency, maintained by admins |
| Models | A pinned text-embedding model and a pinned image-text model (section 6.1) |
| Benchmark data | A synthetic generator plus a small real-photo subset, with a data card (section 7) |
| Configuration | Environment variables: database URL, secrets, allowed email domains, SMTP, retention periods, model versions |

### Outputs

| Output | Details |
| --- | --- |
| Searchable listings | Found items visible to authenticated campus users, without private details |
| Ranked match suggestions | Top candidates for each report, with a score, a bin and a plain-language explanation |
| Claims and handovers | Reviewed claims, expiring handover codes, completed returns with an audit trail |
| Notifications | In-app and email, with no private details |
| Analytics | Recovery rate, time to recovery, unclaimed rate, volume and queue age |
| Evaluation results | Tables and plots of retrieval quality, ablations and latency, with confidence intervals and recorded model versions |
| Deployed service | The web application, running in containers at `http://localhost:8080` (and over HTTPS on the local network) |

### Requirements at a glance

- **Functional:** FR-01 to FR-20 (section 14).
- **Privacy, safety and trust:** P1 to P7 and S1 to S4 (section 4).
- **Security:** SEC1 to SEC12 (section 12). **Deployment:** D1 to D10 (section 13).
- **Non-functional:** section 17.
- **Acceptance criteria:** AC-01 to AC-149 (section 15), mapped to the blueprint in section 16.

## 2. Goals, Scope and Non-Goals

**Goals**
1. Accounts with roles (user, moderator, admin) and campus-email verification.
2. A hierarchical campus location model that tolerates approximate locations.
3. Lost and found reports with a safe photo pipeline and a defined lifecycle.
4. Searchable listings that never expose private details.
5. Background embedding jobs and a hybrid matching engine with explanations.
6. Notifications (in-app and email) through a reliable outbox.
7. Claims, moderator review, and one-time handover codes.
8. An append-only audit log, retention rules, and data export and deletion.
9. An analytics dashboard.
10. A reproducible evaluation of keyword, text, image and hybrid retrieval.
11. A tested, documented, deployed system.

**Non-goals (v1)**
- Campus single sign-on, mobile apps, push notifications, or SMS.
- Automatic ownership decisions, or any AI action without human review.
- GPS tracking or precise indoor positioning.
- Facial recognition. Photos are never used to identify people.
- Evidence that the system improves real-world recovery rates (only a pilot could show that; the benchmark does not).

**Stretch** (only after every required criterion passes): a SigLIP-family model comparison, multilingual text, face and number-plate blurring in photos, learning from dismissals, campus SSO, and a digest email.

## 3. Roles and Access Control

| Role | Who | Can |
| --- | --- | --- |
| `user` | A verified campus account | Report items, browse found items, see matches for their own lost reports, claim found items, manage their own data |
| `moderator` | Authorised campus staff | Everything a user can, plus review reports and images, decide claims, issue and verify handover codes, see private details and the dashboard |
| `admin` | A small number of administrators | Everything a moderator can, plus manage locations, roles, jobs and the audit log (evaluation results are read from `eval/results`, not an admin page; D-23) |

| Capability | Anonymous | User | Moderator | Admin |
| --- | --- | --- | --- | --- |
| Register, verify email, log in | Yes | Yes | Yes | Yes |
| Browse found items (public view) | No | Yes | Yes | Yes |
| Create lost or found reports | No | Yes | Yes | Yes |
| See own reports and matches | No | Yes | Yes | Yes |
| See other users' lost reports | No | No | Yes | Yes |
| See private details and exact location of a found report | No | Reporter only | Yes | Yes |
| Approve or remove reports and images | No | No | Yes | Yes |
| Submit a claim (not on their own found item) | No | Yes | Yes | Yes |
| See claim evidence | No | Claimant only | Yes | Yes |
| Decide claims (subject to the conflict rule) | No | No | Yes | Yes |
| Issue, reissue and verify handover codes | No | No | Yes | Yes |
| See the dashboard | No | No | Yes | Yes |
| Manage locations, roles and jobs; read the audit log | No | No | No | Yes |
| View evaluation results | No | No | No | Yes |

## 4. Privacy, Safety and Trust Rules

| ID | Rule |
| --- | --- |
| **P1 Default-deny public views** | Every response a normal user receives is built from an explicit whitelist of fields. Private details, verification prompts, reporter identity, exact locations, private images, claim evidence, handover codes and hashes never appear in a public view, an explanation, a notification or a log. |
| **P2 Private claim evidence** | Evidence and answers are visible only to the claimant and moderators, never to the finder. |
| **P3 Data minimisation** | Collect only an email address and an optional display name. No phone number, no student ID, no precise location. |
| **P4 Retention** | Found items expire after 90 days unclaimed; photos are deleted 30 days after closure; claim evidence 30 days after the claim closes; audit rows after 365 days (all *initial* and configurable). |
| **P5 Anti-scraping** | A login is required to browse, IDs are unguessable, browsing is rate-limited, and new accounts need a verified campus email. |
| **P6 Abuse controls** | Per-user claim limits, a flag for repeated rejected claims, and a conflict-of-interest rule for moderators. |
| **P7 Evaluation data** | Benchmark data contains no faces or personal data, with consent and licences recorded and a data card. Real users' reports are never used for evaluation. |
| **S1 AI is advisory** | Scores and explanations are suggestions. No code path changes a report, claim or handover state because of a score. |
| **S2 Human gates** | Found items are published after moderator review (default), claims are decided by a moderator, and handovers are completed by a moderator. |
| **S3 Transparent explanations** | Each suggestion shows which signals contributed and how much, in plain language. |
| **S4 Sensitive categories** | Items in the categories `id_card` and `wallet` never show photos publicly, and staff handle their details as private. |

## 5. Domain Rules

### 5.1 Report lifecycle

**Found report**

| State | Meaning | Legal next states (by whom) |
| --- | --- | --- |
| `pending_review` | Awaiting moderator approval | `open` (moderator approves), `removed` (moderator) |
| `open` | Listed and matchable | `reserved` (system, when a claim is approved), `closed` (reporter or moderator), `removed` (moderator), `unclaimed_expired` (system after the retention period) |
| `reserved` | A claim is approved and a handover is pending | `returned` (system, on handover completion), `open` (system, if the handover is cancelled or expires) |
| `returned` | Handed over | none |
| `unclaimed_expired` | Not claimed in time; a disposition is recorded | none |
| `closed`, `removed` | Ended by the reporter or a moderator | none |

**Lost report**

| State | Legal next states (by whom) |
| --- | --- |
| `open` | `resolved` (system on a completed handover, or the reporter), `closed` (reporter), `removed` (moderator), `expired` (system) |
| `resolved`, `closed`, `removed`, `expired` | none |

Every other transition returns 409 `invalid_transition`. A `reserved` item is excluded from matching and from new claims (409 `item_reserved`).

### 5.2 Time windows

A report gives a time and a precision. It becomes a **window** `[start, end]` in UTC: `exact` is a zero-length window, `day` is the local calendar day, and `morning`, `afternoon`, `evening` and `night` are the local periods 06:00 to 12:00, 12:00 to 17:00, 17:00 to 22:00 and 22:00 to 06:00 (initial, configurable). Local time uses the reporter's IANA timezone.

### 5.3 Claim lifecycle

| State | Legal next states (by whom) |
| --- | --- |
| `submitted` | `under_review` (moderator opens it and takes the lock), `withdrawn` (claimant) |
| `under_review` | `approved`, `rejected`, `needs_more_info` (moderator), `withdrawn` (claimant) |
| `needs_more_info` | `submitted` (claimant adds evidence), `withdrawn` (claimant) |
| `approved` | `completed` (system, on handover completion), `expired` (system, code expired), `withdrawn` (claimant; cancels the handover) |
| `rejected`, `completed`, `expired`, `withdrawn` | none |

A claim also has a flag `escalated` when it waits more than 14 days. A user has at most 3 active claims (those not in a final state) and at most one claim per found item. A moderator cannot decide a claim on an item they reported or a claim they made.

### 5.4 Handover codes

- When a claim is approved, the system issues a code of **8 characters** from the alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (40 bits), drawn from a cryptographically secure random source, and shows it **only to the claimant** (in-app and by email).
- Only an HMAC-SHA-256 of the code under a server secret is stored. Comparison is constant-time.
- Input is normalised by uppercasing, dropping spaces and hyphens, and mapping `O` to `0` and `I` or `L` to `1`.
- The code expires **48 hours** after issue (*initial*), works **once**, and locks the handover after **5 wrong attempts** (HTTP 423 until a moderator reissues it; at most 3 reissues). With 5 attempts against 2⁴⁰ possible codes, a random guess succeeds with probability about 4.5 × 10⁻¹².
- At the desk, the claimant shows the code and the moderator types it in. The moderator sees only success or failure, and must record an identity-check note to complete the handover.
- If the code expires, the claim becomes `expired` and the item returns to `open`.

### 5.5 Retention and deletion

A daily job, driven by an injected clock in tests, expires found reports after 90 days, deletes closed reports' photos after 30 days and claim evidence after 30 days, and purges old audit rows through a separate privileged role. Account deletion removes personal data, anonymises reports and keeps audit rows under a pseudonymous ID.

### 5.6 PII scanning of public text

Title and description are scanned before saving. Flagged kinds are: `card_number` (13 to 19 digits that pass the Luhn check), `long_number` (any run of 9 or more digits, ignoring spaces and hyphens), `phone` (a phone-number pattern) and `email`. A flagged public field is rejected with `pii_detected` (the kind, never the value). Private details may contain such text and show a warning only.

### 5.7 Photo pipeline

Allowed types are JPEG, PNG and WebP, decided by file content (magic bytes), up to 5 MB and 6,000 × 6,000 pixels, with at most 3 photos per report. Each upload is decoded with a pixel-limit guard, stripped of all metadata (including GPS), re-encoded, resized to at most 1,600 pixels on the long side, thumbnailed, and stored under a random UUID key with a 64-bit difference hash. Images are served only through an authorised route. Found photos wait for moderator approval and are non-public in sensitive categories.

**Categories (fixed list, initial):** `bottle`, `bag`, `wallet`, `phone`, `laptop_tablet`, `earphones`, `keys`, `id_card`, `clothing`, `book`, `accessory`, `other`.

## 6. Matching

### 6.1 Models and embeddings

| Purpose | Starting choice (verify each licence before use) |
| --- | --- |
| Text embeddings | A small sentence-embedding model such as `all-MiniLM-L6-v2` (384 dimensions) |
| Image and cross-modal embeddings | A CLIP-family model such as ViT-B/32 (512 dimensions), giving image vectors and text vectors in one space |
| Stretch comparison | A SigLIP-family model, as the blueprint suggests |

- Weights are downloaded **at image build time** with pinned revisions and checksums and baked into the image, so the running system makes no outbound model calls (D4).
- Every embedding row stores `model_name`, `model_version` and `dimension`, and vectors are L2-normalised. Matching compares only vectors of the same version. Vectors live in PostgreSQL with the **pgvector** extension and an HNSW index using cosine distance.
- Embeddings are computed by background workers, never during a web request.

### 6.2 Signals

Each signal is a number in [0, 1] or `null` when it cannot be computed.

| Signal | Definition |
| --- | --- |
| Text | `max(0, cosine)` between the text embeddings of `category + title + description` |
| Image | Image-to-image `max(0, cosine)` when both reports have photos (the best pair of photos); otherwise text-to-image `max(0, cosine)` (a report's text against the other report's photo) when exactly one has photos; otherwise `null` |
| Location | The table in 6.3 |
| Time | The decay function in 6.3 |

### 6.3 Location and time scores

**Location score** by the relationship between the two locations in the tree:

| Relationship | Score |
| --- | --- |
| Identical | 1.0 |
| One is an ancestor of the other | 0.8 |
| Share a floor or an area (lowest common ancestor is a floor or an area) | 0.7 |
| Share a building only | 0.6 |
| Different buildings that are adjacent | 0.5 |
| Same campus, not adjacent | 0.2 |
| Different campuses | 0.0 |
| A location is missing | `null` |

**Time score** compares the two windows. If they overlap, the score is 1. Otherwise let `gap` be the hours between them: if the found window is after the lost window, `score = exp(−gap / 48)`; if it is before, `score = exp(−gap / 6)`. The asymmetry reflects that a finder cannot find something before it was lost, apart from imprecise reporting.

### 6.4 Hybrid score

`score = Σ wᵢ sᵢ / Σ wᵢ`, summed **only over signals that are not `null`**. Initial weights: text 0.40, image 0.35, location 0.15, time 0.10. Missing signals are excluded, never treated as zero. Each stored candidate records its weights version. Bins: at least 0.75 `high`, at least 0.55 `medium`, otherwise `low`. A match notification is sent only for a score of at least 0.65 ranked in the top 3. Weights and thresholds are tuned on the development set only (section 7).

### 6.5 Candidates and retrieval

A candidate pair is a lost report and a found report where both are `open`, the reporters differ, the pair has not been dismissed, and the found time lies between 6 hours before the lost window starts and 30 days after it ends. Retrieval uses the HNSW index to fetch the nearest neighbours by text and by image, merges them with the location and time candidates, scores them all, and returns the top K (default 10). New reports trigger scoring in both directions, and each (lost, found, model version, weights version) is scored once. Ties break by the older found report, then by ID.

### 6.6 Explanations

The contribution of a signal is `wᵢ sᵢ / Σ wⱼ` over the available signals, so contributions sum to the score. The explanation lists the signals contributing at least 10% of the score (or the top 3) in plain sentences, for example "Similar description", "Visually similar photo", "Reported in a nearby building", and "Found 3 hours after you reported it lost". It never includes private details.

## 7. Evaluation Design

**Research question:** does combining image similarity, semantic text similarity, and campus location and time signals improve lost-item retrieval compared with keyword-based search?

### 7.1 Benchmark

- **Items:** 300 true items across the 12 categories, each with a lost report and a found report, plus 100 **background** found reports with no lost report (unclaimed items). A fixed campus tree of about 40 leaf locations is used.
- **Synthetic text:** each side is generated by a seeded grammar from the item's attributes (category, colour, material or brand-like descriptor, distinguishing feature). The lost and found sides use **different** lexicons and phrasing (for example "flask" and "bottle", "navy" and "dark blue"), each side drops at least one attribute, and a character-level typo rate of 2% is applied. Because both sides come from templates, a separate **human-written subset** of at least 60 items (two people writing blind to each other's text) is built and reported separately.
- **Photos:** a **real-photo subset** of at least 60 items, each photographed twice by different people with different angles and backgrounds; the other items have no photo. Image-based systems are evaluated on this subset.
- **Time and location:** the found time follows the lost time by a log-normal delay (median about 6 hours); the found location equals the true location with probability 0.6, is one level off with 0.3, and is random with 0.1. These are assumptions, and the noise ablations of 7.6 test how much the conclusions depend on them.
- **Ground truth:** exactly one true found report per lost report.
- **Query and pool:** each lost report is a query, and the candidate pool is all found reports in its split (true items plus the background reports).
- **Split:** 30% development (90 items) and 70% test (210 items), stratified by category, by item.

### 7.2 Systems compared

| System | Description |
| --- | --- |
| A: keyword | BM25 over title and description |
| B: text embedding | Text signal only |
| C: image | Image signal only, on reports with photos |
| D: hybrid | Hand-weighted hybrid of 6.4 |
| E: learned fusion | Logistic regression over the signals and their missing-value indicators, trained on the development set |
| Ablations | Hybrid with one signal removed in turn (7.6) |

### 7.3 Metrics

With one correct answer per query: **Recall@K** (equal to hit rate), **MRR**, **nDCG@K**, and **Precision@K** (capped at 1/K, so reported with that caveat), at K = 1, 3, 5 and 10. **Latency** at the 50th and 95th percentile, at 1,000, 10,000 and 100,000 candidates (synthetic vectors for scale), for approximate and exact search. End-to-end outcomes (verified returns, time to recovery, false claims, unclaimed rate) are operational metrics shown by the dashboard; the benchmark cannot measure them.

### 7.4 Statistics

Confidence intervals come from a **bootstrap over queries** (1,000 resamples, fixed seed). Differences between systems use a **paired bootstrap** on the same queries. A system is called better only if the 95% interval of the difference excludes 0.

### 7.5 Protocol and leakage control

Weights and the learned model are chosen on the **development set only**. The chosen configuration is written to a file, hashed, and **frozen**; the test set is evaluated once from that file. The tuning code has no access path to test labels, and a test enforces this. Every run records model names and versions, weights, random seed, dataset hash, git commit and hardware.

### 7.6 Ablations and robustness

Remove each signal in turn; set 0, 25, 50, 75 and 100% of photos to missing; apply location noise (one level off) and time noise (24 hours off) to 0, 25 and 50% of the found reports. Report each with confidence intervals.

### 7.7 Honest reporting

Write the hypotheses before the test run (**H1:** the hybrid has a higher MRR than the best single-signal baseline). Report the result whether or not it supports H1. State the limits: synthetic text and location and time rules share assumptions with the scoring function, so any advantage from location and time is partly by construction; the real-photo and human-written subsets are small; and nothing here shows real-world recovery gains.

## 8. Data Model

All primary keys are UUIDs, with `created_at` and `updated_at`, foreign keys and `CHECK` constraints.

| Table | Key fields |
| --- | --- |
| `users` | `email` (unique, lower-cased), `password_hash`, `display_name`, `role`, `email_verified_at`, `status`, `timezone`, `notify_match_email` |
| `email_tokens` | `user_id`, `token_hash`, `purpose`, `expires_at`, `used_at` |
| `sessions` | `user_id`, `token_hash`, `csrf_token_hash`, `expires_at`, `revoked_at` |
| `campus_locations` | `parent_id`, `kind` (`campus`, `building`, `floor`, `room`, `area`), `name`, optional rounded `lat` and `lng` |
| `location_adjacency` | `building_a`, `building_b` (stored in both directions or normalised) |
| `item_reports` | `type` (`lost`, `found`), `status`, `title`, `description`, `category`, `private_details`, `verification_prompts` (JSONB), `window_start`, `window_end`, `time_precision`, `location_id` (nullable), `location_text` (nullable, at most 200 characters, private; at least one of the two is set, D-22), `reporter_id`, `disposition`, `closed_at`, `reviewed_by` |
| `item_images` | `owner_type` (`report`, `claim`), `owner_id`, `storage_key`, `sha256`, `dhash`, `width`, `height`, `is_public`, `moderation_status`, `deleted_at` |
| `text_embeddings`, `image_embeddings` | `entity_id`, `model_name`, `model_version`, `dimension`, `vector` (pgvector) |
| `match_candidates` | `lost_id`, `found_id`, per-signal scores, `combined`, `bin`, `weights_version`, `model_versions`, `explanation` (JSONB), `status` (`suggested`, `dismissed`, `stale`) |
| `match_feedback` | `candidate_id`, `user_id`, `action`, `created_at` |
| `claims` | `found_id`, `lost_id` (optional), `claimant_id`, `evidence`, `answers` (JSONB), `status`, `escalated`, `reviewer_id`, `lock_expires_at`, `decision_note` |
| `handovers` | `claim_id`, `code_hmac`, `expires_at`, `attempts`, `reissues`, `status` (`issued`, `locked`, `used`, `expired`, `cancelled`), `completed_by`, `identity_note`, `completed_at` |
| `notifications` | `user_id`, `event_type`, `event_key` (unique), `payload` (JSONB, no private data), `status`, `attempts`, `read_at`, `message_id` |
| `jobs` | `kind`, `entity_id`, `status`, `attempts`, `run_after`, `last_error` |
| `audit_log` | `actor_id`, `role`, `action`, `entity_type`, `entity_id`, `summary` (JSONB), `created_at`; append-only |
| `model_registry`, `weights_versions` | The active model versions and the weights, thresholds and their version labels |

## 9. API Contract

**Conventions:** JSON over HTTPS; decimals as strings; timestamps in UTC; `limit` (default 20, maximum 100) and an opaque `cursor`; strict request schemas that forbid unknown fields; a resource that is not yours returns **404**, identical to a missing one. Errors are `{"error": {"code", "message", "details"}}` with 400, 401, 403, 404, 409, 410, 413, 415, 422, 423, 429 and 500 used as described in the acceptance criteria.

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/verify-email` | Accounts and sessions |
| GET, PATCH, DELETE | `/api/me`; GET `/api/me/export` | Profile, notification preferences, export, deletion |
| GET, POST | `/api/locations`; PATCH, DELETE `/api/locations/{id}`; POST, DELETE `/api/locations/adjacency` | Location tree (admin writes) |
| POST | `/api/reports` | Create a lost or found report |
| GET | `/api/reports/mine`, `/api/reports/{id}` | Own reports; a report in the view the caller may see |
| PATCH, POST | `/api/reports/{id}`, `/api/reports/{id}/close` | Edit and close |
| POST | `/api/reports/{id}/images` | Upload a photo |
| GET | `/api/images/{id}` | Authorised image download |
| GET | `/api/found` | Public found-item listing, search and filters |
| GET | `/api/reports/{id}/matches` | Match suggestions with explanations |
| POST | `/api/matches/{id}/dismiss` | "Not mine" |
| POST | `/api/found/{id}/claims`; GET `/api/claims/mine`, `/api/claims/{id}`; POST `/api/claims/{id}/withdraw`, `/api/claims/{id}/evidence` | Claims |
| GET | `/api/mod/queue` | Pending reports, duplicate flags and claims |
| POST | `/api/mod/reports/{id}/approve`, `/api/mod/reports/{id}/remove` | Report moderation |
| POST | `/api/mod/claims/{id}/open`, `/approve`, `/reject`, `/request-info` | Claim review |
| POST | `/api/mod/handovers/{id}/verify`, `/reissue`, `/complete` | Handover desk |
| GET | `/api/notifications`; POST `/api/notifications/{id}/read` | In-app notifications |
| GET | `/api/dashboard` | Analytics (moderator and admin) |
| GET, PATCH | `/api/admin/users`, `/api/admin/jobs`, `/api/admin/audit`, `/api/admin/evaluation` | Admin |
| GET | `/api/health` | Liveness, database and worker status |

**`POST /api/reports` (found)**

```json
{
  "type": "found",
  "title": "Blue steel water bottle",
  "description": "Dark blue insulated bottle with a dented base, left on a table.",
  "category": "bottle",
  "time": {"at": "2026-10-15T09:30:00+05:30", "precision": "exact"},
  "location_id": "<uuid of Library > Floor 2 > Reading Room>",
  "private_details": "Sticker with the letters RIA inside the lid.",
  "verification_prompts": ["What sticker is inside the lid?"]
}
```

**`GET /api/reports/{id}/matches` response**

```json
{
  "items": [{
    "match_id": "<uuid>",
    "found": {"id": "<uuid>", "title": "Blue steel water bottle", "category": "bottle", "building": "Library", "thumbnail": "/api/images/<id>"},
    "score": "0.7308", "bin": "high",
    "signals": {"text": "0.80", "image": null, "location": "0.70", "time": "0.50"},
    "explanation": [
      {"signal": "text", "contribution": "0.4923", "message": "Similar description"},
      {"signal": "location", "contribution": "0.1615", "message": "Reported in the same building"}
    ],
    "notice": "Suggestions only. A match score is not proof of ownership."
  }],
  "next_cursor": null
}
```

**`POST /api/mod/handovers/{id}/verify`** takes `{"code": "ABCD-1234"}` and returns `{"result": "ok" | "invalid", "attempts_left": 3}`, or 409 `code_used`, 410 `code_expired`, or 423 `handover_locked`. It never echoes the code.

## 10. Architecture

A modular monolith plus a worker process that shares its code.

| Component | Responsibilities |
| --- | --- |
| Frontend | React and TypeScript, with API types generated from the OpenAPI document |
| API service (FastAPI) | Routers (thin), services (use cases and transactions), authorisation, serialisers built from whitelists |
| Domain package | Pure functions: location and time scores, hybrid scoring, explanations, lifecycle tables, handover code logic, PII scanning, metrics and statistics. No framework, database, model or clock imports |
| Worker service | Runs the models: embedding jobs, matching jobs, notification delivery, retention. Claims jobs with `FOR UPDATE SKIP LOCKED` |
| PostgreSQL with pgvector | Data, vectors, the job queue, the notification outbox |
| Image storage | A volume with random keys, served through the API |
| Mail | A local mail catcher in development, an SMTP server in production |
| Evaluation package | The benchmark generator, systems, metrics, statistics and reports, run offline |

Repository layout: `backend/`, `frontend/`, `eval/` (generator, systems, results, `DATA_CARD.md`), `docs/`, `docker-compose.yml`, `.env.example`, `SPEC.md`, `README.md`, `DECISIONS.md`.

## 11. User Interface

| Screen | Contents |
| --- | --- |
| Register, verify, log in | Validation, rate-limit messages |
| Report lost, report found | Fields with precision and location pickers, photo upload (camera on phones), PII warnings |
| My reports, my claims, notifications | Status, history, actions |
| Browse found items | Search, filters, public cards with placeholders for private photos |
| Matches for a report | Ranked candidates with score, bin, explanation text and a "not mine" action, with the suggestion notice |
| Claim | Evidence, answers to prompts, evidence photos |
| Moderator queue | Pending reports, duplicate-image flags, claims with lock status |
| Handover desk | Code entry (shows success or failure and attempts left only) and the identity-check note |
| Admin | Locations and adjacency, roles, jobs, audit log, evaluation results, dashboard |

Every screen has loading, empty and error states; forms link errors with `aria-describedby`; everything works by keyboard with a visible focus; the layout works at 360 pixels wide, because most users will be on phones; colour is never the only carrier of meaning.

## 12. Security

| ID | Requirement |
| --- | --- |
| **SEC1 Passwords** | Argon2id; 12 to 128 characters; never stored, logged or returned in plaintext. |
| **SEC2 Sessions** | Server-side revocable sessions in an `HttpOnly`, `SameSite=Lax` cookie, `Secure` over TLS. |
| **SEC3 CSRF** | A CSRF token on every non-GET request. |
| **SEC4 Authorisation** | Role and ownership checked in every service and repository call; foreign resources return 404; generated role-matrix and ownership tests. |
| **SEC5 Authentication errors** | Identical responses for unknown email and wrong password; a dummy hash is checked so timing does not reveal accounts. |
| **SEC6 Rate limiting** | Failed logins (5 per account and per IP in 15 minutes), browsing, claim creation and handover attempts. |
| **SEC7 TLS for credentials** | Credentials only over TLS beyond localhost; forwarded headers trusted only from the configured proxy. |
| **SEC8 Input and uploads** | Strict schemas, forbidden unknown fields, size limits, content-based file type checks, decompression guards, parameterised queries. |
| **SEC9 Headers and CORS** | Content-Security-Policy, `nosniff`, referrer policy, frame protection, CORS limited to the configured origin; user text is always escaped. |
| **SEC10 Secrets** | Only in environment variables; no `.env` in the repository; production mode refuses placeholders. |
| **SEC11 Dependencies** | `pip-audit` and `npm audit` before release. |
| **SEC12 Logging** | Structured logs with request IDs and no passwords, tokens, codes or full emails. |

## 13. Production Deployment

The project must run as a deployed service. "Deployed" means: built into container images and run as long-lived services that you open in a browser on your own computer or from another device on the same network (intranet). It handles personal reports, photos and claim evidence, so credentials must not cross a network in the clear.

| ID | Requirement |
| --- | --- |
| **D1 Services** | Docker Compose runs `db` (PostgreSQL with pgvector and a named volume), `backend` (FastAPI under a production server), `worker` (same code and models), `frontend` (built files behind nginx, proxying `/api`), and a mail catcher for development. |
| **D2 Non-root, pinned** | Application containers run as a non-root user; images and dependencies are pinned. |
| **D3 One command** | After `cp .env.example .env` and setting the secrets, `docker compose up -d` builds and starts everything, applies migrations, and serves the UI at `http://localhost:8080`. |
| **D4 Offline models** | Model weights are fetched at build time with pinned revisions and checksums and baked into the images; the running backend and worker need no outbound network access. |
| **D5 Health and restart** | `/api/health` reports the database and worker status; all services have health checks and `restart: unless-stopped`. |
| **D6 Persistence and backup** | Named volumes for the database and the images, and a documented backup and restore of both, verified by restoring into a clean setup. |
| **D7 HTTPS on the network** | A TLS reverse proxy serves `https://<LAN-IP>:8443` with a certificate from a private certificate authority you create (a tool such as mkcert can do this) that your devices trust; plain-HTTP credentials from non-localhost clients are refused. |
| **D8 Email** | The development mail catcher shows every email; production uses an SMTP server set in the environment. Deliverability from a self-hosted server is a documented limitation. |
| **D9 Seed and demo data** | A command loads a synthetic campus tree and a demo dataset with one account per role, all labelled synthetic. |
| **D10 Optional public host** | A public deployment is optional and uses synthetic data only. |

## 14. Functional Requirements

| ID | Requirement |
| --- | --- |
| FR-01 | Accounts, roles and campus-email verification. |
| FR-02 | A hierarchical location model with adjacency and approximate locations. |
| FR-03 | Lost reports. |
| FR-04 | Found reports with private details and verification prompts. |
| FR-05 | The photo pipeline (section 5.7). |
| FR-06 | Search and browsing with privacy-safe public views. |
| FR-07 | The report lifecycle (section 5.1). |
| FR-08 | Background jobs and embeddings. |
| FR-09 | Hybrid matching, explanations and dismissals. |
| FR-10 | Notifications through a reliable outbox. |
| FR-11 | Claims. |
| FR-12 | Moderation, including conflict-of-interest and escalation rules. |
| FR-13 | Handover codes and completion. |
| FR-14 | The append-only audit log. |
| FR-15 | The analytics dashboard. |
| FR-16 | The evaluation framework and its results page. |
| FR-17 | Retention, data export and account deletion. |
| FR-18 | Administration of users, locations and jobs. |
| FR-19 | Production deployment (section 13). |
| FR-20 | Documentation, the demo journey and the data card. |

## 15. Acceptance Criteria

Clocks in tests are injected, so results are deterministic.

### Accounts, roles and security
- [ ] **AC-01** (FR-01) Registering with an email outside `ALLOWED_EMAIL_DOMAINS` returns 422 `email_domain_not_allowed`; an allowed email creates an unverified account, stores an Argon2id hash (the stored value starts with `$argon2id$`), never returns or logs the password, and a duplicate email (compared case-insensitively) returns 409.
- [ ] **AC-02** (FR-01) An unverified account cannot create reports or claims (403 `email_not_verified`). The emailed verification link works once, expires after 24 hours (injected clock), and a reused or expired link returns 410.
- [ ] **AC-03** (SEC1) Passwords of 11 characters are rejected with 422; 12 and 128 are accepted; 129 is rejected.
- [ ] **AC-04** (SEC2, SEC5, SEC6) Login sets an `HttpOnly`, `SameSite=Lax` cookie (and `Secure` over TLS); a wrong email and a wrong password return identical responses; the 6th failed login for one account within 15 minutes returns 429 with `Retry-After`.
- [ ] **AC-05** (SEC2) After logout or account deletion, the old session cookie returns 401 on every endpoint.
- [ ] **AC-06** (SEC3) A POST, PATCH or DELETE without a valid CSRF token returns 403 `csrf_failed`; GET requests are unaffected.
- [ ] **AC-07** (SEC7) A login over plain HTTP from a non-localhost client returns 403 `tls_required`; over TLS or from localhost it works; a forged forwarded-protocol header from an untrusted client is ignored.
- [ ] **AC-08** (SEC4) *Role matrix.* A generated test calls every route as anonymous, user, moderator and admin, and checks each response against the access matrix of section 3; no role ever receives more access than the matrix allows.
- [ ] **AC-09** (SEC4) User B requesting, changing or deleting user A's report, claim, evidence image, notification or handover by ID gets a 404 identical to a missing ID, and A's data is unchanged.
- [ ] **AC-10** (SEC8) A request body containing an unknown field, including `reporter_id` or `claimant_id`, is rejected with 422.
- [ ] **AC-11** (SEC8) The string `'; DROP TABLE users;--` saved in a description is stored and returned literally, and all tables remain intact.
- [ ] **AC-12** (SEC8, SEC9) A description containing `<script>alert(1)</script>` is stored as text and rendered escaped; an end-to-end test confirms no script runs, and the Content-Security-Policy header is present.
- [ ] **AC-13** (SEC9) Responses carry the Content-Security-Policy, `X-Content-Type-Options: nosniff`, `Referrer-Policy` and frame-protection headers; CORS allows only the configured origin.
- [ ] **AC-14** (SEC10) A script finds no secret patterns in tracked files and no tracked `.env`; in production mode the application refuses to start with a missing secret or one equal to the `.env.example` placeholder.
- [ ] **AC-15** (SEC8) A non-upload request body above 1 MB returns 413.
- [ ] **AC-16** (SEC11) `pip-audit` and `npm audit` show no known high or critical vulnerabilities at release; the results are recorded.

### Campus locations
- [ ] **AC-17** (FR-02) An admin can build a location tree (campus, building, floor, room or area). A node cannot become its own ancestor (422), sibling names are unique (case-insensitive), and deleting a location that reports use returns 409.
- [ ] **AC-18** (6.3) *Location score.* In a tree of Main Campus, Library (floors 1 and 2; floor 2 has Reading Room and Study Pod), Student Center and Gym, with Library and Student Center adjacent: Reading Room against Reading Room scores **1.0**; Library against Reading Room **0.8**; Reading Room against Study Pod **0.7**; Reading Room against Floor 1 **0.6**; Library against Student Center **0.5**; Library against Gym **0.2**; a location in another campus **0.0**; a missing location gives `null`.
- [ ] **AC-19** (FR-02) Adjacency is symmetric: adding Library to Student Center makes both directions score 0.5, and removing it returns the pair to 0.2.
- [ ] **AC-20** (FR-02) A report can use a location at any level (building-level is allowed), no GPS is ever required, and optional coordinates are stored rounded to 3 decimal places.

### Reports, lifecycle and uploads
- [ ] **AC-21** (FR-03) A lost report requires a title (3 to 120 characters), a description (10 to 2,000), a category, a lost-time window and a location (a campus place, a typed place, or both, D-22); validation errors list each failing field; saving returns without waiting for embeddings.
- [ ] **AC-22** (FR-04) A found report requires the same fields plus a found time; it may add private details (up to 1,000 characters) and up to 3 verification prompts (each up to 200 characters). With moderation on (default), it starts as `pending_review` and is not listed until approved.
- [ ] **AC-23** (5.2) For the timezone `Asia/Kolkata`, a `day` precision on 2026-10-15 gives the window 2026-10-14T18:30:00Z to 2026-10-15T18:29:59.999Z; `morning` is 06:00 to 12:00 local, `afternoon` 12:00 to 17:00, `evening` 17:00 to 22:00, `night` 22:00 to 06:00 (crossing midnight); `exact` is a zero-length window.
- [ ] **AC-24** (FR-03) A category outside the fixed list returns 422.
- [ ] **AC-25** (5.1) *Found-report lifecycle.* Every legal transition in the table of section 5.1 succeeds, and every other (state, action) pair returns 409 `invalid_transition` and leaves the report unchanged (tested exhaustively).
- [ ] **AC-26** (5.1) The same exhaustive check passes for the lost-report lifecycle.
- [ ] **AC-27** (FR-07) A reporter can close their own report; closing someone else's returns 404; a `returned` found report can never reopen.
- [ ] **AC-28** (5.6) *PII scanner.* `4111 1111 1111 1111` is flagged `card_number` (it passes the Luhn check); `4111 1111 1111 1112` fails Luhn and is flagged `long_number` (16 digits); `1234 5678 9012` is flagged `long_number`; `+91 98765 43210` is flagged `phone`; `a.b@campus.edu` is flagged `email`; `blue bottle with a RIA sticker` is not flagged.
- [ ] **AC-29** (5.6) Public fields (title, description) containing a flagged pattern are rejected with 422 `pii_detected` that names the kind but does not echo the value; private details may contain such text and show a warning only.
- [ ] **AC-30** (S4) For the sensitive categories (`id_card`, `wallet`), images are marked non-public automatically, whatever the moderator does, and the public listing shows a placeholder.
- [ ] **AC-31** (5.7) Upload type is decided by the file's content, not its name: a PNG named `.jpg` is accepted as PNG; a text file named `.jpg` returns 415; SVG and GIF return 415; JPEG, PNG and WebP are accepted.
- [ ] **AC-32** (5.7) A file of 5 MB is accepted and one byte over returns 413; an image above 6,000 × 6,000 pixels returns 422 `image_too_large` before it is fully decoded.
- [ ] **AC-33** (5.7) A test image carrying GPS and camera EXIF data has none of it after processing; images are re-encoded, resized to at most 1,600 pixels on the long side, and a thumbnail is created.
- [ ] **AC-34** (5.7) Stored files use random UUID keys; the original file name is neither stored nor served.
- [ ] **AC-35** (5.7) Images are served only through an authorised route that checks visibility: a private image returns 404 to other users, public images require a login, and responses carry the correct content type and `nosniff`.
- [ ] **AC-36** (5.7) A fourth image on one report returns 422.
- [ ] **AC-37** (5.7) A 64-bit difference hash is stored per image: an identical image has Hamming distance 0 and a resized copy at most 4 from the original, while an unrelated image has more than 10; a found image whose distance to an image on another user's found report is at most 4 is flagged `duplicate_image` for moderators.

### Browsing, search and public views
- [ ] **AC-38** (FR-06) The found-item listing shows only `open` items. It excludes `pending_review`, `removed`, `returned` and archived items, and shows building-level location, category, public description, date and the public photo.
- [ ] **AC-39** (P1) *Default-deny contract test.* Every public serialiser is checked against an explicit whitelist: the listing and detail responses never contain private details, verification prompts, reporter identity, locations finer than building level, private images, or any column added later without being whitelisted.
- [ ] **AC-40** (P1) Lost reports are visible only to their reporter, moderators and admins.
- [ ] **AC-41** (FR-06) Search matches title and description (PostgreSQL full-text), filters by category, by building (including all descendants) and by date range, combines filters with AND, and paginates with a stable cursor.
- [ ] **AC-42** (FR-12) Moderators and admins see full details, including private fields and exact locations.
- [ ] **AC-43** (P5) The browse endpoints are rate-limited per user (120 requests per minute, *initial*) and return 429 with `Retry-After` beyond it.
- [ ] **AC-44** (P5) Listing and detail require a login (campus users only), and all IDs are unguessable UUIDs.

### Background jobs and embeddings
- [ ] **AC-45** (FR-08) Saving a report enqueues its embedding jobs and returns; *(initial target)* the create-report endpoint takes at most **300 ms at p95** with the models switched off.
- [ ] **AC-46** (FR-08) With 2 workers and 1,000 jobs, every job completes exactly once (`FOR UPDATE SKIP LOCKED`).
- [ ] **AC-47** (FR-08) A failing job retries after 1, 2, 4 and 8 minutes (injected clock), then becomes `failed` after 5 attempts and appears on the admin page; a manual retry works.
- [ ] **AC-48** (FR-08) Running the embedding job again for the same entity and model version leaves exactly one embedding row.
- [ ] **AC-49** (6.1) Embeddings record model name, model version and dimension. Matching compares only vectors of the same version; changing the configured version triggers a backfill, and matches computed with the old version are marked stale.
- [ ] **AC-50** (6.1) The database rejects a vector of the wrong dimension.

### Matching and explanations
- [ ] **AC-51** (6.2) The text score is `max(0, cosine)` of normalised embeddings: a cosine of 0.82 gives **0.82** and −0.10 gives **0**.
- [ ] **AC-52** (6.3) *Time score.* Overlapping windows score **1.0**; a found time 12 hours after the lost window ends scores **0.7788**, and 48 hours after scores **0.3679**; a found time 12 hours before the lost window starts scores **0.1353**, and 6 hours before scores **0.3679**.
- [ ] **AC-53** (6.4) *Hybrid example.* With weights text 0.40, image 0.35, location 0.15, time 0.10 and signals 0.8, 0.6, 0.7, 0.5, the score is **0.685**. With the image signal missing, the weights renormalise over 0.65 and the score is **0.7308**.
- [ ] **AC-54** (6.4) Missing signals are excluded, never counted as zero: a pair with only a text signal scores exactly its text score.
- [ ] **AC-55** (6.2) The image signal uses image-to-image similarity when both reports have photos, text-to-image similarity (the lost text against the found photo, or the reverse) when exactly one does, and `null` when neither does; the explanation names which was used.
- [ ] **AC-56** (6.5) Candidates are only lost-to-found pairs where both reports are `open`, the reporters differ, the pair was not dismissed, the found item is not reserved or returned, and the found time lies between 6 hours before the lost window starts and 30 days after it ends; each exclusion has its own fixture test.
- [ ] **AC-57** (6.5) Candidates are ordered by score descending, then older found report first, then ID, identically across runs.
- [ ] **AC-58** (FR-09) The matches endpoint returns at most 10 candidates (a parameter, maximum 50) with score, bin, signal scores and explanation, and never includes a found report's private fields.
- [ ] **AC-59** (6.6) Explanation contributions sum exactly to the combined score (within 1e-9); the explanation lists signals contributing at least 10% of the score, or the top 3; and for the example of AC-53 without an image the contributions are text 0.4923, location 0.1615, time 0.0769.
- [ ] **AC-60** (P1) A canary string placed in a found report's private details never appears in any explanation, match response, notification or log.
- [ ] **AC-61** (FR-09) Dismissing a match removes the pair permanently for that user and records the feedback; it never reappears after a recompute.
- [ ] **AC-62** (S1) No code path changes a report or claim status because of a score: setting a pair's score to 0.99 changes no status, and the UI and API label scores as suggestions.
- [ ] **AC-63** (6.5) A new found report triggers scoring against open lost reports, and a new lost report against open found reports; each (lost, found, model version, weights version) is scored once and recomputing is idempotent.
- [ ] **AC-64** (6.4) Each stored candidate records its weights version and model versions; changing the weights creates a new version and does not overwrite earlier results.
- [ ] **AC-65** (6.4) Scores of at least 0.75 are `high`, at least 0.55 are `medium`, and the rest `low`; a match notification is created only for a score of at least 0.65 ranked in the top 3 (*initial*).
- [ ] **AC-66** (6.5) *(initial target)* On 10,000 vectors, the HNSW index returns at least **95%** of the exact top-10 results (recall@10 against exact search).
- [ ] **AC-67** (6.5) *(initial targets)* Retrieving and scoring the top 10 for one lost report against 10,000 found reports takes at most **200 ms at p50 and 800 ms at p95**, excluding embedding time.

### Notifications
- [ ] **AC-68** (FR-10) A notification row is written in the same transaction as the state change that causes it; if the transaction rolls back, no notification exists.
- [ ] **AC-69** (FR-10) Processing the same event twice creates one notification (a unique event key); an email retried after a crash carries the same `Message-ID`, so duplicates are recognisable.
- [ ] **AC-70** (FR-10) An SMTP failure is retried with exponential backoff up to 5 attempts, then marked `failed`.
- [ ] **AC-71** (P1) Match and claim emails contain no private details or claim evidence; the handover code appears only in the email and in-app message to the approved claimant.
- [ ] **AC-72** (FR-10) Opting out of match emails stops them but not claim or handover emails; in-app notifications still appear.
- [ ] **AC-73** (FR-10) At most 5 match emails per user per day (*initial*); further matches appear in-app only.
- [ ] **AC-74** (FR-10) The in-app notification list is owner-only, paginated, and supports read and unread.

### Claims and moderation
- [ ] **AC-75** (FR-11) A claim on a found item needs evidence text (20 to 2,000 characters) and an answer to every verification prompt, and may add up to 3 private evidence images; a user has at most 3 active claims and at most one claim per found item.
- [ ] **AC-76** (5.3) *Claim lifecycle.* Every legal transition in the table of section 5.3 succeeds, and every other (state, action) pair returns 409 and changes nothing (tested exhaustively).
- [ ] **AC-77** (P2) Claim evidence and answers are visible only to the claimant and moderators; the finder and other users never see them.
- [ ] **AC-78** (FR-12) The moderator queue is ordered by submission time; opening a claim assigns a lock to that moderator for 30 minutes, during which others cannot decide it.
- [ ] **AC-79** (FR-12) Approving or rejecting needs a decision note of at least 10 characters; approving makes the found item `reserved` and issues a handover; both decisions write an audit row and a notification.
- [ ] **AC-80** (FR-12) A moderator cannot decide a claim on an item they reported, or a claim they made themselves (403 `conflict_of_interest`).
- [ ] **AC-81** (FR-12) Only one claim per found item can be approved at a time; approving another while the item is reserved returns 409.
- [ ] **AC-82** (5.3) `needs_more_info` lets the claimant add evidence and sends the claim back into the queue.
- [ ] **AC-83** (5.3) A claimant can withdraw before approval; withdrawing after approval cancels the handover and returns the item to `open`.
- [ ] **AC-84** (P6) A user with 3 rejected claims in 30 days is flagged for moderators and limited to 1 active claim (*initial*).
- [ ] **AC-85** (FR-12) A claim unreviewed after 14 days is marked `escalated` and shown first to admins (*initial*).

### Handover codes
- [ ] **AC-86** (5.4) A code is 8 characters from the 32-character alphabet `0123456789ABCDEFGHJKMNPQRSTVWXYZ` (40 bits), generated from a cryptographically secure random source.
- [ ] **AC-87** (5.4) Only an HMAC-SHA-256 of the code (with a server secret) is stored; the plaintext is never persisted or logged, and is shown only to the approved claimant.
- [ ] **AC-88** (5.4) `abcd-1234`, `ABCD 1234` and `ABCD1234` are the same code, and the substitutions `O` to `0` and `I` or `L` to `1` are accepted.
- [ ] **AC-89** (5.4) *(injected clock)* A code issued at time T is valid at T + 47:59:59 and invalid at T + 48:00:00.
- [ ] **AC-90** (5.4) A successful verification completes the handover; verifying the same code again returns 409 `code_used`.
- [ ] **AC-91** (5.4) After 5 wrong attempts the handover locks; a 6th attempt returns 423 `handover_locked` even with the correct code until a moderator reissues it. The guessing bound is `5 / 2^40 ≈ 4.5 × 10⁻¹²`.
- [ ] **AC-92** (5.4) Reissuing (moderator only, at most 3 times) invalidates the old code, resets the attempts, and writes an audit row.
- [ ] **AC-93** (FR-13) Completing a handover needs a moderator and an identity-check note, and in one transaction sets the claim `completed`, the found report `returned`, the linked lost report `resolved`, other open claims on the item `rejected` (`item_returned`), writes the audit rows, and creates the notifications.
- [ ] **AC-94** (5.4) When a code expires unused, the claim becomes `expired`, the found item returns to `open`, the claimant is notified, and other claims can be reviewed.
- [ ] **AC-95** (5.4) Code comparison is constant-time (a static check requires `hmac.compare_digest` or equivalent).
- [ ] **AC-96** (P1) No endpoint other than the claimant's own claim response ever returns a code, and no endpoint returns the stored hash.

### Audit, retention and data rights
- [ ] **AC-97** (FR-14) Audit rows cannot be updated or deleted: a raw SQL `UPDATE` or `DELETE` on the audit table fails because of a trigger or revoked privileges.
- [ ] **AC-98** (FR-14) Each of these events writes an audit row with actor, role, action, entity and time: report removal, claim decision, handover issue, lock, reissue, completion and expiry, role change, location change, retention action and account deletion.
- [ ] **AC-99** (FR-18) Role changes are admin-only and are audited, and the last admin cannot be demoted or deleted.
- [ ] **AC-100** (5.5) *(injected clock)* A found report still `open` after 90 days becomes `unclaimed_expired`, and a moderator records a disposition (`donated`, `disposed` or `kept`).
- [ ] **AC-101** (5.5) Images are deleted 30 days after their report closes and claim evidence 30 days after the claim closes: files are removed from storage, rows are marked deleted, and their embeddings are removed.
- [ ] **AC-102** (5.5) Audit rows older than the configured period (365 days, *initial*) can be removed only by the retention job's privileged role.
- [ ] **AC-103** (FR-17) Deleting an account removes its email, name, sessions, notifications, private images and claim evidence, anonymises its reports, closes its open reports, keeps audit rows with a pseudonymous ID, and a scan of a database dump finds no occurrence of the deleted email.
- [ ] **AC-104** (FR-17) The data export contains the user's own reports, claims, evidence and notifications as JSON, and no one else's data.

### Analytics
- [ ] **AC-105** (FR-15) *Fixture.* With 10 found reports created in a period, of which 4 are `returned`, 2 are `unclaimed_expired` and 4 are still open, the dashboard shows: recovery rate = returned / (returned + unclaimed_expired) = **0.667**; unclaimed rate = unclaimed_expired / created = **0.2**; and the median time to recovery is the median of (handover completed − found report created) over the returned items.
- [ ] **AC-106** (FR-15) The dashboard is available only to moderators and admins.
- [ ] **AC-107** (FR-15) With no data the dashboard returns zeros or `null` with status 200 and no errors.
- [ ] **AC-108** (FR-15) A banner states when operational metrics come from synthetic demonstration data, and that they show the dashboard, not real-world effectiveness.

### Evaluation
- [ ] **AC-109** (7.1) The benchmark generator is deterministic for a given seed and produces 300 true items, each with a lost report and a found report, plus 100 background found reports with no lost report.
- [ ] **AC-110** (7.1) Items are split 30% development and 70% test, stratified by category, with no item in both; the test set's content hash is recorded.
- [ ] **AC-111** (7.5) Tuning code cannot read test-set labels: pointing it at the test set raises an error, verified by a test.
- [ ] **AC-112** (7.3) *Metric fixture.* For first-correct ranks `[1, 3, 2, 10]`: Recall@1 = **0.25**, Recall@3 = **0.75**, Recall@5 = **0.75**, MRR = **0.4833**, nDCG@10 = **0.605** (±0.001), Precision@5 = **0.15**.
- [ ] **AC-113** (7.2) On a toy corpus (`blue water bottle`, `red backpack`, `blue backpack`), the BM25 query `blue bottle` ranks the first document first.
- [ ] **AC-114** (7.4) The bootstrap confidence interval for MRR is deterministic for a seed; for all ranks equal to 1 it is exactly [1.0, 1.0]; and in 100 simulations with a known true value, it covers that value in at least 90.
- [ ] **AC-115** (7.4) The paired bootstrap for ranks A = `[1,1,1,1]` and B = `[2,2,2,2]` gives a difference in MRR of **0.5** with an interval that excludes 0.
- [ ] **AC-116** (7.2) The harness evaluates BM25, text embeddings, image similarity, the hand-weighted hybrid and the learned-fusion hybrid, plus the ablations of 7.6, and every run records model names and versions, weights, seed, dataset hash, git commit and hardware.
- [ ] **AC-117** (7.5) Weights are tuned on the development set only (a grid in steps of 0.05, selected by development MRR); learned fusion is trained on the development set only; the chosen configuration is frozen and hashed before the test run.
- [ ] **AC-118** (7.5) The final test evaluation is run once from the frozen configuration; re-running with the same seed and versions reproduces identical numbers; results are saved as JSON and CSV with confidence intervals.
- [ ] **AC-119** (7.6) The report includes: removing each signal in turn; 0, 25, 50, 75 and 100% of photos missing; and location (one level off) and time (24 hours off) noise at 0, 25 and 50%, each with confidence intervals.
- [ ] **AC-120** (7.3) Latency (p50 and p95) is reported per system at 1,000, 10,000 and 100,000 candidates, with approximate against exact search, and the hardware is recorded.
- [ ] **AC-121** (7.7) Hypotheses are written before the test run (H1: the hybrid has a higher MRR than the best single-signal baseline); the outcome is reported whichever way it falls; the limits of synthetic text, location and time are stated; and a real-photo subset of at least 60 items is reported separately.
- [ ] **AC-122** (P7) The evaluation data contains no faces or personal data and has EXIF removed; contributor consent and photo licences are recorded, and `eval/DATA_CARD.md` documents how it was built.
- [ ] **AC-123** (FR-16) *(Superseded by D-23: no admin page; `GET /api/admin/evaluation` remains.)* The admin evaluation page shows the latest saved results with their model versions and weights version, and never evaluates on live private data.

### Interface and accessibility
- [ ] **AC-124** (11) Every screen in section 11 has loading, empty and error states, and form errors are linked to their fields with `aria-describedby`.
- [ ] **AC-125** (11) A keyboard-only end-to-end test reports a found item and submits a claim; every interactive element shows a visible focus.
- [ ] **AC-126** (11) An automated accessibility scan (axe) reports no serious or critical violations on the main pages.
- [ ] **AC-127** (11) At 360 × 740 pixels no main page scrolls horizontally, and the photo field opens the camera on a phone.
- [ ] **AC-128** (11) The matches screen shows each candidate's score, bin, an explanation as text (not colour alone), and a "not mine" action, with a notice that scores are suggestions.
- [ ] **AC-129** (11) The handover desk lets a moderator type a code, shows only success or failure and the remaining attempts, and never displays the code.
- [ ] **AC-130** (11) The moderation queue shows pending reports, duplicate-image flags and claims, with the claim lock status.

### Quality and architecture
- [ ] **AC-131** (NFR) `alembic upgrade head` builds the schema (including the vector extension) from an empty database, `alembic downgrade base` works, and `alembic check` reports no drift.
- [ ] **AC-132** (10) A layering check confirms that the domain package imports no framework, database, model or clock module, and that routers contain no business rules.
- [ ] **AC-133** (10) The frontend's API types are generated from the backend's OpenAPI document, and CI fails if they are out of date.
- [ ] **AC-134** (NFR) *(initial targets)* Line coverage is at least **90%** for the domain and services and **70%** for the frontend.
- [ ] **AC-135** (NFR) CI runs lint, strict type checks, unit, database, API, worker, frontend and end-to-end tests, and fails on any failure.
- [ ] **AC-136** (SEC12) A canary test shows that no password, token, session ID, handover code or full email address appears in the logs.
- [ ] **AC-137** (NFR) *(initial targets)* With the demo dataset, the browse and search endpoints take at most **300 ms at p95** and the dashboard at most **500 ms**.

### Deployment and documentation
- [ ] **AC-138** (D3) From a fresh clone, `cp .env.example .env` and `docker compose up -d` start every service, apply migrations, and serve the UI at `http://localhost:8080`.
- [ ] **AC-139** (D4) *Models work offline.* With outbound network access blocked for the backend and worker containers, a new report is embedded, matched and explained successfully.
- [ ] **AC-140** (D5) `/api/health` returns 200 with the database and worker status; all containers report healthy, restart after a killed process, and run as non-root.
- [ ] **AC-141** (D6) Data survives `docker compose down` and `up`; a backup of the database and the image volume restores into a clean setup with identical row counts and image hashes.
- [ ] **AC-142** (D7) Through the TLS proxy at `https://<LAN-IP>:8443`, a device that trusts your private certificate authority loads the app without a warning, only TLS 1.2 or higher is accepted, and plain-HTTP login from a non-localhost client is refused.
- [ ] **AC-143** (D7) From a second device on the same network, sign in, report an item and see a notification. This is a manual check: record the date and result in the README.
- [ ] **AC-144** (D8) In development, emails arrive in the local mail catcher; in production they use the configured SMTP server; a test reads the catcher's API to confirm the verification, match and handover emails.
- [ ] **AC-145** (D9) A seed command loads a synthetic campus tree and a demo dataset with accounts for each role, all clearly labelled synthetic; the full demo journey runs in the browser.
- [ ] **AC-146** (FR-20) The blueprint's demo runs end to end in CI against the Compose stack: report a lost item with a photo, report the same item as found in different words, see keyword results and then ranked matches with the explanation, submit a claim, review it as a moderator, complete the handover with the code, and open the dashboard.
- [ ] **AC-147** *(Optional)* (D10) A public deployment runs with synthetic data only and limited registration.
- [ ] **AC-148** (FR-20) The README documents setup, environment variables, seed data, migrations, tests, the demo, and known limitations; `docs/` holds the ER diagram, the architecture diagram, `DATA_LICENCES.md` (datasets, model weights and photos, each with its licence), model cards, `eval/DATA_CARD.md`, and `test-plan.md` mapping every acceptance criterion to a test or manual check.
- [ ] **AC-149** (FR-20) The README states the limitations: the synthetic benchmark, unverified real-world effectiveness, self-hosted email deliverability, no SSO, scores that are only suggestions, and the chosen retention periods.

## 16. Traceability to the Blueprint

| Blueprint | Covered by |
| --- | --- |
| 2. User journey (report, match, claim, review, handover) | AC-21 to AC-96 |
| 3. Modules: portal, matching service, administration, notifications, analytics | AC-38 to AC-74, AC-105 to AC-108 |
| 4.1 Multimodal matching | AC-51 to AC-67 |
| 4.2 Explainable suggestions | AC-59, AC-62, AC-60 |
| 4.3 Campus-aware locations | AC-17 to AC-20 |
| 4.4 Secure claim and handover | AC-75 to AC-96 |
| 4.5 Research-grade evaluation | AC-109 to AC-123 |
| 8. Security, privacy and trust | AC-01 to AC-16, AC-97 to AC-104 |
| 9. Evaluation plan | AC-109 to AC-123 |
| 13. Definition of done | Section 22 |

## 17. Non-Functional Requirements

| Area | Requirement |
| --- | --- |
| Correctness | Scoring, lifecycle, code and metric logic live in the pure domain package with the worked numbers of the criteria as tests |
| Reliability | State changes and their notifications and jobs are written in one transaction (outbox); workers are idempotent |
| Privacy | Whitelist serialisers (P1), retention (P4), data minimisation (P3) |
| Performance | The targets in the matching, jobs and quality criteria |
| Reproducibility | Pinned models and dependencies, seeded benchmark, recorded configuration and dataset hashes |
| Accessibility | Section 11 |
| Maintainability | Thin routers, services for rules, a layering check |
| Observability | Request IDs, job states and queue age visible to admins, without private data |

## 18. Testing Strategy

| Layer | What it checks |
| --- | --- |
| Unit (domain) | Scores, hybrid, explanations, lifecycle tables, codes, PII scanner, metrics, statistics, with the worked numbers |
| Property | Role matrix, ownership, public-view whitelist, transition tables (exhaustive), contributions sum to the score |
| Database | Constraints, vector dimensions, audit immutability, transactions, migrations, index use |
| API | Authentication, CSRF, validation, uploads, errors, pagination |
| Worker | Job claiming, retries, idempotency, outbox delivery |
| Model integration | Real models on a small fixture set (marked slow, run in CI nightly or before release) |
| Frontend | Forms, states, matches display, claim flow |
| End to end | The demo journey, the keyboard-only flow, mobile layout, accessibility scan, XSS check |
| Evaluation | Metric and statistics unit tests; deterministic generator; the leakage guard |
| Deployment | Compose build, health, offline operation, backup and restore, TLS, second-device check |

Expected values come from the calculations written in the acceptance criteria, not from copying the application's output. Fast tests use fixed stand-in embeddings so the suite needs no model downloads.

## 19. Build Order

Build in this order, because each step depends on the one before it. A step is done when its acceptance criteria pass. There are no time estimates; go as fast as the tests allow.

| Step | Build | Acceptance criteria |
| --- | --- | --- |
| 1 | Repo and tooling setup, CI skeleton, ER diagram, and a walking-skeleton Compose stack (database with pgvector, a backend with `/api/health`, an idle worker, a placeholder frontend, the mail catcher) | AC-138 (skeleton), AC-131 (start) |
| 2 | Accounts, roles, email verification, sessions, CSRF, rate limiting, the TLS rule, the role-matrix and ownership test harness, and the audit-log writer | AC-01 to AC-16 |
| 3 | Campus locations and adjacency | AC-17 to AC-20 |
| 4 | Reports, lifecycle tables, PII scanning, and the photo pipeline | AC-21 to AC-37 |
| 5 | Browsing, search and the whitelisted public views | AC-38 to AC-44 |
| 6 | The job framework, the embedding worker and model registry, and the notification outbox | AC-45 to AC-50, AC-68 to AC-74 |
| 7 | The matching engine: signals, hybrid, candidates, retrieval, explanations, dismissals | AC-51 to AC-67 |
| 8 | Claims and moderation | AC-75 to AC-85 |
| 9 | Handover codes and completion | AC-86 to AC-96 |
| 10 | Retention, deletion, export, and the remaining audit events | AC-97 to AC-104 |
| 11 | The analytics dashboard | AC-105 to AC-108 |
| 12 | The evaluation framework: generator, systems, metrics, statistics, tuning, final run, results page | AC-109 to AC-123 |
| 13 | Interface polish, accessibility and quality gates | AC-124 to AC-130, AC-131 to AC-137 |
| 14 | Production deployment: offline models, TLS proxy, backups, seed and demo data, the end-to-end journey in CI, documentation | AC-138 to AC-149 |
| 15 | Stretch: SigLIP comparison, multilingual text, face and plate blurring, learning from dismissals, SSO, digest email | None required |

The benchmark generator, the metrics and the statistics in step 12 depend only on the domain package, so they can be built early and in parallel with steps 4 to 6. The matching engine (step 7) needs the embedding worker (step 6). The frontend of each step can start once that step's API is fixed in the OpenAPI document. Keep the Compose stack from step 1 working throughout.

**If you need to cut scope, cut in this order:** all of step 15, the optional public host, the learned-fusion system, the SigLIP comparison, then duplicate-image detection. Never cut the whitelist views, the role and ownership tests, the handover-code rules, the leakage guard, or the honest reporting.

## 20. Decisions Log

| ID | Date | Decision | Alternatives | Why |
| --- | --- | --- | --- | --- |
| D-01 | 2026-10-18 | AI is advisory: scores never change a state | Auto-approve high scores | Ownership needs human judgement, and false claims are the main risk |
| D-02 | 2026-10-18 | Lost reports are private; only found reports are browsable | Public lost reports | Lost reports reveal owners and valuables, and browsing found items helps owners |
| D-03 | 2026-10-18 | Found reports and photos are moderated before publication (configurable) | Publish immediately | Stops spam, personal data in photos, and stolen-property listings |
| D-04 | 2026-10-18 | Missing signals are excluded and weights renormalised | Treat missing as zero | A missing photo is not evidence of a mismatch |
| D-05 | 2026-10-18 | The time score is asymmetric (steeper when found before lost) | Symmetric decay | Reflects that a thing cannot be found before it is lost, apart from imprecise reporting |
| D-06 | 2026-10-18 | A location-tree score with an adjacency table | GPS distance | Works indoors, tolerates approximate reports, and needs no precise location data |
| D-07 | 2026-10-18 | Embeddings are computed by workers, and models are baked into the images | Compute in requests; download models at runtime | Fast requests, offline operation, and pinned reproducible models |
| D-08 | 2026-10-18 | pgvector with HNSW in PostgreSQL | A separate vector database | One database to run, back up and secure; recall against exact search is measured |
| D-09 | 2026-10-18 | 8-character codes (40 bits), HMAC-stored, 5 attempts, 48-hour expiry | 6-digit numeric codes | A far smaller guessing chance (about 4.5 × 10⁻¹²) for the same effort at the desk |
| D-10 | 2026-10-18 | Server-side sessions with CSRF tokens | Stateless JWTs | Revocable, and not readable by scripts |
| D-11 | 2026-10-18 | A synthetic benchmark plus small real-photo and human-written subsets | Real users' reports | Privacy, consent and reproducibility; the limits are stated |
| D-12 | 2026-10-18 | Development-only tuning with a frozen configuration | Tune on all data | Prevents leakage, and the test run stays honest |
| D-13 | 2026-10-18 | Bootstrap confidence intervals and paired differences | Single-number comparison | Shows whether a difference is real |
| D-14 | 2026-10-18 | An append-only audit table enforced in the database | Application-level logging | Moderation and handover events must be trustworthy |
| D-15 | 2026-10-18 | A job queue and notification outbox in PostgreSQL | A message broker | No extra service, with transactional consistency |
| D-16 | 2026-10-18 | Credentials only over TLS beyond localhost, with a private certificate authority | Plain HTTP on the network | Passwords and sessions must not be readable on the network |
| D-17 | 2026-10-18 | Email-only identity with a campus-domain restriction | Collect phone numbers or student IDs | Data minimisation |
| D-18 | 2026-10-20 | Automated face and license plate blurring in photo pipeline | Unredacted photo storage; external cloud vision APIs | Protects bystander and student privacy by smoothing sensitive biometric and vehicle zones before disk persistence without leaking images to third-party APIs |
| D-19 | 2026-10-21 | A report's CLIP text vector is stored in `image_embeddings` (entity = report id, model name `clip-ViT-B-32:text`) and drives the text-to-image signal | A new table; computing CLIP text vectors at match time | Same 512-d space as photo vectors, no schema change, matching stays a pure vector comparison |
| D-20 | 2026-10-21 | A signed-in user starting a claim sees the finder's verification questions through a claim-form endpoint; listings and detail views never include them | Keep prompts hidden (AC-75 cannot be satisfied); show prompts publicly | Resolves the P1 / AC-75 conflict: the answers are the secret, not the questions (pending owner confirmation) |
| D-21 | 2026-10-21 | Credentials only over TLS or from this machine; forwarded headers trusted only from `TRUSTED_PROXIES`; published ports bound to 127.0.0.1; LAN uses HTTPS on 8443 | Trust any 172.* peer and all proxied requests in development | The old rule let LAN clients log in over plain HTTP and let containers forge forwarded headers (SEC7) |
| D-22 | 2026-10-28 | "Where?" is free text with campus suggestions. Text that starts with a campus place links that place (`location_id`); the words are kept in `location_text`, which only the reporter and staff see and which is PII-scanned. A report with only typed text gets a `null` location score (6.3) and no building in public views | Fixed pickers only; geocoding or parsing free text into the tree | Owner request: people describe spots the tree does not have ("bench outside the canteen"). Matching keeps working whenever a place is linked, and P1 holds because the typed text is private |
| D-23 | 2026-10-29 | The admin area has no Evaluation or Retention tab. `GET /api/admin/evaluation` and `POST /api/admin/retention/run` stay for scripts, and the worker still runs retention hourly | Keep both tabs | Owner request: the admin console is for running the service; offline research results and a manual retention button do not belong there |

## 21. Open Questions

- [ ] Which campus email domain or domains will you allow, and who will be the moderators and admins in the demo?
- [ ] Which text and image models will you pin, and what are the licences of their weights (record them in `DATA_LICENCES.md`)?
- [ ] Who will take the real-photo subset (at least 60 items, two photographers each) and write the human-written subset, and where is the consent recorded?
- [ ] Which retention periods suit your campus (the defaults are 90, 30 and 365 days)?
- [ ] Will you compare a SigLIP-family model, as the blueprint suggests, and does the evaluation budget allow it?
- [ ] The blueprint mentions an "Antigravity CLI" workflow: will you use Claude Code or that tool? (The files below work with either; check the tool's documentation for the name of its rules file.)
- [ ] Do you want a public synthetic-data demo, and on which free host?

## 22. Definition of Done

- [ ] AC-01 to AC-149 pass or have a recorded measurement (the optional criterion excepted).
- [ ] The role-matrix, ownership, whitelist, handover-code and leakage-guard tests pass in the normal suite.
- [ ] The system runs in its containers on your computer with the models working offline, and you have opened it over HTTPS from a second device.
- [ ] The evaluation is run once on the frozen configuration, and its results, intervals, ablations, latency and limitations are in the README and on the results page, whichever way H1 falls.
- [ ] The blueprint's demo runs end to end.
- [ ] The README, diagrams, `DECISIONS.md`, `DATA_LICENCES.md`, model cards, data card and test plan are complete.
- [ ] You can explain every module, formula, metric and security rule without notes.

