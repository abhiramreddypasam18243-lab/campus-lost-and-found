The spec above is the source of truth. If the code and the spec disagree, stop and tell me which one should change. Do not quietly change either. The original assignment blueprint is docs/Smart_Campus_Lost_and_Found_Project_Blueprint.docx; the spec's section 16 maps it onto the spec's requirements.

About me and this project

I am an undergraduate student building this as a graded project. I will be quizzed on it in a viva, so I must understand every module. I want to finish as fast as possible, so keep the pace high and the explanations short.

How to work
Follow the build order in section 19 of the spec, one step at a time. Finish a step (all its acceptance criteria passing) before starting the next. Do not stop in the middle of a step unless you are blocked, a [LEARN] module comes up, or the spec has an open question you need me to answer.
Tests first. For each acceptance criterion, write the failing test, then the code that makes it pass. Name each test after its AC ID (for example test_ac_53_hybrid_example).
Derive expected values by calculation, as the acceptance criteria do. Never copy the application's own output into a test as the expected answer, and never edit a test value or a threshold to make a test pass. If a test seems wrong, tell me.
Fast tests use fixed stand-in embeddings, so the normal suite needs no model downloads. Tests that use the real models are marked slow.
Run all checks after every change: formatting, lint, type checks, migrations and tests. Show me the results at the end of each step.
Move fast. Do not pause for review between modules. At the end of each step, give me a short summary: files changed, tests passing, anything I should check.
Ask before deciding. If the spec leaves a choice open (section 21), ask me. When we decide, add a row to the Decisions Log in SPEC.md and to DECISIONS.md.
Do not add features that are not in the spec. Suggest them at the end instead.
Learning rules
At the end of each step, add a short entry to docs/learning-log.md: what was built, why it is designed that way, one thing that could go wrong, and 3 quiz questions for me (no answers; I will answer them myself).
These modules are marked [LEARN]. For them, first explain the design and the key edge cases in a few sentences, then let me write the first version myself and review it afterwards:
The location and time scores, and the hybrid score with missing signals and its explanations (spec sections 6.3 to 6.6)
The handover code: generation, HMAC storage, normalisation, attempts and expiry (spec section 5.4)
The evaluation metrics, bootstrap and paired bootstrap (spec sections 7.3 and 7.4)
The whitelist serialisers and the role and ownership checks (spec sections 3, 4 and 12)
If I say "you write it" for a [LEARN] module, write it, and still add its learning-log entry.
If I ask "why", explain with a small concrete example, not just a definition.
Safety, privacy and integrity rules (never relax these)
AI is advisory. Never write code that changes a report, claim or handover state because of a score.
Default-deny serialisers. Every response a normal user sees is built from an explicit whitelist. Private details, verification prompts, reporter identity, exact locations, private images, claim evidence, handover codes and hashes must never appear in a public view, an explanation, a notification or a log. Use canary strings in tests.
Handover codes: secure random generation, store only the HMAC, constant-time comparison, never log or return a code except to the approved claimant.
No real student data. Use only synthetic data and the consented evaluation subsets. Never invent photos, consent records or licences, and ask me for any dataset or model whose licence you cannot confirm.
Evaluation integrity. Never tune on the test set or give tuning code a path to it. Never edit results or choose a configuration after seeing test results. Record the hypotheses first and report the outcome whichever way it falls. Never fabricate or round up benchmark numbers.
Models: pin versions and checksums, bake them into the images, and make the running backend and worker work with no outbound network access.
Project rules
Layering: the domain package contains pure functions with no framework, database, model or clock imports. Routers are thin; rules live in services and the domain package.
Identity and roles: derive them from the session only. Request schemas forbid unknown fields. Foreign resources return 404.
Consistency: write state changes together with their notifications and jobs in one transaction (outbox). Workers claim jobs with FOR UPDATE SKIP LOCKED and must be idempotent.
Time: store UTC, inject the clock, and compute local days in the user's IANA timezone.
Secrets: only in environment variables. Never commit .env. Never log passwords, tokens, codes or full emails.
Uploads: decide the file type by content, guard pixel counts, strip metadata, re-encode, store under random keys, and serve only through the authorised route.
Dependencies: pin versions, and ask before adding a new dependency.
Tests use PostgreSQL with pgvector, never SQLite.
Deployment: the project must always run with Docker Compose (spec section 13). Build the walking-skeleton stack in step 1, keep it working, and rebuild after each step. Application containers run as non-root, and credentials from non-localhost clients are accepted only over TLS.
Commands

I have not verified the exact commands for the versions you choose. Correct this list as the real commands appear.

Backend tests: cd backend && pytest -q (slow model tests: pytest -m slow)
Lint and types: cd backend && ruff check . && mypy .; cd frontend && npm run lint && npx tsc --noEmit
Migrations: cd backend && alembic upgrade head (and alembic check)
Frontend and end-to-end tests: cd frontend && npm test; npx playwright test
Generate the benchmark: python -m eval.generate --seed 1; tune on the development set: python -m eval.tune; final test run (once): python -m eval.final
Seed the campus and demo data: docker compose run --rm backend python -m app.seed
Run the deployed service: docker compose up -d --build, then open http://localhost:8080
Git

Commit after each completed step, with a message that names the AC IDs, for example Add handover codes (AC-86 to AC-96).

Content
Mini_Real_Time_Strategy_Game_Project_Guide.docx

DOCX

Advanced_Gym_Workout_Logger_Diet_Planning_Blueprint.docx

DOCX

Smart_Campus_Lost_and_Found_Project_Blueprint.docx

DOCX

# SPEC.md — NLP Research Intelligence Platform ## 1. Project Overview **Project Name:** NLP Research Intelligence Platform **Project Type:** Natural Language Processing (NLP) / Generative AI **Development Methodology:** Spec-Driven Development (SDD) **Objective:** Build a research

PASTED