"""Validate storyboard.json against schema/storyboard.schema.json.
Run before every pipeline execution. Exits non-zero on failure."""
import json
import sys
from pathlib import Path
from jsonschema import validate, ValidationError

ROOT = Path(__file__).parent.parent
SCHEMA_PATH = ROOT / "schema" / "storyboard.schema.json"
STORYBOARD_PATH = ROOT / "storyboard.json"

def main():
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        schema = json.load(f)
    with open(STORYBOARD_PATH, encoding="utf-8") as f:
        storyboard = json.load(f)

    try:
        validate(instance=storyboard, schema=schema)
        print("✓ Schema validation passed")
    except ValidationError as e:
        print(f"✗ Schema validation failed: {e.message}")
        print(f"  Path: {' -> '.join(str(p) for p in e.absolute_path)}")
        sys.exit(1)

    shots = storyboard["shots"]
    total = sum(s["duration_s"] for s in shots)
    print(f"✓ {len(shots)} shots, total duration {total}s")

    if not (60 <= total <= 90):
        print(f"✗ Total duration {total}s is outside 60-90s")
        sys.exit(1)

    # Character reference check
    char_ids = {c["id"] for c in storyboard["characters"]}
    for s in shots:
        for cid in s.get("characters", []):
            if cid not in char_ids:
                print(f"✗ {s['id']}: references unknown character '{cid}'")
                sys.exit(1)

    # Narration timing check (rough: 3 words/sec max)
    for s in shots:
        words = len(s["narration"].split())
        max_words = s["duration_s"] * 3.0
        if words > max_words:
            print(f"⚠ {s['id']}: {words} words in {s['duration_s']}s (max ~{max_words:.0f})")
            
        # Dialogue timing check
        if "dialogue" in s:
            d_words = len(s["dialogue"].get("text_am", "").split())
            if d_words > (s["duration_s"] * 4.0): # dialogue can be a bit faster
                print(f"⚠ {s['id']} dialogue: {d_words} words might be too fast for {s['duration_s']}s")

    print("✓ All checks passed")

if __name__ == "__main__":
    main()