# "እጆቿ የገነቡት ሕልም", The Dream Her Hands Helped Build

A 68-second AI-generated short film about a mother's quiet support building her daughter's dreams. Narration in Amharic, with English subtitles.

## The Pipeline

This repository contains a fully reproducible AI content generation pipeline. One JSON file (`storyboard.json`) acts as the contract for all stages.

**To run the entire pipeline from scratch (assuming API keys are in `.env`):**

```bash
python pipeline/validate_storyboard.py
python pipeline/narration.py
python pipeline/keyframes.py
# Videos are generated on Kaggle (see ARCHITECTURE.md)
python pipeline/assemble.py --aspect 9x16
python pipeline/assemble.py --aspect 16x9
```
