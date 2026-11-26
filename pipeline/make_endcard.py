from PIL import Image, ImageDraw, ImageFont
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUT_DIR = ROOT / "outputs" / "keyframes"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Create a dark warm brown background (1080x1920 vertical)
img = Image.new('RGB', (1080, 1920), color='#2a1e16')
draw = ImageDraw.Draw(img)

# Use exact Windows system paths for fonts that support Amharic
try:
    # Nyala is standard on Windows for Ethiopic scripts
    font_title = ImageFont.truetype("C:/Windows/Fonts/nyala.ttf", 120)
    font_en = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 60)
    font_ai = ImageFont.truetype("C:/Windows/Fonts/nyala.ttf", 50)
except Exception as e:
    print(f"Font loading failed: {e}")
    # Fallback to Ebrima if Nyala is missing
    font_title = ImageFont.truetype("C:/Windows/Fonts/ebrima.ttf", 120)
    font_en = ImageFont.truetype("C:/Windows/Fonts/ebrima.ttf", 60)
    font_ai = ImageFont.truetype("C:/Windows/Fonts/ebrima.ttf", 50)

title_am = "እጆቿ የገነቡት ሕልም"
title_en = "The Dream Her Hands Helped Build"
ai_text = "Made with AI\nበAI እገዛ የተዘጋጀ"

def draw_centered(text, font, y_offset):
    # Handle multi-line text
    lines = text.split('\n')
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        text_width = bbox[2] - bbox[0]
        x = (1080 - text_width) / 2
        draw.text((x, y_offset + (i * 60)), line, font=font, fill="#f4e8d1")

# Draw text in the center (much larger now)
draw_centered(title_am, font_title, 700)
draw_centered(title_en, font_en, 880)
draw_centered(ai_text, font_ai, 1500)

# Save it as shot_12.png
img.save(OUT_DIR / "endcard.png")
print("✓ Created AI End Card: outputs/keyframes/endcard.png")