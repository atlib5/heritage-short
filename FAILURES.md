# FAILURES.md

## 2026-11-24 — Gemini 2.5 Flash retired for new users

**What broke:** Discovery listed `models/gemini-2.5-flash`, but a
generate_content call returned 404: "no longer available to new users.
Use models/gemini-3.8-flash."
**What I tried:** Read the error; checked the discovery list; found
`models/gemini-3.8-flash` present.
**Fix:** Changed model selection to prefer the newest Flash model
(3.8) instead of first-match. Logged the full model list in runs.jsonl
so future drift is visible.
**Lesson:** Never hardcode a model name. Discover, then choose by rule.

## 2026-11-24 — Cloudflare flux-2-klein rejected JSON body

**What broke:** POST to `@cf/black-forest-labs/flux-2-klein-9b` with
JSON `{"prompt": ..., "steps": ...}` returned: "required properties at
'/' are 'multipart'."
**What I tried:** Read the model's input schema; it requires a
`multipart` object, not a flat JSON body.
**Fix:** Switched the smoke test to `@cf/black-forest-labs/flux-1-schnell`,
whose schema accepts `prompt` and `steps` directly.
**Lesson:** Each model has its own input contract. Read the schema
before calling.

## 2026-11-24 — Gemini 503 High Demand (Transient Error)

**What broke:** Gemini 3.8 Flash returned `503 UNAVAILABLE` on the first try. The API reported: "currently experiencing high demand."
**What I tried:** Initially, nothing. I just read the error.
**Fix:** Implemented a `max_retries = 3` loop with exponential backoff (waiting 2s, then 4s, then 8s) before trying again. This handles transient server spikes gracefully without crashing the pipeline.
**Lesson:** Cloud APIs fail sometimes. The pipeline must be resilient to temporary spikes in demand so a whole run doesn't die because of a one-second server hiccup.

## 2026-11-24 — Gemini 3.8 Flash sustained 503 (not transient)

**What broke:** Retry loop with exponential backoff (1s, 2s, 4s) exhausted
all 3 attempts on `models/gemini-3.8-flash`. All returned `503 UNAVAILABLE:
high demand`. This is a sustained outage, not a one-second spike.
**What I tried:** First, retries alone. They failed because the model was
down for minutes, not seconds.
**Fix:** Built a model fallback chain from the discovery list:
3.8 → 3.7 → 3.6 → 3.5 → lite. The pipeline now tries the newest Flash
model, and if it stays down, moves to the next healthy sibling.
**Lesson:** Retries handle transient errors. Fallbacks handle sustained
outages. A production pipeline needs both.

## 2026-11-24 — Gemini Flash family: sustained 503 across 3.8, 3.7, 3.6, 3.5

**What broke:** Exponential backoff (1s, 2s, 4s) exhausted on 3.8-flash,
then the fallback chain moved to 3.7, 3.6, 3.5 — all returned the same
`503 UNAVAILABLE: high demand`. This is a sustained regional outage, not
a transient spike.
**What I tried:** First, retries alone. Then an unbounded fallback chain
through all 9 Flash models (≈27 attempts, 3–5 min). That was resilient
but wasteful.
**Fix:** Bounded the chain to 3 Flash models + 1 Pro fallback, 2
attempts each (~8 attempts, ~45s max), then clean exit with a
"wait and retry" message. Pro often serves from a different pool and
survives Flash saturation.
**Lesson:** Retries handle transient errors. Fallbacks handle single-model
outages. Bounded fallbacks + a clean give-up handle **family-wide**
outages without burning the whole run.

## 2026-11-25 — UnicodeDecodeError on Amharic JSON

**What broke:** `validate_storyboard.py` crashed with `UnicodeDecodeError: 'charmap' codec can't decode byte 0x90`.
**Why:** Python on Windows defaults to `cp1252` encoding when opening files. `storyboard.json` contains Amharic characters (UTF-8), which cp1252 cannot read.
**Fix:** Explicitly passed `encoding="utf-8"` to both `open()` calls in the validator.
**Lesson:** When building software for non-English languages, always force UTF-8 encoding when reading or writing text files. Never rely on the operating system's default encoding.
