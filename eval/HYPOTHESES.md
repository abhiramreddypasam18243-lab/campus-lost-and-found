# Pre-registered hypotheses and analysis plan

Written on 2026-10-21, after tuning on the development split and **before** the test split was
evaluated. It is committed together with the frozen configuration, before the commit that adds
the test results, so the git history shows the order.

## Frozen configuration

- File: `eval/results/frozen_config.json`
- SHA-256 of the configuration: `b3cd10219475bbf16a66127684d956547ef99c0af2560028fccb4ec8c94294dc`
- Hybrid weights chosen on the development split (grid step 0.05, 231 points, by dev MRR):
  text 0.40, location 0.30, time 0.30 (image excluded: the benchmark has no photos)
- Learned fusion: logistic regression over text, location and time, trained on development pairs
- Text model: all-MiniLM-L6-v2 at revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`
- Seed 42; test split of 210 queries, each ranked against 310 found reports

## Hypothesis

**H1:** The hand-weighted hybrid (system D) has a higher MRR on the test split than the best
single-signal baseline.

- The single-signal baselines are A (BM25 keyword search) and B (text embeddings alone).
  The image system C cannot be evaluated (no photos), so it is not a candidate baseline.
- "Best" means whichever of A and B has the higher test MRR. Choosing the stronger baseline
  after the fact can only make H1 harder to support.
- Test: paired bootstrap over the 210 test queries (1,000 resamples, seed 42) of
  MRR(D) − MRR(best baseline).
- Decision rule: H1 is supported only if the 95% interval of the difference lies entirely above 0.
  Otherwise it is reported as not supported. The outcome is reported either way.

## Secondary results (reported, not hypotheses)

- Learned fusion (E) against the same baseline, marked exploratory.
- Ablations: the hybrid with text, location or time removed.
- Robustness: location one level off and time shifted 24 hours on 0, 25 and 50% of the true
  found reports.
- Latency of exact and HNSW search in pgvector at 1,000, 10,000 and 100,000 random vectors.

## Expectations stated in advance

The synthetic generator places location and time with the same assumptions the scoring encodes,
and spreads items over 60 days while each found report follows its loss within hours. The
development MRR of the hybrid was already 0.99, so a large hybrid advantage over text alone is
expected **largely by construction**. That would not show that location and time help on real
reports; the text-only result (B) is the more informative number about semantics.
