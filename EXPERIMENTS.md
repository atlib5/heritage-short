# EXPERIMENTS.md

## 2026-11-25 — TTS Voice Accent Accuracy in Amharic

**Hypothesis:** The Gemini TTS model (`gemini-2.5-flash-preview-tts`) will produce a natural-sounding native Amharic accent, given its stated support for 130+ languages.
**Method:** Generated 1 test sentence ("አንዳንድ ሕልሞች በአንድ ሰው እጅ ብቻ አይገነቡም።") using three different voices: `Aoede`, `Kore`, and `Charon`.
**Result:**

- `Aoede`: Fluent pronunciation, but distinctly English prosody (sounds like a native English speaker reading Amharic).
- `Kore`: Similar English prosody, slightly higher pitch.
- `Charon`: Deeper tone, but still carries a non-native rhythm.
  **Analysis:** The model's training data for Amharic is likely text-heavy but voice-light. It is transliterating the Ge'ez script into phonetic sounds using an English phonetic model.
  **Decision:** Use `Charon` for the narrator (deepest, most serious tone) and accept the non-native accent. Documented in FAILURES.md.
  **Future Work:** If I had access to a paid, high-quality Amharic voice model (like ElevenLabs custom voices), I would use that for the final cut. For this challenge, the AI-generated accent adds a specific, honest texture to the film.

  ## 2026-11-25 — Keyframe Model Comparison: FLUX-1 Schnell vs FLUX-2 Dev

  **Hypothesis:** `flux-1-schnell` (4 steps) would be sufficient for generating emotional, cinematic keyframes.
  **Method:** Generated 11 images using `flux-1-schnell` with prompts specifying "exhausted", "disappointed", and "collapsed model".
  **Result:** Failed. The model exhibited a strong "beauty bias," ignoring narrative instructions. It generated smiling, camera-facing stock photos and completely ignored the "collapsed model" instruction.
  **Correction:** Switched to `@cf/black-forest-labs/flux-2-dev` (8 steps), added a negative prompt ("smiling, looking at camera, eye contact"), and updated the storyboard to explicitly direct the subject to "look down" and "no eye contact".
  **Outcome:** Pending review of the new renders. This highlights the necessity of negative prompts and higher-step models for cinematic directing.

**Outcome (FLUX-2-dev):** Success. The switch to `flux-2-dev` with a negative prompt ("smiling, looking at camera") and explicit directional language ("look down", "profile view") completely solved the stock-photo bias. The images are now vertical (768x1344), highly cinematic, and emotionally match the storyboard. The lighting in Shot 01 (chiaroscuro desk lamp) and Shot 03 (warm morning window light) is exceptional.

## 2026-11-25 — Character Consistency Failure in FLUX

**Hypothesis:** FLUX-2-dev would maintain character consistency across shots based on general descriptions (e.g., "Ethiopian mother").
**Result:** Failed. The model generated completely different faces, ages, and hairstyles for the same characters across different shots. It also hallucinated objects (e.g., mother putting a pencil inside a sandwich) due to confusing overlapping prompts.
**Correction:**

1. Locked character descriptions (exact facial features, skin tone, clothing) into `storyboard.json` and injected them verbatim into every relevant prompt.
2. Simplified action prompts to prevent hallucination (e.g., removed "sharpening pencil" while packing bag to avoid pencil-in-sandwich errors).
3. Changed Shot 07 from a split-screen prompt to a single adult hand shot.
   **Lesson:** AI models have zero memory. "Prompt Locking" (repeating exact physical descriptions) is mandatory for multi-shot consistency.
