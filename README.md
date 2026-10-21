# Smart Campus Lost-and-Found Network

An accessible, privacy-preserving campus lost-and-found system featuring explainable multimodal retrieval, evidence-based claim verification, single-use expiring handover desk codes, immutable audit logging, and empirical benchmark evaluation.

---

## 1. Overview
The platform combines a reliable campus operational workflow with a controlled retrieval research framework:
* **Product:** Privacy-safe found item listings, hierarchical campus location tree, safe image pipeline (magic byte verification, pixel guards, EXIF metadata stripping, 64-bit dHash duplicate detection), moderator claim locks, single-use 8-character handover codes (HMAC-SHA256, 5-attempt lock, 48-hour expiry), transactional outbox notifications, and retention rules.
* **Research:** A seeded synthetic benchmark (300 items + 100 unclaimed, 70% held out) comparing BM25, text embeddings (`all-MiniLM-L6-v2`), a hand-weighted hybrid and learned fusion, with bootstrap confidence intervals, a pre-registered hypothesis (H1) and pgvector latency. Image retrieval is **not** evaluated: no photo subset has been collected (see section 5).

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
   cp .env.example .env   # then set SECRET_KEY; optionally SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD
   ```
2. **Build and Launch Services** (the first build downloads the pinned model weights, about 700 MB, and verifies their checksums; migrations run automatically when the backend starts):
   ```bash
   docker compose up -d --build
   ```
3. **Seed Campus Tree, Users, and Demo Reports (AC-145):**
   ```bash
   docker compose exec -T backend python -m app.seed
   ```
4. **Access Endpoints:**
   * **Web Application:** `http://localhost:8080`
   * **Backend API Documentation:** `http://localhost:8000/docs`
   * **Mailpit (In-Development Mail Catcher):** `http://localhost:8025` (verification links and notification emails arrive here)

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

Run inside the backend image (the models are baked in, so this works offline):
```bash
# 1. Tune on the development split only, then freeze and hash the configuration
docker compose exec -T backend python -m eval.runner tune

# 2. Write the hypotheses (eval/HYPOTHESES.md) and commit them with the frozen config

# 3. Evaluate the test split once (refuses to run again for the same frozen config)
docker compose exec -T backend python -m eval.runner final

# 4. Check reproducibility: re-runs and compares with the saved numbers
docker compose exec -T backend python -m eval.runner final --reproduce
```
Results: `eval/results/benchmark_results.json` and `.csv`, shown on the admin **Evaluation** page.

### Results (seed 42, test split: 210 queries × 310 candidates, frozen config `b3cd1021…`)

| System | MRR | 95% CI | Recall@1 | Recall@10 |
| --- | --- | --- | --- | --- |
| A: BM25 keyword | 0.120 | [0.090, 0.153] | 0.062 | 0.233 |
| B: text embedding (MiniLM) | 0.342 | [0.293, 0.389] | 0.195 | 0.657 |
| D: hand-weighted hybrid (text 0.40, location 0.30, time 0.30) | 0.959 | [0.938, 0.979] | 0.933 | 0.995 |
| E: learned fusion (logistic regression) | 0.982 | [0.966, 0.994] | 0.971 | 1.000 |
| C: image similarity | not evaluated — no photos collected | | | |

**H1 (pre-registered): supported.** MRR(D) − MRR(B) = 0.618, paired-bootstrap 95% CI [0.568, 0.669].
As stated in `eval/HYPOTHESES.md` before the run, most of this gap is **by construction**: the
generator places location and time with the assumptions the scoring encodes, and spreads items over
60 days while each item is found within hours. Removing time drops the hybrid to 0.739; removing
location to 0.901; removing text to 0.878. The informative semantic result is text-only: MiniLM
roughly triples BM25 (0.342 vs 0.120) when the two sides use different words.

**Robustness:** location one level off for 25/50% of found reports: 0.966 / 0.961 (no meaningful
change); time shifted 24 h for 25/50%: 0.931 / 0.919.

**Latency (pgvector, random 384-d vectors, one machine):** exact top-10 p50 0.41 / 2.8 / 24.6 ms
at 1k / 10k / 100k; HNSW p50 0.39 / 1.0 / 3.7 ms. HNSW recall@10 against exact search was
0.99 / 0.30 / 0.06 — random isotropic vectors are a worst case for HNSW at the default
`ef_search = 40`, so the speed-up came with a large loss of recall here. (The matching service
currently scores candidates directly and does not depend on HNSW recall.)

**Not evaluated / limitations:** no real-photo subset and no human-written subset have been
collected (`eval/DATA_CARD.md`); results come from a synthetic benchmark and say nothing about
real-world recovery rates.

---

## 6. Verification and Quality Gates

```bash
# Backend (inside the backend image or a Python 3.12 venv with PostgreSQL + pgvector)
cd backend
ruff check .
mypy .
alembic upgrade head && alembic check
pytest -q              # fast suite, stand-in embeddings
pytest -q -m slow      # real models (inside the backend image)

# Frontend
cd frontend
npm run gen:api        # regenerate API types from src/api/openapi.json (CI checks for drift)
npm run lint
npx tsc --noEmit
npm run build
```

Browser end-to-end tests live in `e2e/` (see `e2e/README.md`) and run with `sh e2e/run.sh` against a
freshly seeded stack: the full demo journey (AC-146) with an axe scan of eight pages (AC-126) and
360 px layout checks (AC-127), and a keyboard-only report-and-claim flow that also checks every
focused element has a visible focus indicator (AC-125). Both passed on 2026-10-21. They are not in
CI yet, because CI would have to build the model-carrying backend image.

---

## 7. Using it from a phone: HTTPS on the local network (AC-142, AC-143)

All published ports are bound to `127.0.0.1`, so the database, API, mail catcher and the
plain-HTTP site are reachable only from this machine. Other devices use HTTPS on port 8443:

```bash
# once: create a local certificate authority and a certificate for this machine's LAN address
mkcert -install
mkdir -p certs
mkcert -cert-file certs/campus.pem -key-file certs/campus-key.pem <LAN-IP> localhost

# start with the HTTPS listener
APP_BASE_URL=https://<LAN-IP>:8443 docker compose -f docker-compose.yml -f docker-compose.lan.yml up -d --build
```

On the phone, install and trust mkcert's root certificate (`mkcert -CAROOT` shows where
`rootCA.pem` is), then open `https://<LAN-IP>:8443`. `certs/` is git-ignored; never commit keys.

How the TLS rule works (SEC7, D-21): the backend accepts a login only over TLS or from this
machine, and believes `X-Forwarded-Proto` / `X-Client-Network` only from the configured proxy
(`TRUSTED_PROXIES`, default `frontend`). nginx sets both headers itself on every request.

Verified on 2026-10-21 against the Compose stack with a test certificate: login over HTTPS
returns a `Secure` session cookie; TLS 1.1 is refused and TLS 1.2 / 1.3 accepted; HSTS is sent
over HTTPS only; a container talking to the backend directly with forged headers gets 403.
**Still to do by hand (AC-143):** sign in, report an item and see a notification from a real
second device, then record the date, device and result here.

---

## 8. Explicit Limitations (AC-149)

1. **AI Suggestions are Strictly Advisory:** Machine learning match scores are advisory recommendations for human users. No matching algorithm or similarity score ever automatically approves a claim or changes report lifecycle status.
2. **Synthetic Benchmark Evaluation:** The research evaluation dataset is procedurally generated with calibrated spatial and temporal noise; empirical gains do not guarantee identical field recovery rates on uncurated student submissions without pilot validation.
3. **Self-Hosted Email Deliverability:** In development, transactional emails are routed to local Mailpit (`:8025`). In production deployments, SMTP delivery depends on campus IT network firewall configurations, SPF records, and DKIM signing.
4. **Authentication & SSO Scope:** The application enforces allowed campus email domains (`@campus.edu`) and Argon2id session authentication; campus enterprise Single Sign-On (SAML 2.0 / Shibboleth) was out of scope for this build and requires an upstream reverse-proxy bridge.
5. **Data Retention Policies** (configurable in `.env`; applied hourly by the worker):
   * Found items still open after **90 days** become `unclaimed_expired`.
   * Photos are deleted **30 days** after their report closes, and claim evidence **30 days** after the claim closes.
   * Audit rows older than **365 days** can be purged only by the retention job's privileged role.
6. **Image matching is unvalidated:** the photo signal (CLIP) is computed and used, but it has not been evaluated on real photos, and its raw cosine for a text-to-photo comparison is low (about 0.2–0.3 even for a true match), which can rank a found item with a photo below one without.
