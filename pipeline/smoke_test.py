"""Smoke test: prove each provider answers, log latency to runs.jsonl.
Model names are discovered, then chosen by preference — never hardcoded first-match."""
import base64, json, os, time
from datetime import datetime, timezone
import requests
from dotenv import load_dotenv
from google import genai

load_dotenv()
GEMINI_KEY = os.environ["GEMINI_API_KEY"]
CF_ACCOUNT = os.environ["CLOUDFLARE_ACCOUNT_ID"]
CF_TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]
LOG = "runs.jsonl"

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

# --- 1. GEMINI: discover models, build a fallback chain ---
client = genai.Client(api_key=GEMINI_KEY)

t0 = time.time()
available = []
try:
    for m in client.models.list():
        available.append(m.name)
    log("discovery", "gemini", time.time() - t0, "ok", models=available)
except Exception as e:
    log("discovery", "gemini", time.time() - t0, "error", error=str(e))

def flash_chain(models):
    """Ordered list: newest flash first, then older flash, then lite."""
    flash = [m for m in models
             if "flash" in m.lower()
             and "tts" not in m.lower()
             and "image" not in m.lower()]
    # preferred order: 3.8, 3.7, 3.6, 3.5, then whatever else
    def rank(m):
        for i, v in enumerate(["3.8", "3.7", "3.6", "3.5"]):
            if v in m:
                return i
        return 99
    return sorted(flash, key=rank)

chain = flash_chain(available)
print("fallback chain:", chain)

# --- Gemini: bounded fallback chain ---
t0 = time.time()
success = False
last_error = ""
MAX_MODELS = 3          # don't grind through all 9
ATTEMPTS_PER_MODEL = 2  # 2 tries per model is enough

# Build a short chain: first 3 flash models, then a non-flash fallback
flash_models = flash_chain(available)[:MAX_MODELS]
pro_fallback = [m for m in available if "pro" in m.lower() and "image" not in m.lower()][:1]
short_chain = flash_models + pro_fallback

print(f"bounded chain ({len(short_chain)} models):", short_chain)

for model_name in short_chain:
    print(f"trying {model_name}...")
    for attempt in range(ATTEMPTS_PER_MODEL):
        try:
            r = client.models.generate_content(
                model=model_name, contents="Reply with exactly: smoke test ok")
            log("script", model_name, time.time() - t0, "ok",
                output=r.text.strip()[:80],
                prompt_tokens=getattr(r.usage_metadata, "prompt_token_count", None))
            success = True
            break
        except Exception as e:
            last_error = str(e)
            if "503" in last_error or "429" in last_error:
                wait = 2 ** attempt
                print(f"  attempt {attempt+1} failed. retrying in {wait}s")
                time.sleep(wait)
            else:
                print(f"  hard error: {last_error[:80]}")
                break
    if success:
        break

if not success:
    log("script", "bounded-chain", time.time() - t0, "error",
        error=f"all {len(short_chain)} models failed. last: {last_error[:200]}")
    print("Giving up. This looks like a sustained outage. Wait 10–15 min and retry.")
    
# --- 2. CLOUDFLARE: use flux-1-schnell (JSON schema, not multipart) ---
cf_model = "@cf/black-forest-labs/flux-1-schnell"
url = f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCOUNT}/ai/run/{cf_model}"

t0 = time.time()
try:
    r = requests.post(
        url,
        headers={"Authorization": f"Bearer {CF_TOKEN}"},
        json={"prompt": "a warm hand-painted market street, golden hour", "steps": 4},
        timeout=120,
    )
    data = r.json()
    img_b64 = data.get("result", {}).get("image")
    if img_b64:
        os.makedirs("outputs/smoke", exist_ok=True)
        with open("outputs/smoke/test.png", "wb") as f:
            f.write(base64.b64decode(img_b64))
        log("keyframes", cf_model, time.time() - t0, "ok",
            saved="outputs/smoke/test.png", bytes=len(img_b64))
    else:
        log("keyframes", cf_model, time.time() - t0, "error",
            response=str(data)[:300])
except Exception as e:
    log("keyframes", cf_model, time.time() - t0, "error", error=str(e))