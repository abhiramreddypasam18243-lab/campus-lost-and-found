# Test Plan: Acceptance Criteria Traceability Matrix (AC-01 to AC-149)

This test plan defines the complete traceability matrix mapping every single Acceptance Criterion (**AC-01** through **AC-149**) from [spec.md](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/spec.md) to its automated test implementation, test suite file, or verification method.

---

## 1. Authentication, Sessions & Security (AC-01 to AC-16)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-01** | Allowed campus email domain registration, rejects non-campus domains | Automated Test | [`backend/tests/test_ac_01_registration.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_01_registration.py) |
| **AC-02** | Email verification token delivery via mailcatcher & single-use expiry | Automated Test | [`backend/tests/test_ac_02_email_verification.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_02_email_verification.py) |
| **AC-03** | Password complexity rules (min 8 chars, uppercase, lowercase, digit, symbol) | Automated Test | [`backend/tests/test_ac_03_password_rules.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_03_password_rules.py) |
| **AC-04** | Argon2id password hashing, session tokens, login rate limiting (5 attempts/min) | Automated Test | [`backend/tests/test_ac_04_session_and_rate_limiting.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_04_session_and_rate_limiting.py) |
| **AC-05** | Logout invalidates server-side session token and clears cookie | Automated Test | [`backend/tests/test_ac_05_logout.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_05_logout.py) |
| **AC-06** | Double-submit CSRF cookie & header validation on state-modifying requests | Automated Test | [`backend/tests/test_ac_06_csrf.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_06_csrf.py) |
| **AC-07** | TLS enforcement: non-localhost HTTP requests refused | Automated Test | [`backend/tests/test_ac_07_tls_requirement.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_07_tls_requirement.py) |
| **AC-08** | Role permission matrix (`user`, `moderator`, `admin`) default-deny | Automated Test | [`backend/tests/test_ac_08_role_matrix.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_08_role_matrix.py) |
| **AC-09** | Ownership checks: non-staff cannot view or edit foreign private reports | Automated Test | [`backend/tests/test_ac_09_ownership.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_09_ownership.py) |
| **AC-10** | Strict Pydantic input schemas (`extra='forbid'`) reject unknown fields | Automated Test | [`backend/tests/test_ac_10_unknown_fields.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_10_unknown_fields.py) |
| **AC-11** | Parameterized SQL queries prevent SQL injection | Automated Test | [`backend/tests/test_ac_11_12_sql_xss.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_11_12_sql_xss.py) |
| **AC-12** | Output encoding & React JSX sanitization prevent XSS | Automated Test | [`backend/tests/test_ac_11_12_sql_xss.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_11_12_sql_xss.py) |
| **AC-13** | Security headers: CSP, `X-Content-Type-Options: nosniff`, `Referrer-Policy` | Automated Test | [`backend/tests/test_ac_13_14_15_security.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_13_14_15_security.py) |
| **AC-14** | Foreign/non-existent IDs return uniform 404 anti-enumeration responses | Automated Test | [`backend/tests/test_ac_13_14_15_security.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_13_14_15_security.py) |
| **AC-15** | Environment variable configuration: zero committed secrets | Automated Test | [`backend/tests/test_ac_13_14_15_security.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_13_14_15_security.py) |
| **AC-16** | Unauthenticated and unauthorized requests rejected | Automated Test | [`backend/tests/test_ac_08_role_matrix.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_08_role_matrix.py) |

---

## 2. Campus Location Hierarchy & Scoring (AC-17 to AC-20)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-17** | Hierarchical campus location tree CRUD with circular-reference checks | Automated Test | [`backend/tests/test_ac_17_location_tree.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_17_location_tree.py) |
| **AC-18** | Location distance & tree scoring: identical node=1.0, sibling=0.8, parent=0.6 | Automated Test | [`backend/tests/test_ac_18_location_scoring.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_18_location_scoring.py) |
| **AC-19** | Building adjacency table: adjacent buildings receive calibrated proximity score 0.5 | Automated Test | [`backend/tests/test_ac_19_adjacency.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_19_adjacency.py) |
| **AC-20** | Approximate locations tolerated with gracefully degraded location scores | Automated Test | [`backend/tests/test_ac_20_approximate_locations.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_20_approximate_locations.py) |

---

## 3. Reports, Lifecycle & PII Scanner (AC-21 to AC-29)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-21** | Report lost item: title, description, category, date, precision, location | Automated Test | [`backend/tests/test_ac_21_22_report_creation.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_21_22_report_creation.py) |
| **AC-22** | Report found item: verification prompts and private details start in `pending_review` | Automated Test | [`backend/tests/test_ac_21_22_report_creation.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_21_22_report_creation.py) |
| **AC-23** | Time precision windows (exact, hour, morning, afternoon, evening, day, range) | Automated Test | [`backend/tests/test_ac_23_time_windows.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_23_time_windows.py) |
| **AC-24** | 12 fixed categories and sensitive-category classification | Automated Test | [`backend/tests/test_ac_24_categories.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_24_categories.py) |
| **AC-25** | Report status transitions (`open`, `claimed`, `returned`, `expired`, `removed`) | Automated Test | [`backend/tests/test_ac_25_26_27_lifecycle.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_25_26_27_lifecycle.py) |
| **AC-26** | Validated state machine rejects illegal lifecycle transitions | Automated Test | [`backend/tests/test_ac_25_26_27_lifecycle.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_25_26_27_lifecycle.py) |
| **AC-27** | Outbox pattern: lifecycle transitions emit audit logs and notifications | Automated Test | [`backend/tests/test_ac_25_26_27_lifecycle.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_25_26_27_lifecycle.py) |
| **AC-28** | PII scanner detects phone numbers, email addresses, credit cards, student IDs | Automated Test | [`backend/tests/test_ac_28_29_pii_scanner.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_28_29_pii_scanner.py) |
| **AC-29** | PII detection raises confirmation warning preventing accidental leak | Automated Test | [`backend/tests/test_ac_28_29_pii_scanner.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_28_29_pii_scanner.py) |

---

## 4. Photo Pipeline & Duplicate Detection (AC-30 to AC-37)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-30** | Maximum 3 photos per report/claim | Automated Test | [`backend/tests/test_ac_30_to_37_photo_pipeline.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_30_to_37_photo_pipeline.py) |
| **AC-31** | Content-based MIME inspection (magic bytes), rejects spoofed extensions | Automated Test | [`backend/tests/test_ac_30_to_37_photo_pipeline.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_30_to_37_photo_pipeline.py) |
| **AC-32** | Pixel dimension limits guard against image decompression bombs | Automated Test | [`backend/tests/test_ac_30_to_37_photo_pipeline.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_30_to_37_photo_pipeline.py) |
| **AC-33** | EXIF metadata stripping (removes GPS coordinates and camera serial numbers) | Automated Test | [`backend/tests/test_ac_30_to_37_photo_pipeline.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_30_to_37_photo_pipeline.py) |
| **AC-34** | Image re-encoding into standard web formats (JPEG/WebP) and thumbnail generation | Automated Test | [`backend/tests/test_ac_30_to_37_photo_pipeline.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_30_to_37_photo_pipeline.py) |
| **AC-35** | Images stored under unguessable random UUID keys outside webroot | Automated Test | [`backend/tests/test_ac_30_to_37_photo_pipeline.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_30_to_37_photo_pipeline.py) |
| **AC-36** | Authenticated image route validates viewer permissions before streaming bytes | Automated Test | [`backend/tests/test_ac_30_to_37_photo_pipeline.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_30_to_37_photo_pipeline.py) |
| **AC-37** | Perceptual dHash computation flags duplicate/near-identical photos (Hamming <= 10) | Automated Test | [`backend/tests/test_ac_30_to_37_photo_pipeline.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_30_to_37_photo_pipeline.py) |

---

## 5. Browsing, Search & Privacy Whitelisting (AC-38 to AC-44)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-38** | Public listing shows only open found items; lost items are hidden | Automated Test | [`backend/tests/test_ac_38_found_listing.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_38_found_listing.py) |
| **AC-39** | Default-deny whitelist: private details, verification prompts, and reporter IDs stripped | Automated Test | [`backend/tests/test_ac_39_default_deny_whitelist.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_39_default_deny_whitelist.py) |
| **AC-40** | Lost reports accessible only to creator and moderators (anti-enumeration 404) | Automated Test | [`backend/tests/test_ac_40_lost_reports_privacy.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_40_lost_reports_privacy.py) |
| **AC-41** | Full-text search and filters (category, building descendants, date ranges) | Automated Test | [`backend/tests/test_ac_41_search_and_filters.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_41_search_and_filters.py) |
| **AC-42** | Staff view includes full unmasked details and audit history | Automated Test | [`backend/tests/test_ac_42_staff_full_details.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_42_staff_full_details.py) |
| **AC-43** | Browse endpoint rate limited to 120 requests/minute per user | Automated Test | [`backend/tests/test_ac_43_browse_rate_limiting.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_43_browse_rate_limiting.py) |
| **AC-44** | Authentication required to access browse & search; unauthenticated calls rejected | Automated Test | [`backend/tests/test_ac_44_auth_and_uuid.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_44_auth_and_uuid.py) |

---

## 6. Background Jobs & Worker Architecture (AC-45 to AC-50)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-45** | Report creation enqueues embedding job in `jobs` table atomically | Automated Test | [`backend/tests/test_ac_45_report_enqueues_embedding.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_45_report_enqueues_embedding.py) |
| **AC-46** | Worker concurrency: `FOR UPDATE SKIP LOCKED` prevents race conditions | Automated Test | [`backend/tests/test_ac_46_concurrent_workers_skip_locked.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_46_concurrent_workers_skip_locked.py) |
| **AC-47** | Job retries with exponential backoff; dead-letter queue inspectable by admins | Automated Test | [`backend/tests/test_ac_47_job_retry_backoff_and_admin.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_47_job_retry_backoff_and_admin.py) |
| **AC-48** | Text embeddings (384d) and image embeddings (512d) stored in pgvector columns | Automated Test | [`backend/tests/test_ac_48_49_50_embeddings_and_model_registry.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_48_49_50_embeddings_and_model_registry.py) |
| **AC-49** | Pinned Model Registry tracks model name, version, dimension, active status | Automated Test | [`backend/tests/test_ac_48_49_50_embeddings_and_model_registry.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_48_49_50_embeddings_and_model_registry.py) |
| **AC-50** | Fast test suite uses deterministic mock embeddings without network egress | Automated Test | [`backend/tests/test_ac_48_49_50_embeddings_and_model_registry.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_48_49_50_embeddings_and_model_registry.py) |

---

## 7. Multimodal Matching & Explainable Scoring (AC-51 to AC-67)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-51** | Text cosine similarity bounded in [0, 1] | Automated Test | [`backend/tests/test_ac_51_to_55_domain_scores.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_51_to_55_domain_scores.py) |
| **AC-52** | Visual cosine similarity (CLIP embeddings) bounded in [0, 1] | Automated Test | [`backend/tests/test_ac_51_to_55_domain_scores.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_51_to_55_domain_scores.py) |
| **AC-53** | Hybrid score calculation: $0.45 S_{text} + 0.25 S_{img} + 0.15 S_{loc} + 0.15 S_{time}$ | Automated Test | [`backend/tests/test_ac_51_to_55_domain_scores.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_51_to_55_domain_scores.py) |
| **AC-54** | Missing signal weight redistribution maintains total weight = 1.0 | Automated Test | [`backend/tests/test_ac_51_to_55_domain_scores.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_51_to_55_domain_scores.py) |
| **AC-55** | Confidence bin assignment: High (>=0.75), Medium ([0.50, 0.75)), Low (<0.50) | Automated Test | [`backend/tests/test_ac_51_to_55_domain_scores.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_51_to_55_domain_scores.py) |
| **AC-56** | Candidate filtering: hard constraints (sensitive category match, status open) | Automated Test | [`backend/tests/test_ac_56_to_60_candidates_and_explanations.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_56_to_60_candidates_and_explanations.py) |
| **AC-57** | Top-K candidates retrieval (default top 10) | Automated Test | [`backend/tests/test_ac_56_to_60_candidates_and_explanations.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_56_to_60_candidates_and_explanations.py) |
| **AC-58** | `GET /api/reports/{id}/matches`: Owner-only access, foreign access returns 404 | Automated Test | [`backend/tests/test_ac_58_to_65_matching_api_and_triggers.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_58_to_65_matching_api_and_triggers.py) |
| **AC-59** | Plain-language additive explanations describe individual signal contributions | Automated Test | [`backend/tests/test_ac_56_to_60_candidates_and_explanations.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_56_to_60_candidates_and_explanations.py) |
| **AC-60** | Privacy canary in match suggestions: private details never leaked | Automated Test | [`backend/tests/test_ac_58_to_65_matching_api_and_triggers.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_58_to_65_matching_api_and_triggers.py) |
| **AC-61** | Match feedback endpoint: user can confirm or dismiss match suggestions | Automated Test | [`backend/tests/test_ac_58_to_65_matching_api_and_triggers.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_58_to_65_matching_api_and_triggers.py) |
| **AC-62** | AI suggestions are strictly advisory: never automatically transition report state | Automated Test | [`backend/tests/test_ac_58_to_65_matching_api_and_triggers.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_58_to_65_matching_api_and_triggers.py) |
| **AC-63** | Triggering matching on new report creation | Automated Test | [`backend/tests/test_ac_58_to_65_matching_api_and_triggers.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_58_to_65_matching_api_and_triggers.py) |
| **AC-64** | Re-scoring triggered upon report description/location updates | Automated Test | [`backend/tests/test_ac_58_to_65_matching_api_and_triggers.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_58_to_65_matching_api_and_triggers.py) |
| **AC-65** | Match notifications sent only when candidate score exceeds high threshold | Automated Test | [`backend/tests/test_ac_58_to_65_matching_api_and_triggers.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_58_to_65_matching_api_and_triggers.py) |
| **AC-66** | Retrieval benchmark integration test runs on synthetic corpus | Automated Test | [`backend/tests/test_ac_66_67_retrieval_benchmark.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_66_67_retrieval_benchmark.py) |
| **AC-67** | Evaluation outputs reproducible metric values across runs | Automated Test | [`backend/tests/test_ac_66_67_retrieval_benchmark.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_66_67_retrieval_benchmark.py) |

---

## 8. Notifications & Privacy Canary (AC-68 to AC-74)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-68** | Transactional outbox table (`notifications`) enqueues alerts atomically | Automated Test | [`backend/tests/test_ac_68_69_70_notification_outbox.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_68_69_70_notification_outbox.py) |
| **AC-69** | Notification dispatcher delivers emails via SMTP/Mailpit | Automated Test | [`backend/tests/test_ac_68_69_70_notification_outbox.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_68_69_70_notification_outbox.py) |
| **AC-70** | Dispatcher retries failed sends with exponential backoff | Automated Test | [`backend/tests/test_ac_68_69_70_notification_outbox.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_68_69_70_notification_outbox.py) |
| **AC-71** | Canary strings verify zero private evidence or passwords leak into notifications | Automated Test | [`backend/tests/test_ac_71_notification_privacy_canary.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_71_notification_privacy_canary.py) |
| **AC-72** | User email preferences (opt-in/opt-out for match alerts) | Automated Test | [`backend/tests/test_ac_72_73_email_preferences_and_rate_cap.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_72_73_email_preferences_and_rate_cap.py) |
| **AC-73** | Notification frequency caps prevent email flooding (max 5 emails/hour per user) | Automated Test | [`backend/tests/test_ac_72_73_email_preferences_and_rate_cap.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_72_73_email_preferences_and_rate_cap.py) |
| **AC-74** | In-app notification feed API (`GET /api/notifications`) with read markers | Automated Test | [`backend/tests/test_ac_74_in_app_notifications_api.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_74_in_app_notifications_api.py) |

---

## 9. Claims, Moderation & Anti-Abuse (AC-75 to AC-85)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-75** | Submit claim with evidence text, prompt answers, and up to 3 private photos | Automated Test | [`backend/tests/test_ac_75_77_claim_creation_and_privacy.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_75_77_claim_creation_and_privacy.py) |
| **AC-76** | Claim state machine (`submitted`, `under_review`, `approved`, `rejected`, `withdrawn`) | Automated Test | [`backend/tests/test_ac_76_claim_lifecycle.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_76_claim_lifecycle.py) |
| **AC-77** | Claim evidence visible only to claimant and staff (foreign calls return 404) | Automated Test | [`backend/tests/test_ac_75_77_claim_creation_and_privacy.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_75_77_claim_creation_and_privacy.py) |
| **AC-78** | Moderator queue endpoint with lock acquisition (`POST /api/mod/claims/{id}/open`) | Automated Test | [`backend/tests/test_ac_78_80_81_moderation_queue_locks.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_78_80_81_moderation_queue_locks.py) |
| **AC-79** | Moderator decision recorded with decision note in audit log | Automated Test | [`backend/tests/test_ac_79_82_83_decisions_info_withdraw.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_79_82_83_decisions_info_withdraw.py) |
| **AC-80** | Review locks expire automatically after 15 minutes | Automated Test | [`backend/tests/test_ac_78_80_81_moderation_queue_locks.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_78_80_81_moderation_queue_locks.py) |
| **AC-81** | Lock contention returns 409 Conflict with holding moderator info | Automated Test | [`backend/tests/test_ac_78_80_81_moderation_queue_locks.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_78_80_81_moderation_queue_locks.py) |
| **AC-82** | Request additional information transitions claim to `more_info_needed` | Automated Test | [`backend/tests/test_ac_79_82_83_decisions_info_withdraw.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_79_82_83_decisions_info_withdraw.py) |
| **AC-83** | Claimant can withdraw their pending claim | Automated Test | [`backend/tests/test_ac_79_82_83_decisions_info_withdraw.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_79_82_83_decisions_info_withdraw.py) |
| **AC-84** | Rate limiter caps users to at most 3 active claims concurrently | Automated Test | [`backend/tests/test_ac_84_85_abuse_and_escalation.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_84_85_abuse_and_escalation.py) |
| **AC-85** | Repeated claim rejections trigger abuse escalation flag in queue | Automated Test | [`backend/tests/test_ac_84_85_abuse_and_escalation.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_84_85_abuse_and_escalation.py) |

---

## 10. Cryptographic Handover Codes & Verification (AC-86 to AC-96)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-86** | Handover code generated with `secrets.choice` using Crockford Base32 alphabet | Automated Test | [`backend/tests/test_ac_86_to_89_handover_domain.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_86_to_89_handover_domain.py) |
| **AC-87** | Plaintext code never stored: HMAC-SHA256 hash stored in DB | Automated Test | [`backend/tests/test_ac_86_to_89_handover_domain.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_86_to_89_handover_domain.py) |
| **AC-88** | Normalization handles lowercase and replaces confusable characters (O->0, I/L->1) | Automated Test | [`backend/tests/test_ac_86_to_89_handover_domain.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_86_to_89_handover_domain.py) |
| **AC-89** | Verification uses constant-time `hmac.compare_digest` | Automated Test | [`backend/tests/test_ac_86_to_89_handover_domain.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_86_to_89_handover_domain.py) |
| **AC-90** | Desk verification completes handover and marks item `returned` | Automated Test | [`backend/tests/test_ac_90_to_96_handover_flow.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_90_to_96_handover_flow.py) |
| **AC-91** | Re-verifying a completed handover returns 409 Conflict (`code_used`) | Automated Test | [`backend/tests/test_ac_90_to_96_handover_flow.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_90_to_96_handover_flow.py) |
| **AC-92** | Maximum 3 failed attempts before code is permanently locked | Automated Test | [`backend/tests/test_ac_90_to_96_handover_flow.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_90_to_96_handover_flow.py) |
| **AC-93** | Code expires after 48 hours; expired verification attempts return 410 Gone | Automated Test | [`backend/tests/test_ac_90_to_96_handover_flow.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_90_to_96_handover_flow.py) |
| **AC-94** | Moderator can reissue a fresh handover code invalidating previous hash | Automated Test | [`backend/tests/test_ac_90_to_96_handover_flow.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_90_to_96_handover_flow.py) |
| **AC-95** | Desk verification requires non-empty identity note recording staff ID check | Automated Test | [`backend/tests/test_ac_90_to_96_handover_flow.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_90_to_96_handover_flow.py) |
| **AC-96** | Handover code returned strictly to approved claimant, never logged | Automated Test | [`backend/tests/test_ac_90_to_96_handover_flow.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_90_to_96_handover_flow.py) |

---

## 11. Data Retention & Immutable Audit Log (AC-97 to AC-104)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-97** | PostgreSQL trigger blocks `UPDATE` or `DELETE` on `audit_log` (SQLSTATE 42501) | Automated Test | [`backend/tests/test_ac_97_to_104_retention_and_audit.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_97_to_104_retention_and_audit.py) |
| **AC-98** | Retention cleanup deletes claim evidence files 14 days post-handover | Automated Test | [`backend/tests/test_ac_97_to_104_retention_and_audit.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_97_to_104_retention_and_audit.py) |
| **AC-99** | Unclaimed reports transition to `expired` after 90 days | Automated Test | [`backend/tests/test_ac_97_to_104_retention_and_audit.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_97_to_104_retention_and_audit.py) |
| **AC-100** | Expired reports archived and images removed after 180 days | Automated Test | [`backend/tests/test_ac_97_to_104_retention_and_audit.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_97_to_104_retention_and_audit.py) |
| **AC-101** | User account deletion cascades sessions, anonymizes audit entries | Automated Test | [`backend/tests/test_ac_97_to_104_retention_and_audit.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_97_to_104_retention_and_audit.py) |
| **AC-102** | Automated retention cron job execution | Automated Test | [`backend/tests/test_ac_97_to_104_retention_and_audit.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_97_to_104_retention_and_audit.py) |
| **AC-103** | Retention operations record execution entries in `audit_log` | Automated Test | [`backend/tests/test_ac_97_to_104_retention_and_audit.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_97_to_104_retention_and_audit.py) |
| **AC-104** | Physical disk files unlinked when image records are pruned | Automated Test | [`backend/tests/test_ac_97_to_104_retention_and_audit.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_97_to_104_retention_and_audit.py) |

---

## 12. Operational Analytics Dashboard (AC-105 to AC-108)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-105** | Domain metrics: recovery rate (0.667), unclaimed rate (0.2), median recovery hours | Automated Test | [`backend/tests/test_ac_105_to_108_analytics.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_105_to_108_analytics.py) |
| **AC-106** | Dashboard restricted to moderators/admins; non-staff receives 404 anti-enumeration | Automated Test | [`backend/tests/test_ac_105_to_108_analytics.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_105_to_108_analytics.py) |
| **AC-107** | Query window aggregation across daily, weekly, monthly time buckets | Automated Test | [`backend/tests/test_ac_105_to_108_analytics.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_105_to_108_analytics.py) |
| **AC-108** | Synthetic demonstration banner clearly displayed on dashboard | Automated Test | [`backend/tests/test_ac_105_to_108_analytics.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_105_to_108_analytics.py) |

---

## 13. Research Evaluation Framework (AC-109 to AC-123)

Descriptions follow spec section 15. Status as of 2026-10-21.

| AC ID | Requirement (spec) | Status | Verified by |
| :--- | :--- | :--- | :--- |
| **AC-109** | Deterministic generator: 300 true items + 100 background found reports | Pass | `backend/tests/test_ac_109_to_123_evaluation.py` |
| **AC-110** | Stratified 30/70 split, no overlap, test hash recorded | Pass | `backend/tests/test_ac_109_to_123_evaluation.py` |
| **AC-111** | Tuning code cannot read test labels (by split name and by item label) | Pass | `backend/tests/test_ac_109_to_123_evaluation.py` |
| **AC-112** | Metric fixture [1, 3, 2, 10] | Pass | `backend/tests/test_ac_109_to_123_evaluation.py` |
| **AC-113** | BM25 toy corpus | Pass | `backend/tests/test_ac_109_to_123_evaluation.py` |
| **AC-114** | Bootstrap CI deterministic, exact for all-ones, ≥90/100 coverage | Pass | `backend/tests/test_ac_109_to_123_evaluation.py` |
| **AC-115** | Paired bootstrap A=[1,1,1,1], B=[2,2,2,2] | Pass | `backend/tests/test_ac_109_to_123_evaluation.py` |
| **AC-116** | Harness evaluates BM25, text, image, hybrid, learned fusion + ablations; records models, weights, seed, dataset hash, commit, hardware | **Partial** — image (C) not evaluated: no photos exist | `backend/tests/test_ac_109_to_123_evaluation.py`; `eval/results/benchmark_results.json` |
| **AC-117** | Weights tuned on dev (0.05 grid, by dev MRR), fusion trained on dev, config frozen and hashed before the test run | Pass | `backend/tests/test_ac_109_to_123_evaluation.py`; commit `291c2b4` (config + hypotheses before results) |
| **AC-118** | Test run once from the frozen config; re-run reproduces identical numbers; JSON + CSV with CIs | Pass | `python -m eval.runner final --reproduce` → identical; second `final` refused |
| **AC-119** | Ablations: remove each signal; missing photos 0–100%; location and time noise 0/25/50% | **Partial** — missing-photo sweep not possible without photos | `eval/results/benchmark_results.json` |
| **AC-120** | Latency p50/p95 at 1k/10k/100k, approximate vs exact, hardware recorded | Pass (measured in pgvector) | `eval/latency.py`; results file |
| **AC-121** | Hypotheses written before the test run; outcome reported either way; limits stated; real-photo subset (≥60) reported separately | **Partial** — real-photo subset not collected | `eval/HYPOTHESES.md`; README section 5 |
| **AC-122** | Evaluation data has no faces/personal data, EXIF removed, consent and licences recorded, data card | Pass for the synthetic data (no photos, no contributors); must be redone if photos are collected | `eval/DATA_CARD.md`; `backend/tests/test_ac_109_to_123_evaluation.py` |
| **AC-123** | Admin page shows the latest saved results; never evaluates live data | Pass (endpoint serves saved results only; 404 `no_results` otherwise) | `backend/tests/test_ac_109_to_123_evaluation.py`; admin Evaluation page |

---

## 14. UI, Accessibility & Architecture Gates (AC-124 to AC-137)

UI checks are the browser tests in `e2e/` (Playwright, Chromium), run with `sh e2e/run.sh` against a
freshly seeded Compose stack. Last passed 2026-10-21. Not yet in CI (the stack needs the model image).

| AC ID | Requirement (spec) | Status | Verified by |
| :--- | :--- | :--- | :--- |
| **AC-124** | Loading, empty and error states; form errors linked with `aria-describedby` | Implemented | `frontend/src/app/ui.tsx` (`AsyncView`, field components) |
| **AC-125** | Keyboard-only end-to-end test; visible focus everywhere | Pass (33 focused elements, all with a visible indicator) | `e2e/keyboard.py` |
| **AC-126** | axe scan: no serious or critical violations on main pages | Pass (8 pages) | `e2e/journey.py` (axe-core 4.10.2) |
| **AC-127** | No horizontal scroll at 360 × 740; photo field opens the camera | Pass (5 pages); `capture="environment"` on the photo input | `e2e/journey.py` |
| **AC-128** | Matches show score, bin, text explanation, "not mine", suggestion notice | Implemented and exercised in the recorded run | `frontend/src/app/pages/Reports.tsx` |
| **AC-129** | Handover desk shows only success/failure and attempts left; never the code | Implemented and exercised (wrong code → "4 of 5", correct code → complete; code never on the desk page) | `frontend/src/app/pages/Moderation.tsx` |
| **AC-130** | Moderation queue: pending reports, duplicate-image flags, claims with lock status | Implemented | `frontend/src/app/pages/Moderation.tsx` |
| **AC-131** | Database schema builds from empty via Alembic, downgrades, and reports zero drift | Automated CLI Test | [`backend/tests/test_ac_131_migrations.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_131_migrations.py) |
| **AC-132** | Pure domain layering: zero DB/framework/clock imports in `app.domain` | AST Inspection Test | [`backend/tests/test_ac_131_to_137_quality_and_architecture.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_131_to_137_quality_and_architecture.py) |
| **AC-133** | Frontend API types generated from the OpenAPI document; CI fails if out of date | Pass | `backend/scripts/export_openapi.py`, `npm run gen:api`, two drift steps in `.github/workflows/ci.yml` |
| **AC-134** | Test coverage exceeds 90% across domain & services | Pytest-cov Metric | [`backend/tests/conftest.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/conftest.py) |
| **AC-135** | CI pipeline runs linting, type checks, unit and integration tests | CI Suite | GitHub Actions / Docker Test Suites |
| **AC-136** | Canary test proves zero passwords, session tokens, or emails leak into logs | Automated Test | [`backend/tests/test_ac_131_to_137_quality_and_architecture.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_131_to_137_quality_and_architecture.py) |
| **AC-137** | Latency benchmark gates: browse <300ms p95, dashboard <500ms | Automated Benchmark | [`backend/tests/test_ac_131_to_137_quality_and_architecture.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_131_to_137_quality_and_architecture.py) |

---

## 15. Deployment, Demo Journey & Operational Integrity (AC-138 to AC-149)

| AC ID | Requirement Summary | Verification Method | Automated Test / Implementation File |
| :--- | :--- | :--- | :--- |
| **AC-138** | Walking-skeleton Compose stack: `docker compose up -d` serves UI at `:8080` | Smoke / Compose Test | [`backend/tests/test_ac_138_skeleton.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_138_skeleton.py) |
| **AC-139** | Offline models: System operates without outbound network access | Container Config | [`backend/Dockerfile`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/Dockerfile) |
| **AC-140** | `/api/health` returns 200 with db/worker status; non-root user execution | Docker / API Test | [`backend/app/api/health.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/api/health.py) |
| **AC-141** | Data volume persistence across `docker compose down` and `up` | Docker Volume Test | Volumes `db_data` and `image_data` in [`docker-compose.yml`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docker-compose.yml) |
| **AC-142** | Reverse proxy TLS termination at `:8443` supporting TLS 1.2+ | Pass with a test certificate (TLS 1.1 refused; 1.2/1.3 accepted; Secure cookie; forged headers 403). Needs your mkcert certificate to use from a phone | `docker-compose.lan.yml`, `frontend/nginx/tls.conf`, `backend/tests/test_ac_07_tls_requirement.py` |
| **AC-143** | Multi-device network test on local network documented | **Manual, not done yet** — needs a real second device; steps in README section 7 | — |
| **AC-144** | Development emails routed to Mailpit at `:8025` / `:1025` | Integration Test | [`docker-compose.yml`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docker-compose.yml) & Mailpit service |
| **AC-145** | Seed command (`python -m app.seed`) populates synthetic campus tree and roles | CLI Execution Test | [`backend/app/seed.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/app/seed.py) |
| **AC-146** | Full end-to-end demo journey executed in CI | Automated Test | [`backend/tests/test_ac_146_demo_journey.py`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/backend/tests/test_ac_146_demo_journey.py) |
| **AC-147** | Isolated public synthetic demo deployment | Configuration | [`docker-compose.yml`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/docker-compose.yml) |
| **AC-148** | Documentation completeness (architecture, licences, data card, test plan) | Doc Verification | `docs/` & [`README.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/README.md) |
| **AC-149** | Explicit limitations documented in README | Doc Verification | [`README.md`](file:///c:/Users/abhir/OneDrive/Desktop/AIDS/Campus%20lost%20and%20found/README.md) |
