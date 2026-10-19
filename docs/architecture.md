# System Architecture: Smart Campus Lost-and-Found Network

## 1. Overview
The Smart Campus Lost-and-Found Network is built as a **modular monolith** with dedicated background workers, designed to ensure privacy, transactional consistency, explainable matching, and auditability.

```
+---------------------------------------------------------------------------------+
|                                 Client Devices                                  |
|            (Browser, Mobile Web - Responsive, A11y, 360px+ viewport)            |
+---------------------------------------+-----------------------------------------+
                                        |
                                        v
                 +-----------------------------------------------+
                 |             Reverse Proxy (Nginx)             |
                 |      TLS termination, static files, /api      |
                 +----------------------+------------------------+
                                        |
                 +----------------------+------------------------+
                 |                                               |
                 v                                               v
+---------------------------------+             +---------------------------------+
|       Frontend Container        |             |        Backend API (FastAPI)    |
|   React + TypeScript SPA        |             | - Thin routers                  |
|   Tailored CSS design system    |             | - Strict Pydantic (extra=forbid)|
|   OpenAPI generated client      |             | - Session & CSRF auth           |
+---------------------------------+             | - Default-deny serializers      |
                                                +----------------+----------------+
                                                                 |
                                                +----------------+----------------+
                                                |                                 |
                                                v                                 v
                                 +-----------------------------+   +-----------------------------+
                                 |        Domain Layer         |   |      Services / Outbox      |
                                 | - Pure functions only       |   | - Atomic DB transactions    |
                                 | - No DB/Framework/Clock     |   | - Enqueue jobs/notifs       |
                                 | - Scoring, logic, PII check |   | - Ownership enforcement     |
                                 +-----------------------------+   +--------------+--------------+
                                                                                  |
                                 +------------------------------------------------+
                                 |
                                 v
+---------------------------------------------------------------------------------+
|                       PostgreSQL Database with pgvector                         |
|  - Relational tables (Users, Reports, Claims, Handovers, Adjacency)             |
|  - Vector columns (pgvector HNSW cosine index for 384d text, 512d image)       |
|  - Transactional Job Queue (`jobs`) & Notification Outbox (`notifications`)     |
|  - Immutable append-only Audit Log (`audit_log`) with trigger protection        |
+---------------------------------------+-----------------------------------------+
                                        ^
                                        | (FOR UPDATE SKIP LOCKED)
                                        v
+---------------------------------------------------------------------------------+
|                           Background Worker Process                             |
|  - Embeddings computation (Sentence-Transformers & CLIP ViT-B/32 offline)       |
|  - Candidate retrieval and scoring updates                                      |
|  - Notification dispatch (SMTP / Mailpit) with exponential backoff              |
|  - Automated retention & cleanup cron jobs                                      |
+---------------------------------------------------------------------------------+
```

## 2. Key Architectural Guarantees
1. **Layering & Pure Domain Core:** Business rules (location tree distance, time decay, hybrid weighting, explanations, code hashing, PII detection, evaluation metrics) reside in `app/domain` as pure functions with zero framework dependencies.
2. **Transactional Outbox:** State changes (e.g. claim approval, report creation) write notifications and jobs in the *exact same database transaction*, preventing orphaned states or ghost notifications.
3. **Worker Concurrency:** Workers poll `jobs` with `SELECT ... FOR UPDATE SKIP LOCKED` to enable safe horizontal scaling without distributed locks.
4. **Default-Deny Serializers:** Normal users only ever see explicitly whitelisted fields. Private details, verification answers, and hashes never cross the API boundary.
5. **AI is Advisory:** Matching algorithms produce ranked candidate suggestions with explanations. No code path permits an automated status transition based on matching scores.
