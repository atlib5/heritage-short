# Experiments

## 1. TTS Engine Comparison (Gemini vs. Addis AI)

- **Hypothesis:** Gemini 3.8 Flash TTS would handle Amharic natively.
- **Result:** Failed. It applied an English prosody, making it sound like a foreigner reading Amharic.
- **Fix:** Switched to Addis AI. The result was immediate—a native, emotionally resonant voice.

## 2. Image Model Quality (FLUX-1 Schnell vs. FLUX-2 Dev)

- **Hypothesis:** Schnell is faster and sufficient.
- **Result:** Failed. Schnell exhibited a "beauty bias," generating smiling, camera-facing stock photos and ignoring narrative prompts.
- **Fix:** Switched to FLUX-2-dev with a negative prompt ("smiling, looking at camera"). The cinematic quality improved massively.

## 3. Hardware Constraints (Cloudflare vs. Kaggle)

- **Hypothesis:** We could generate all images on Cloudflare free tier.
- **Result:** Exhausted the 10,000 daily neurons after iteration.
- **Fix:** Moved the entire pipeline to Kaggle T4 GPUs, using 4-bit quantization to fit within VRAM limits.
