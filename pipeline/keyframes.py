"""Generate keyframes from storyboard.json using Cloudflare Workers AI (FLUX)."""
import json
import hashlib
import os
import time
import base64
import requests
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()
CF_ACCOUNT = os.environ["CLOUDFLARE_ACCOUNT_ID"]
CF_TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]

ROOT = Path(__file__).parent.parent
STORYBOARD_PATH = ROOT / "storyboard.json"
OUT_DIR = ROOT / "outputs" / "keyframes"
OUT_DIR.mkdir(parents=True, exist_ok=True)
LOG = ROOT / "runs.jsonl"

# Using flux-1-schnell for speed. It accepts standard JSON.
CF_MODEL = "@cf/black-forest-labs/flux-2-dev"

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

def generate_image(prompt, output_path):
    # Caching
    prompt_hash = hashlib.md5(prompt.encode('utf-8')).hexdigest()
    hash_path = output_path.with_suffix(".hash")
    
    if output_path.exists() and hash_path.exists():
        if hash_path.read_text() == prompt_hash:
            print(f"  [cache hit] {output_path.name}")
            return output_path

    print(f"  [api call] generating {output_path.name}...")
    t0 = time.time()
    
    url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/{CF_MODEL}"
    
    # FLUX-2-dev requires multipart/form-data, not JSON.
    # The tuple format (None, "value") tells requests to send it as a form field.
    files = {
        "prompt": (None, prompt),
        "negative_prompt": (None, "smiling, looking at camera, eye contact, perfect teeth, stock photo, generic AI face, extra fingers, distorted hands"),
        "steps": (None, "8"),
        "width": (None, "768"),
        "height": (None, "1344"),
    }
    
    max_retries = 3
    for attempt in range(max_retries):
        try:
            r = requests.post(
                url,
                headers={"Authorization": f"Bearer {CF_TOKEN}"},
                files=files,
                timeout=180,
            )
            data = r.json()
            
            if not data.get("success"):
                raise ValueError(f"API error: {data.get('errors')}")
                
            img_b64 = data.get("result", {}).get("image")
            if not img_b64:
                raise ValueError("No image data in response")
                
            with open(output_path, "wb") as f:
                f.write(base64.b64decode(img_b64))
                
            hash_path.write_text(prompt_hash)
            
            log("keyframes", CF_MODEL, time.time() - t0, "ok", 
                file=output_path.name, bytes=len(img_b64))
            return output_path
            
        except Exception as e:
            error_msg = str(e)
            if "429" in error_msg or "capacity" in error_msg.lower() or "busy" in error_msg.lower():
                wait = 15 * (attempt + 1)
                print(f"  [busy] waiting {wait}s...")
                time.sleep(wait)
            else:
                log("keyframes", CF_MODEL, time.time() - t0, "error", 
                    file=output_path.name, error=error_msg[:300])
                return None
                
    return None

def main():
    with open(STORYBOARD_PATH, encoding="utf-8") as f:
        storyboard = json.load(f)

    style = storyboard["style_block"]
    shots = storyboard["shots"]
    
    print(f"Generating keyframes for {len(shots)} shots...")
    
    for shot in shots:
        shot_id = shot["id"]
        
        # Skip the end card—that's generated in post-production with FFmpeg, not FLUX.
        if shot_id == "shot_12":
            print(f"  [skip] {shot_id} is an end card (post-production)")
            continue
            
        # Combine style block + shot-specific prompt
        full_prompt = f"{style}. {shot['image_prompt']}"
        
        out_path = OUT_DIR / f"{shot_id}.png"
        generate_image(full_prompt, out_path)
        
        # Be polite to Cloudflare's API
        time.sleep(2)

    print("✓ Keyframe generation complete.")

if __name__ == "__main__":
    main()