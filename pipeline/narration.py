"""Generate narration and dialogue from storyboard.json using Addis AI."""
import json
import hashlib
import os
import time
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from addisai import AddisAI

load_dotenv()

# Initialize Addis AI client (reads ADDIS_API_KEY from .env)
addis = AddisAI()

ROOT = Path(__file__).parent.parent
STORYBOARD_PATH = ROOT / "storyboard.json"
AUDIO_DIR = ROOT / "outputs" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "runs.jsonl"

# Addis AI Voice IDs
# You can see the full list here: https://docs.addisassistant.com/docs/capabilities/text-to-speech
VOICES = {
    "narrator": "am-hamen",      # Warm conversational delivery (female)
    "mother": "am-nejat"         # Smooth measured elegance (female) - good for motherly advice
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
    """Calls Addis AI TTS and saves to WAV. Uses caching."""
    if not text.strip():
        return None

    text_hash = hashlib.md5((text + voice_name).encode('utf-8')).hexdigest()
    hash_path = output_path.with_suffix(".hash")
    
    if output_path.exists() and hash_path.exists():
        if hash_path.read_text() == text_hash:
            print(f"  [cache hit] {output_path.name}")
            return output_path

    print(f"  [api call] generating {output_path.name} with voice {voice_name}...")
    t0 = time.time()
    
    try:
        # Call Addis AI TTS
        # We use WAV format for compatibility with the assembly script
        clip = addis.voice.generate(
            voice_id=voice_name,
            text=text,
            language="am", 
            output_format="wav_44100"
        )
        
        # Save the audio file directly
        clip.to_file(str(output_path))
        hash_path.write_text(text_hash)
        
        log("narration", f"addis-{voice_name}", time.time() - t0, "ok",
            file=output_path.name, chars=len(text))
        return output_path
        
    except Exception as e:
        log("narration", f"addis-{voice_name}", time.time() - t0, "error",
            file=output_path.name, error=str(e)[:300])
        return None

def main():
    with open(STORYBOARD_PATH, encoding="utf-8") as f:
        storyboard = json.load(f)

    shots = storyboard["shots"]
    print(f"Processing narration for {len(shots)} shots...")

    for shot in shots:
        shot_id = shot["id"]
        
        # 1. Handle the Narrator (Adult Daughter)
        if shot.get("narration"):
            out_path = AUDIO_DIR / f"{shot_id}_narrator.wav"
            generate_audio(shot["narration"], VOICES["narrator"], out_path)

        # 2. Handle the Mother's Dialogue (if present)
        if "dialogue" in shot and shot["dialogue"].get("text_am"):
            out_path = AUDIO_DIR / f"{shot_id}_mother.wav"
            generate_audio(shot["dialogue"]["text_am"], VOICES["mother"], out_path)

        # Be polite to the API
        time.sleep(2)

    print("✓ Narration generation complete.")

if __name__ == "__main__":
    main()