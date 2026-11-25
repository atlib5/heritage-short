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

## 2026-11-25 — Gemini TTS: 400 speechConfig Unknown

**What broke:** The narration script tried to generate audio using `gemini-2.5-flash`, but the API returned `400 INVALID_ARGUMENT: Unknown name "speechConfig"`.
**Why:** `gemini-2.5-flash` is a text-only model. It does not accept audio configuration parameters like `speech_config`.
**Fix:** Switched to the dedicated TTS model `gemini-2.5-flash-preview-tts` (or `gemini-2.0-flash`).
**Lesson:** Audio generation requires a specific TTS model endpoint, not the standard text Flash model. Always verify model capabilities before passing modality-specific configurations.

## 2026-11-25 — Gemini TTS: Persistent speechConfig 400 Error

**What broke:** Even after switching from `gemini-2.0-flash` to the dedicated TTS endpoint, the API returned `400 INVALID_ARGUMENT: Unknown name "speechConfig"`.
**Diagnosis:** The `speech_config` parameter is a preview feature. The installed `google-genai` SDK version was likely too old to serialize this field into the API's expected `speechConfig` JSON key. Additionally, using any model name without the `-tts` suffix guarantees a failure.
**Fix:**

1. Upgraded the SDK with `pip install --upgrade google-genai` to ensure `types.SpeechConfig` is supported.
2. Forced the model to `gemini-2.5-flash-preview-tts`.
3. Implemented a `wave` module wrapper to properly save the raw PCM bytes returned by the TTS endpoint into a playable `.wav` file (raw bytes lack WAV headers).
   **Lesson:** Audio generation requires both a dedicated TTS model _and_ an SDK that supports the preview `speech_config` serialization. Raw audio bytes from the API are PCM data and must be wrapped with WAV headers before they can be played.

## 2026-11-25 — Gemini TTS: `speechConfig` 400 Error (API Version Mismatch)

**What broke:** After switching to the dedicated TTS model, the API still returned `400 INVALID_ARGUMENT: Unknown name "speechConfig"`.
**Root Cause:** The `google-genai` SDK (v3.0+) defaults to the `v1` API endpoint, which does not support the `speech_config` parameter. The `v1beta` endpoint is required for audio generation.
**Fix:**

1. Explicitly forced the client to use the `v1beta` API: `genai.Client(api_key=..., http_options={'api_version': 'v1beta'})`.
2. Ensured the model name was the dedicated TTS preview: `gemini-2.5-flash-preview-tts`.
3. Added a `wave` module wrapper to save the raw PCM audio bytes with proper WAV headers.
   **Lesson:** Not all API endpoints are created equal. Preview features like TTS often require the `v1beta` endpoint, and the SDK's default may change between versions. Always verify the API version when a parameter is reported as "unknown."

## 2026-11-25 — Gemini TTS: 429 RESOURCE_EXHAUSTED (Quota)

**What broke:** Generating 12 audio clips back-to-back caused the API to return `429 RESOURCE_EXHAUSTED` after the 6th request.
**Why:** The free tier of the Gemini API has strict Requests-Per-Minute (RPM) limits. The script fired requests faster than the quota window allowed.
**Fix:**

1. Wrapped the API call in a retry loop that specifically detects "429" and waits 15s, 30s, 45s before trying again.
2. Added a mandatory `time.sleep(5)` between successful shots.
3. The caching layer (`.hash` files) ensures that a re-run skips already-generated audio, saving quota.
   **Lesson:** Free APIs are rate-limited. Pipelines must be polite and patient (exponential backoff + caching) to survive quota windows.

## 2026-11-25 — Gemini TTS: NoneType error on valid response

**What broke:** The API returned a successful HTTP status but an empty payload (`response.candidates[0].content` was `None`). This caused a crash when accessing `.parts[0]`.
**Why:** The TTS endpoint occasionally returns an empty response without throwing an HTTP error code.
**Fix:** Added a validation check to ensure `response.candidates`, `content`, and `parts` are not empty. If they are, raise a custom `ValueError("Empty response from API")` and trigger the retry loop (treating it like a 429).
**Lesson:** Never assume a 200 OK means the data is actually there. Always validate the payload structure before accessing deep attributes.

## 2026-11-25 — FFmpeg Windows Path Colon Error

**What broke:** The FFmpeg subtitles filter failed with `Unable to parse "original_size" option value` when passed an absolute Windows path (`C:\Users\...`).
**Why:** FFmpeg uses colons (`:`) to separate filter options. The `C:` in the Windows drive letter caused FFmpeg to misinterpret the path as a new parameter.
**Fix:** Changed the Python script to run FFmpeg with `cwd=OUT_DIR` and pass the subtitle file as a relative path (`subtitles.srt`). This avoids the drive letter colon entirely.
**Lesson:** When passing file paths to FFmpeg filters on Windows, always use relative paths and change the working directory. Absolute paths require complex escaping (`C\\:/...`) that is prone to errors.

## 2026-11-25 — Cloudflare FLUX-1-schnell: width/height not allowed

**What broke:** The keyframes script sent `width` and `height` in the JSON payload, and Cloudflare returned: `AiError: Bad input: Error: Additional or unevaluated properties '/width, /height' at '/' not allowed`.
**Why:** The `@cf/black-forest-labs/flux-1-schnell` model's input schema only accepts `prompt` and `steps`. It does not support dimension parameters. This is a strict schema enforcement by Cloudflare Workers AI.
**Fix:** Removed `width` and `height` from the payload. The model now generates a default square image, which will be cropped/padded to 9:16 during the assembly stage using FFmpeg.
**Lesson:** Every AI model has its own input contract. Always read the official schema before calling. This is the second time this lesson appeared in this project (first: flux-2-klein multipart requirement). Document model schemas in ARCHITECTURE.md for future reference.

## 2026-11-25 — Cloudflare FLUX: JSON vs Multipart (third occurrence)

**What broke:** `flux-2-dev` returned `required properties at '/' are 'multipart'` when sent a JSON body.
**Why:** Cloudflare's FLUX models have inconsistent input contracts:

- `@cf/black-forest-labs/flux-1-schnell` → accepts JSON (`{"prompt": ..., "steps": ...}`)
- `@cf/black-forest-labs/flux-2-dev` → requires `multipart/form-data`
- `@cf/black-forest-labs/flux-2-klein-*` → requires `multipart/form-data`
  **Fix:** Replaced `json=payload` with `files={...}` using `(None, value)` tuples in the `requests` call. This forces `multipart/form-data` encoding and also re-enabled `width` and `height` (768x1344 for 9:16 vertical).
  **Pattern Recognized:** This is the third Cloudflare schema error in this project (smoke test, keyframes-v1, keyframes-v2). Each model requires its own contract.
  **Lesson:** Never trust a provider to have a uniform API. Read the schema per model, not per provider. Will document all Cloudflare model contracts in ARCHITECTURE.md.

## 2026-11-25 — Cloudflare Workers AI: Daily Quota Exhausted

**What broke:** After generating ~30 images during development and prompt-refinement, the API returned `4006: you have used up your daily free allocation of 10,000 neurons`.
**Why:** `flux-2-dev` consumes significantly more neurons per image than `flux-1-schnell`. Iterating on prompts and generating 11 images multiple times burned through the daily free tier allowance.
**Fix:** Pivoting to Kaggle (free GPU) for remaining generation and animation. The pipeline caches images, so the ones we already generated are safe. The quota resets at midnight UTC.
**Lesson:** Free tiers are for prototyping, not production. Always track consumption in COSTS.md and build caching so quota resets don't lose work.
