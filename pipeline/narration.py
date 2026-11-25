"""Generate narration and dialogue from storyboard.json using Gemini TTS."""
import json
import hashlib
import os
import time
import wave
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
GEMINI_KEY = os.environ["GEMINI_API_KEY"]

# Force the client to use the v1beta API version, which supports speech_config.
client = genai.Client(api_key=GEMINI_KEY, http_options={'api_version': 'v1beta'})

ROOT = Path(__file__).parent.parent
STORYBOARD_PATH = ROOT / "storyboard.json"
AUDIO_DIR = ROOT / "outputs" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "runs.jsonl"

# Voice choices (you can change these to other Gemini voices like 'Puck', 'Charon', 'Kore')
VOICES = {
    "narrator": "Aoede",
    "mother": "Zephyr"
}

def log(stage, model, latency, status, **extra):
    line = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "stage": stage, "model": model,
        "latency_s": round(latency, 2),
        "status": status, **extra,
    }
    with open(LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(line) + "\n")
    print(json.dumps(line))

def generate_audio(text, voice_name, output_path):
    """Calls Gemini TTS and saves to WAV. Retries on 429. Uses caching."""
    if not text.strip():
        return None

    text_hash = hashlib.md5((text + voice_name).encode('utf-8')).hexdigest()
    hash_path = output_path.with_suffix(".hash")
    
    if output_path.exists() and hash_path.exists():
        if hash_path.read_text() == text_hash:
            print(f"  [cache hit] {output_path.name}")
            return output_path

    print(f"  [api call] generating {output_path.name} with voice {voice_name}...")
    model_name = "gemini-2.5-flash-preview-tts"
    
    max_retries = 4
    for attempt in range(max_retries):
        t0 = time.time()
        try:
            response = client.models.generate_content(
                model=model_name,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name
                            )
                        )
                    )
                )
            )
            
            # NEW: Check for empty response before accessing parts
            if (not response.candidates or 
                not response.candidates[0].content or 
                not response.candidates[0].content.parts):
                raise ValueError("Empty response from API")
            
            audio_data = response.candidates[0].content.parts[0].inline_data.data
            
            with wave.open(str(output_path), "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(24000)
                wf.writeframes(audio_data)
                
            hash_path.write_text(text_hash)
            
            log("narration", model_name, time.time() - t0, "ok",
                file=output_path.name, voice=voice_name, chars=len(text))
            return output_path
            
        except Exception as e:
            error_msg = str(e)
            # NEW: Retry on 429, NoneType, or Empty response
            if "429" in error_msg or "NoneType" in error_msg or "Empty response" in error_msg:
                wait_time = 15 * (attempt + 1) # 15s, 30s, 45s
                print(f"  [API empty/quota hit] waiting {wait_time}s before retry...")
                time.sleep(wait_time)
            else:
                log("narration", model_name, time.time() - t0, "error",
                    file=output_path.name, error=error_msg[:300])
                return None

def main():
    with open(STORYBOARD_PATH, encoding="utf-8") as f:
        storyboard = json.load(f)

    shots = storyboard["shots"]
    print(f"Processing narration for {len(shots)} shots...")

    for shot in shots:
        shot_id = shot["id"]
        any_generated = False
        
        # 1. Handle the Narrator
        if shot.get("narration"):
            out_path = AUDIO_DIR / f"{shot_id}_narrator.wav"
            if generate_audio(shot["narration"], VOICES["narrator"], out_path):
                any_generated = True
                
        # 2. Handle the Mother's Dialogue
        if "dialogue" in shot and shot["dialogue"].get("text_am"):
            out_path = AUDIO_DIR / f"{shot_id}_mother.wav"
            if generate_audio(shot["dialogue"]["text_am"], VOICES["mother"], out_path):
                any_generated = True
                
        # If we made an API call, be polite and wait 5s before the next one
        if any_generated:
            time.sleep(5)

    print("✓ Narration generation complete.")

if __name__ == "__main__":
    main()