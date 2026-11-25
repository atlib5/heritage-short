"""Assemble the Radio Cut: Black screen, narration, burned-in English subtitles."""
import json
import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent
STORYBOARD_PATH = ROOT / "storyboard.json"
AUDIO_DIR = ROOT / "outputs" / "audio"
OUT_DIR = ROOT / "outputs" / "video"
OUT_DIR.mkdir(parents=True, exist_ok=True)

# Path to ffmpeg (Windows uses ffmpeg.exe, Linux/Mac use ffmpeg)
FFMPEG = "ffmpeg" # Change to absolute path if needed, e.g., "C:\\ffmpeg\\bin\\ffmpeg.exe"

def main():
    with open(STORYBOARD_PATH, encoding="utf-8") as f:
        storyboard = json.load(f)

    shots = storyboard["shots"]
    
    # 1. Generate an SRT subtitle file from the English narration
    srt_path = OUT_DIR / "subtitles.srt"
    current_time = 0.0
    
    with open(srt_path, "w", encoding="utf-8") as f:
        for i, shot in enumerate(shots):
            duration = shot["duration_s"]
            start = current_time
            end = start + duration
            
            # Format time as HH:MM:SS,mmm
            def fmt_time(sec):
                h = int(sec // 3600)
                m = int((sec % 3600) // 60)
                s = int(sec % 60)
                ms = int((sec - int(sec)) * 1000)
                return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"
                
            text = shot.get("narration_en", "")
            if "dialogue" in shot:
                text += f"\n({shot['dialogue']['text_en']})"
                
            if text.strip():
                f.write(f"{i+1}\n")
                f.write(f"{fmt_time(start)} --> {fmt_time(end)}\n")
                f.write(f"{text}\n\n")
                
            current_time += duration
            
    print(f"✓ Created subtitles.srt")
    
    # 2. Build the FFmpeg command to mix audio and create video
    # We will use a concat demuxer approach via a text file for the audio parts
    # First, create the concatenated audio file
    audio_concat_txt = OUT_DIR / "audio_concat.txt"
    with open(audio_concat_txt, "w", encoding="utf-8") as f:
        for shot in shots:
            shot_id = shot["id"]
            duration = shot["duration_s"]
            
            # If there is narration, use it. If there's dialogue, mix it.
            # For simplicity in the radio cut, we prioritize mother dialogue if it exists
            # (In the final edit, we will layer them with proper timing)
            audio_file = None
            if "dialogue" in shot:
                audio_file = AUDIO_DIR / f"{shot_id}_mother.wav"
            elif shot.get("narration"):
                audio_file = AUDIO_DIR / f"{shot_id}_narrator.wav"
                
            if audio_file and audio_file.exists():
                # Pad audio to match exact duration so the timeline is perfect
                padded_file = AUDIO_DIR / f"{shot_id}_padded.wav"
                cmd = [
                    FFMPEG, "-y", "-i", str(audio_file), 
                    "-af", f"apad,atrim=0:{duration}", 
                    str(padded_file)
                ]
                subprocess.run(cmd, capture_output=True)
                f.write(f"file '{padded_file.absolute().as_posix()}'\n")
            else:
                # If no audio, generate silence for that duration
                silence_file = AUDIO_DIR / f"{shot_id}_silence.wav"
                cmd = [
                    FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono", 
                    "-t", str(duration), str(silence_file)
                ]
                subprocess.run(cmd, capture_output=True)
                f.write(f"file '{silence_file.absolute().as_posix()}'\n")

    # 3. Create the final video
    output_video = OUT_DIR / "radio_cut.mp4"
    total_duration = sum(s["duration_s"] for s in shots)
    
    print("Rendering video with FFmpeg...")
    cmd = [
        FFMPEG, "-y",
        "-f", "lavfi", "-i", f"color=c=black:s=1080x1920:d={total_duration}:r=24",
        "-f", "concat", "-safe", "0", "-i", str(audio_concat_txt),
                "-vf", "subtitles=subtitles.srt:force_style='FontName=Arial,FontSize=18,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,Outline=2'",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac",
        "-shortest", str(output_video)
    ]
    
    subprocess.run(cmd, cwd=OUT_DIR, capture_output=False)
    print(f"✓ Radio Cut complete: {output_video}")

if __name__ == "__main__":
    main()