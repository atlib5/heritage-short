"""Generate narration and dialogue from storyboard.json using Gemini TTS."""
import json
import hashlib
import os
import time
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
client = genai.Client(api_key=GEMINI_KEY)

ROOT = Path(__file__).parent.parent
STORYBOARD_PATH = ROOT / "storyboard.json"
AUDIO_DIR = ROOT / "outputs" / "audio"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "runs.jsonl"

# Voice choices (you can change these to other Gemini voices like 'Puck', 'Charon', 'Kore')
# Aoede is often good for warm female narration.
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
    """Calls Gemini TTS and saves to WAV. Uses caching to prevent re-runs."""
    if not text.strip():
        return None

    # Caching: hash the text and voice
    text_hash = hashlib.md5((text + voice_name).encode('utf-8')).hexdigest()
    hash_path = output_path.with_suffix(".hash")
    
    if output_path.exists() and hash_path.exists():
        if hash_path.read_text() == text_hash:
            print(f"  [cache hit] {output_path.name}")
            return output_path

    print(f"  [api call] generating {output_path.name} with voice {voice_name}...")
    t0 = time.time()
    
    # The TTS model. You can also try 'gemini-2.5-flash' if this 404s.
    model_name = "gemini-2.5-flash" 
    
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
        
        # Extract the audio bytes
        audio_part = response.candidates[0].content.parts[0]
        audio_data = audio_part.inline_data.data
        
        with open(output_path, "wb") as f:
            f.write(audio_data)
            
        hash_path.write_text(text_hash)
        
        log("narration", model_name, time.time() - t0, "ok", 
            file=output_path.name, voice=voice_name, chars=len(text))
        return output_path
        
    except Exception as e:
        log("narration", model_name, time.time() - t0, "error", 
            file=output_path.name, error=str(e)[:200])
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

    print("✓ Narration generation complete.")

if __name__ == "__main__":
    main()