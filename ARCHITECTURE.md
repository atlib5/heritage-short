#### 2. `ARCHITECTURE.md`

```markdown
# Architecture

## The Contract

`storyboard.json` is the single source of truth. Every script reads from it. If a prompt changes, the hash changes, and only that specific asset is regenerated.

## The 5 Stages

1. **Validation:** `jsonschema` ensures the contract is valid before wasting API calls.
2. **Narration:** Uses Addis AI (native Amharic). It pads/trims audio to match the exact `duration_s` of the shot.
3. **Keyframes:** Uses FLUX.2-dev via Cloudflare (multipart form-data). Caches images using MD5 hashes.
4. **Video:** Wan 2.2 on Kaggle T4. Uses 4-bit quantization to prevent OOM crashes.
5. **Assembly:** FFmpeg uses `concat`, `zoompan` (Ken Burns), `sidechaincompress` (ducking music), and `loudnorm` to render the final MP4.

## Failure Handling

- **Cloudflare 10k limit:** Fell back to local 4-bit quantized FLUX on Kaggle.
- **TTS Quotas:** Implemented exponential backoff and a fallback chain for Gemini; switched to Addis AI for native prosody.
- **Memory (OOM):** Kaggle scripts use `BitsAndBytesConfig` (NF4) and `enable_sequential_cpu_offload()`.
```
