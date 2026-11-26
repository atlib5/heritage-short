"""Final assembly: video + narration + (music, ambience, SFX ducked under voice)
+ burned-in subtitles + 'Made with AI' end card. Exports 9x16 or 16x9.

Usage:
    python pipeline/assemble.py                 # vertical 9:16
    python pipeline/assemble.py --aspect 16x9   # horizontal

Optional audio files (put in outputs/audio/):
    music.wav|mp3|flac|m4a      score (ducked under the voice)
    ambience.wav|mp3|flac|m4a   room/market/wind tone (quiet, steady)
Optional per-shot sound effects in storyboard.json:
    "sfx": [{"file": "outputs/audio/sfx/door.wav", "at_s": 1.5, "volume": 0.7}]
End card image: outputs/keyframes/endcard.png (made by make_endcard.py)
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STORYBOARD_PATH = ROOT / "storyboard.json"
AUDIO_DIR = ROOT / "outputs" / "audio"
IMG_DIR = ROOT / "outputs" / "keyframes"
VIDEO_DIR = ROOT / "outputs" / "videos"   # real Wan 2.2 clips: <shot_id>.mp4
OUT_DIR = ROOT / "outputs" / "video"

FFMPEG, FFPROBE = "ffmpeg", "ffprobe"
FPS = 24
ENDCARD_IMG = IMG_DIR / "endcard.png"
ENDCARD_S = 3.0
ENDCARD_BG = "0x2a1e16"
SIZES = {"9x16": (1080, 1920), "16x9": (1920, 1080)}
SUB_STYLE = {
    "9x16": "FontSize=9,MarginV=45",
    "16x9": "FontSize=14,MarginV=15",
}


def run(cmd, **kw):
    """Run a command; on failure print FFmpeg's real error and stop (no silent failures)."""
    cmd = [str(c) for c in cmd]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", **kw)
    if r.returncode != 0:
        print("\n✗ COMMAND FAILED:\n ", " ".join(cmd))
        print("--- ffmpeg says ---\n" + r.stderr[-2000:])
        sys.exit(1)
    return r


def duration_of(path):
    r = subprocess.run([FFPROBE, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=nw=1:nk=1", str(path)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def fmt_time(sec):
    total_ms = int(round(sec * 1000))
    h, rem = divmod(total_ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def find_audio(stem):
    for ext in (".wav", ".mp3", ".flac", ".m4a"):
        p = AUDIO_DIR / f"{stem}{ext}"
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------- video
ENC = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
       "-pix_fmt", "yuv420p", "-r", FPS, "-an"]


def make_clip(shot_id, dur, W, H, tmp):
    """Return a clip of EXACTLY `dur` seconds at WxH, FPS, h264 (all clips identical
    so the concat step can never break)."""
    out = tmp / f"{shot_id}_clip.mp4"
    fit = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"
    real = VIDEO_DIR / f"{shot_id}.mp4"
    img = IMG_DIR / f"{shot_id}.png"

    if real.exists():
        print(f"  {shot_id}: real video")
        vf = f"{fit},fps={FPS},tpad=stop_mode=clone:stop_duration={dur}"
        run([FFMPEG, "-y", "-i", real, "-vf", vf, "-t", dur, *ENC, out])
    elif img.exists():
        print(f"  {shot_id}: Ken Burns on keyframe")
        frames = int(round(dur * FPS))
        vf = (f"scale={W*2}:{H*2}:force_original_aspect_ratio=increase,crop={W*2}:{H*2},"
              f"zoompan=z='1+0.12*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d=1:s={W}x{H}:fps={FPS}")
        run([FFMPEG, "-y", "-loop", "1", "-framerate", FPS, "-i", img,
             "-vf", vf, "-frames:v", frames, *ENC, out])
    else:
        print(f"  ⚠ {shot_id}: no media, using black")
        run([FFMPEG, "-y", "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}",
             "-t", dur, *ENC, out])
    return out


def make_endcard_clip(W, H, tmp):
    out = tmp / "endcard_clip.mp4"
    if not ENDCARD_IMG.exists():
        print(f"✗ {ENDCARD_IMG} not found. Run: python pipeline/make_endcard.py")
        sys.exit(1)
    # fit (not crop) so the text is never cut off, even in 16:9
    vf = (f"scale={W}:{H}:force_original_aspect_ratio=decrease,"
          f"pad={W}:{H}:(ow-iw)/2:(oh-ih)/2:color={ENDCARD_BG},fps={FPS},"
          f"fade=t=in:st=0:d=0.5")
    run([FFMPEG, "-y", "-loop", "1", "-framerate", FPS, "-i", ENDCARD_IMG,
         "-vf", vf, "-t", ENDCARD_S, *ENC, out])
    return out


# ---------------------------------------------------------------- voice
def make_voice(shot, dur, tmp):
    """Narration/dialogue for one shot, 48 kHz stereo, padded/trimmed to `dur`."""
    sid = shot["id"]
    src = None
    if "dialogue" in shot and (AUDIO_DIR / f"{sid}_mother.wav").exists():
        src = AUDIO_DIR / f"{sid}_mother.wav"
    elif (AUDIO_DIR / f"{sid}_narrator.wav").exists():
        src = AUDIO_DIR / f"{sid}_narrator.wav"

    out = tmp / f"{sid}_voice.wav"
    if src:
        d = duration_of(src)
        if d > dur + 0.05:
            print(f"  ⚠ {sid}: narration is {d:.1f}s but shot is {dur}s, it will be CUT OFF. "
                  f"Raise duration_s or shorten the line.")
        run([FFMPEG, "-y", "-i", src, "-af",
             "aresample=48000,aformat=channel_layouts=stereo,apad", "-t", dur, out])
    else:
        run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", dur, out])
    return out


def concat_list(paths, list_file):
    with open(list_file, "w", encoding="utf-8") as f:
        for p in paths:
            f.write(f"file '{Path(p).resolve().as_posix()}'\n")


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--aspect", choices=SIZES, default="9x16")
    args = ap.parse_args()
    W, H = SIZES[args.aspect]

    tmp = OUT_DIR / f"tmp_{args.aspect}"
    tmp.mkdir(parents=True, exist_ok=True)

    with open(STORYBOARD_PATH, encoding="utf-8") as f:
        shots = json.load(f)["shots"]

    durs = [float(s["duration_s"]) for s in shots]
    total = sum(durs) + ENDCARD_S

    # 1. subtitles (end card has none)
    t = 0.0
    with open(tmp / "subtitles.srt", "w", encoding="utf-8") as f:
        n = 0
        for shot, d in zip(shots, durs):
            text = shot.get("narration_en", "")
            if "dialogue" in shot:
                text += f"\n({shot['dialogue']['text_en']})"
            if text.strip():
                n += 1
                f.write(f"{n}\n{fmt_time(t)} --> {fmt_time(t + d - 0.05)}\n{text.strip()}\n\n")
            t += d
    print("✓ subtitles.srt")

    # 2. picture: one identical-format clip per shot, then the end card
    print("Building clips...")
    clips = [make_clip(s["id"], d, W, H, tmp) for s, d in zip(shots, durs)]
    clips.append(make_endcard_clip(W, H, tmp))
    concat_list(clips, tmp / "video_concat.txt")

    # 3. voice track (same length as picture, silence under the end card)
    voices = [make_voice(s, d, tmp) for s, d in zip(shots, durs)]
    end_sil = tmp / "endcard_silence.wav"
    run([FFMPEG, "-y", "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-t", ENDCARD_S, end_sil])
    voices.append(end_sil)
    concat_list(voices, tmp / "voice_concat.txt")
    voice_wav = tmp / "voice.wav"
    run([FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", tmp / "voice_concat.txt",
         "-c", "copy", voice_wav])

    # 4. mix: voice + ducked music + quiet ambience + SFX
    inputs = ["-f", "concat", "-safe", "0", "-i", tmp / "video_concat.txt", "-i", voice_wav]
    filters = ["[1:a]asplit=2[vo][sc]"]
    mix = ["[vo]"]
    idx = 2
    STEREO = "aresample=48000,aformat=channel_layouts=stereo"

    music = find_audio("music")
    if music:
        print(f"Music: {music.name}")
        inputs += ["-stream_loop", "-1", "-i", music]
        filters.append(f"[{idx}:a]{STEREO},atrim=0:{total},"
                       f"afade=t=out:st={total-2.5}:d=2.5,volume=0.8[m]")
        filters.append("[m][sc]sidechaincompress=threshold=0.02:ratio=6:"
                       "attack=300:release=1500[md]")
        mix.append("[md]")
        idx += 1
    else:
        # sidechain label must be consumed, so route it to a null sink
        filters[0] = "[1:a]anull[vo]"
        print("(no outputs/audio/music.* found, no music)")

    amb = find_audio("ambience")
    if amb:
        print(f"Ambience: {amb.name}")
        inputs += ["-stream_loop", "-1", "-i", amb]
        filters.append(f"[{idx}:a]{STEREO},atrim=0:{total},volume=0.25,"
                       f"afade=t=in:d=1,afade=t=out:st={total-1.5}:d=1.5[a]")
    else:
        print("(no ambience.* found, using a soft low room-tone fallback)")
        inputs += ["-f", "lavfi", "-i", "anoisesrc=color=brown:sample_rate=48000:amplitude=0.5"]
        filters.append(f"[{idx}:a]lowpass=f=600,atrim=0:{total},volume=0.06,"
                       f"aformat=channel_layouts=stereo[a]")
    mix.append("[a]")
    idx += 1

    # per-shot SFX
    offset = 0.0
    for shot, d in zip(shots, durs):
        for sfx in shot.get("sfx", []):
            p = ROOT / sfx["file"]
            if not p.exists():
                print(f"  ⚠ SFX not found: {p}")
                continue
            ms = int((offset + float(sfx.get("at_s", 0))) * 1000)
            vol = float(sfx.get("volume", 0.7))
            inputs += ["-i", p]
            filters.append(f"[{idx}:a]{STEREO},adelay={ms}|{ms},volume={vol},"
                           f"apad=whole_dur={total}[s{idx}]")
            mix.append(f"[s{idx}]")
            print(f"  SFX {p.name} at {offset + float(sfx.get('at_s', 0)):.1f}s")
            idx += 1
        offset += d

    # every input is `total` long, so amix never rescales mid-film
    filters.append("".join(mix) +
                   f"amix=inputs={len(mix)}:duration=first:dropout_transition=0,"
                   f"loudnorm=I=-14:TP=-1.0:LRA=11,atrim=0:{total}[aout]")

    style = ("FontName=Arial,PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,"
             "BorderStyle=1,Outline=2,Shadow=0,Alignment=2," + SUB_STYLE[args.aspect])
    filters.append(f"[0:v]subtitles=subtitles.srt:force_style='{style}'[vout]")

    final = OUT_DIR / f"heritage_short_{args.aspect}.mp4"
    print("Mixing and rendering...")
    run([FFMPEG, "-y", *inputs, "-filter_complex", ";".join(filters),
         "-map", "[vout]", "-map", "[aout]",
         "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
         "-r", FPS, "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
         "-movflags", "+faststart", "-t", total, final], cwd=tmp)
    print(f"✓ FINAL FILM READY: {final}  ({duration_of(final):.1f}s)")


if __name__ == "__main__":
    main()