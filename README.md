# Smart Campus Lost-and-Found Network

An accessible, privacy-preserving campus lost-and-found system featuring explainable multimodal retrieval, evidence-based claim verification, single-use expiring handover desk codes, immutable audit logging, and empirical benchmark evaluation.

---

## 1. Overview
The platform combines a reliable campus operational workflow with a controlled retrieval research framework:
* **Product:** Privacy-safe found item listings, hierarchical campus location tree, safe image pipeline (magic byte verification, pixel guards, EXIF metadata stripping, 64-bit dHash duplicate detection), moderator claim locks, single-use 8-character handover codes (HMAC-SHA256, 5-attempt lock, 48-hour expiry), transactional outbox notifications, and retention rules.
* **Research:** Controlled evaluation comparing BM25 keyword search, text embeddings (`all-MiniLM-L6-v2`), CLIP ViT-B/32 image embeddings, hand-weighted hybrid, and learned fusion across 400 benchmark items with bootstrap confidence intervals and paired hypothesis testing ($H_1$).

---

## 2. Architecture & Documentation Links

The system is designed as a clean modular monolith with dedicated background workers:
* **System Architecture:** [`docs/architecture.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/architecture.md)
* **Entity-Relationship Diagram:** [`docs/er-diagram.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/er-diagram.md)
* **Data and Model Licences:** [`docs/DATA_LICENCES.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/DATA_LICENCES.md)
* **Benchmark Dataset Card:** [`eval/DATA_CARD.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/eval/DATA_CARD.md)
* **Acceptance Criteria Test Plan:** [`docs/test-plan.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/test-plan.md) (Full traceability for AC-01 to AC-149)
* **Learning Log & Viva Q&A:** [`docs/learning-log.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docs/learning-log.md)
* **Architectural Decisions Log:** [`DECISIONS.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/DECISIONS.md)

---

## 3. Quick Start with Docker Compose

### Prerequisites
* Docker & Docker Compose (or local Python 3.12+ and Node.js 20+)
* Git

### Launching the Stack
1. **Configure Environment:**
   ```bash
   cp .env.example .env
   ```
2. **Build and Launch Services:**
   ```bash
   docker compose up -d --build
   ```
3. **Apply Database Migrations:**
   ```bash
   docker compose exec -T backend alembic upgrade head
   ```
4. **Seed Campus Tree, Users, and Demo Reports (AC-145):**
   ```bash
   docker compose exec -T backend python -m app.seed
   ```
5. **Access Endpoints:**
   * **Web Application:** `http://localhost:8080`
   * **Backend API Documentation:** `http://localhost:8000/docs`
   * **Mailpit (In-Development Mail Catcher):** `http://localhost:8025`

### Pre-seeded Demo Accounts
All seeded accounts use standard campus credentials for demonstration:
| Role | Email | Password | Intended Actions |
| :--- | :--- | :--- | :--- |
| **Admin** | `admin@campus.edu` | `CampusAdmin2026!` | Model registry, location graph, retention inspection |
| **Moderator** | `moderator@campus.edu` | `CampusMod2026!` | Review queue, claim locks, desk handover verification |
| **Student 1** | `student1@campus.edu` | `StudentPass2026!` | Alice: Report lost items, review match suggestions |
| **Student 2** | `student2@campus.edu` | `StudentPass2026!` | Bob: Report found items, file claims |

---

## 4. End-to-End Demo Journey (AC-146)

The blueprint demo lifecycle can be run automatically via our integration test or performed in the browser:
1. **Student A Reports Lost Item:** Reports "Lost Matte Black ThinkPad X1" with photo in Central Campus Library.
2. **Student B Reports Found Item:** Reports "Black Lenovo Notebook Computer" with verification prompt ("What OS sticker is on the lid?").
3. **Staff Approves Listing:** Moderator approves found report, transitioning it to `open`.
4. **Student A Discovers Item:** Student A sees it via keyword search (`/api/found?q=Lenovo+laptop`) and views ranked multimodal match candidate with additive plain-language explanation (`/api/reports/{id}/matches`).
5. **Student A Submits Claim:** Provides verification answer and serial number evidence.
6. **Moderator Review & Handover Code:** Moderator locks claim (`/api/mod/claims/{id}/open`), verifies evidence, and approves claim. Single-use 8-character Crockford Base32 code is generated and displayed strictly to Student A.
7. **Desk Handover Verification:** Moderator verifies code and records identity note (`/api/mod/handovers/{claim_id}/verify`), marking item as `returned`.
8. **Operational Analytics:** Moderator checks operational dashboard (`/api/dashboard`), verifying completed lifecycle metrics and updated recovery statistics.

Run the automated test directly:
```bash
docker compose exec -T backend pytest -q tests/test_ac_146_demo_journey.py
```

---

## 5. Research Benchmark Evaluation (AC-109 to AC-123)

Run the reproducible offline benchmark pipeline:
```bash
# 1. Generate seeded benchmark dataset (30% dev / 70% test split)
python -m eval.generator --seed 42

# 2. Run hyperparameter tuning on development split (leakage-guarded)
python -m eval.protocol --split dev

# 3. Execute final evaluation runner on test set
python -m eval.runner
```
Outputs are saved to `eval/benchmark_results.json` and `eval/benchmark_results.csv` and served via `GET /api/admin/evaluation`.

---

## 6. Verification and Quality Gates

Execute full checks across the entire stack:
```bash
# Backend Quality Gates
cd backend
ruff check .
mypy .
alembic check
pytest -v

# Frontend Quality Gates
cd frontend
npm run lint
npx tsc --noEmit
npm test
```

---

## 7. Multi-Device Network Testing (AC-142, AC-143)
* **Date Verified:** 2026-10-20
* **Configuration:** Local network TLS reverse proxy configured at `https://<LAN-IP>:8443` with self-signed certificate and HTTP/2.
* **Test Outcome:** Second device (mobile browser on same Wi-Fi subnet) successfully authenticated, submitted a report, and observed notifications without security warnings when trusting the local CA. Plain HTTP logins from non-localhost clients are strictly refused.

---

## 8. Explicit Limitations (AC-149)

1. **AI Suggestions are Strictly Advisory:** Machine learning match scores are advisory recommendations for human users. No matching algorithm or similarity score ever automatically approves a claim or changes report lifecycle status.
2. **Synthetic Benchmark Evaluation:** The research evaluation dataset is procedurally generated with calibrated spatial and temporal noise; empirical gains do not guarantee identical field recovery rates on uncurated student submissions without pilot validation.
3. **Self-Hosted Email Deliverability:** In development, transactional emails are routed to local Mailpit (`:8025`). In production deployments, SMTP delivery depends on campus IT network firewall configurations, SPF records, and DKIM signing.
4. **Authentication & SSO Scope:** The application enforces allowed campus email domains (`@campus.edu`) and Argon2id session authentication; campus enterprise Single Sign-On (SAML 2.0 / Shibboleth) was out of scope for this build and requires an upstream reverse-proxy bridge.
5. **Data Retention Policies:**
   * Private claim evidence files and photos are permanently purged **14 days** post-handover.
   * Unclaimed reports transition to `expired` after **90 days**.
   * Expired reports and associated image files are permanently unlinked and archived after **180 days**.
