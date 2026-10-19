# DECISIONS.md: Architecture and Design Decisions Log

This log records the core design and architectural decisions made for the Smart Campus Lost-and-Found Network.

| ID | Date | Decision | Alternatives Considered | Rationale |
| --- | --- | --- | --- | --- |
| **D-01** | 2026-10-18 | **AI is advisory:** scores never change a state automatically | Auto-approve high scores | Ownership decisions require human judgment and identity verification; false claims are the primary abuse risk. |
| **D-02** | 2026-10-18 | **Lost reports are private; only found reports are browsable** | Public lost reports | Public lost reports reveal what valuable items people have lost and who lost them; browsing found items helps owners find belongings safely. |
| **D-03** | 2026-10-18 | **Found reports and photos are moderated before publication (configurable)** | Publish immediately | Stops spam, personal identification data in photos, and listings of stolen or sensitive items. |
| **D-04** | 2026-10-18 | **Missing signals are excluded and weights renormalized** | Treat missing signals as zero | A report missing a photo is not evidence of a mismatch; renormalizing preserves fair scoring. |
| **D-05** | 2026-10-18 | **Asymmetric time decay score** | Symmetric time decay | Items cannot be found before they were lost (apart from reporting imprecision); penalize "found before lost" more steeply. |
| **D-06** | 2026-10-18 | **Location tree with adjacency table** | GPS distance | Works indoors, tolerates approximate human reporting, requires no intrusive precise location tracking. |
| **D-07** | 2026-10-18 | **Background embedding workers; models baked into images** | In-request computation; runtime model downloads | Keeps API response fast (<300ms p95), supports offline operation, pins exact model weights. |
| **D-08** | 2026-10-18 | **PostgreSQL with pgvector and HNSW index** | Separate vector database (e.g. Pinecone/Milvus) | Single database to run, back up, and maintain transactional consistency; measured recall against exact search. |
| **D-09** | 2026-10-18 | **8-character codes (40 bits, Crockford-like Base32), HMAC-stored, 5 attempts, 48h expiry** | 6-digit numeric codes | Negligible brute-force collision probability (~4.5 × 10⁻¹²) for identical friction at the desk. |
| **D-10** | 2026-10-18 | **Server-side revocable sessions with CSRF tokens** | Stateless JWTs | Instant revocation on logout or account deletion; protection against XSS token theft. |
| **D-11** | 2026-10-18 | **Synthetic benchmark with consented real-photo and human-text subsets** | Live student user data | Respects student privacy and consent while enabling reproducible scientific benchmarking. |
| **D-12** | 2026-10-18 | **Development-only tuning with frozen configuration** | Tuning on all data | Prevents data leakage; guarantees test set reporting is honest and unbiased. |
| **D-13** | 2026-10-18 | **Bootstrap confidence intervals and paired bootstrap testing** | Single-point metrics | Quantifies whether performance differences over baselines are statistically significant. |
| **D-14** | 2026-10-18 | **Append-only audit table enforced by DB trigger/privileges** | Application-level logging | Audit rows must be immutable and tamper-evident even if application logic is compromised. |
| **D-15** | 2026-10-18 | **Transactional outbox pattern for jobs and notifications** | External message broker (RabbitMQ/Kafka) | Guarantees atomic consistency with database state changes using `FOR UPDATE SKIP LOCKED`. |
| **D-16** | 2026-10-18 | **Credentials over TLS beyond localhost** | Plain HTTP on intranet | Prevents credential and session sniffing over local campus Wi-Fi networks. |
| **D-17** | 2026-10-18 | **Email-only identity with campus domain restriction** | Collecting phone numbers or student IDs | Adheres to strict data minimization principles. |
