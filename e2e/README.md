# Browser end-to-end tests

| Script | Checks |
| --- | --- |
| `journey.py` | The blueprint demo (AC-146): found report → moderator approval → search → match suggestion → claim with the finder's question → approval → claimant's code → wrong code then right code at the desk → dashboard → admin evaluation page. Along the way: private details never in the public listing, the desk never shows the code, an axe scan of eight pages with no serious or critical violations (AC-126), and no horizontal scroll at 360 × 740 (AC-127). |
| `keyboard.py` | Reports a found item and submits a claim using only the keyboard, and fails if any element reached with Tab has no visible focus indicator (AC-125). |

Run against a **freshly seeded** stack (the journey uses the seeded demo accounts and expects a
clean database), from the repository root:

```bash
docker compose down -v && docker compose up -d --build
docker compose exec -T backend python -m app.seed
sh e2e/run.sh
```

The tests run in the official Playwright image on the Compose network, so nothing is installed
locally. `journey.py` downloads axe-core from cdnjs at run time. Screenshots and a JSON log are
written to `e2e/output/` (git-ignored).

These are not in CI yet: CI would need to build the backend image with the model weights
(about 700 MB) to run the whole stack.
