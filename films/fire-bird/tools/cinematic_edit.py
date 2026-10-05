#!/usr/bin/env python3
"""Cinematic edit for "The Fire Bird" clips.

Usage:
    python cinematic_edit.py "C:\\Users\\LAPTOP\\Downloads\\طائر النار"

Needs ffmpeg and ffprobe on PATH. What it does:
  1. Orders the clips. Files named by shot number (01-02.mp4, 05-03 take2.mp4)
     are sorted by shot. Otherwise it falls back to the timestamp Google Flow puts
     in the file name, then to the file date. The order is written to
     order.txt in the clips folder; edit that file and run again to reorder or
     drop clips.
  2. Grades every clip the same way: teal shadows, warm highlights, gentle
     contrast, vignette, fine film grain, 2.39:1 letterbox, 1920x1080 at 24fps.
  3. Joins clips with soft cross-dissolves, and with a dip to black whenever
     the scene number changes.
  4. Adds a fade in from black, an end title card, and an optional music bed
     (put music.mp3 or music.wav in the clips folder), then normalizes loudness
     for YouTube (-14 LUFS).

Output: <clips folder>/output/طائر_النار_مونتاج.mp4
"""
import argparse
import hashlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

W, H, FPS = 1920, 1080, 24
SCOPE_H = round(W / 2.39)          # visible picture height inside the letterbox
BAR = (H - SCOPE_H) // 2
DISSOLVE = 0.5                     # seconds, between shots of the same scene
DIP = 1.0                          # seconds, between scenes
TITLE = "طائر النار"
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}

GRADE = ",".join([
    f"scale={W}:{H}:force_original_aspect_ratio=increase",
    f"crop={W}:{H}",
    f"fps={FPS}",
    "eq=contrast=1.07:saturation=0.92:gamma=0.98",
    "colorbalance=rs=-0.05:gs=-0.01:bs=0.07:rm=0.02:bm=-0.02:rh=0.07:gh=0.02:bh=-0.07",
    "vignette=angle=PI/5",
    "noise=alls=5:allf=t",
    f"drawbox=x=0:y=0:w=iw:h={BAR}:color=black:t=fill",
    f"drawbox=x=0:y=ih-{BAR}:w=iw:h={BAR}:color=black:t=fill",
    "format=yuv420p",
])

FONT_CANDIDATES = [
    r"C:\Windows\Fonts\arialbd.ttf", r"C:\Windows\Fonts\arial.ttf",
    r"C:\Windows\Fonts\tahomabd.ttf", r"C:\Windows\Fonts\tahoma.ttf",
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
]


LOG = None


def fail(message):
    if LOG:
        try:
            LOG.write_text(message, encoding="utf-8")
            message += f"\n\nThis message was also saved to {LOG}"
        except OSError:
            pass
    sys.exit(message)


def run(cmd, cwd=None):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                       encoding="utf-8", errors="replace", cwd=cwd)
    if p.returncode != 0:
        fail("ffmpeg failed:\n" + " ".join(map(str, cmd)) + "\n" + p.stderr[-3000:])
    return p.stdout


def duration(path):
    out = run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
               "-of", "default=nw=1:nk=1", str(path)])
    return float(out.strip())


def has_audio(path):
    out = run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries",
               "stream=index", "-of", "csv=p=0", str(path)])
    return bool(out.strip())


def shot_id(name):
    m = re.search(r"(?<!\d)(\d{2})[-_ ](\d{2})(?!\d)", name)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    m = re.search(r"PC[-_ ]?(\d{2})", name, re.I)
    return f"PC-{m.group(1)}" if m else None


def flow_timestamp(name):
    m = re.search(r"(20\d{12})", name)
    return m.group(1) if m else None


def sort_key(path):
    sid = shot_id(path.stem)
    if sid:
        scene = 99 if sid.startswith("PC") else int(sid[:2])
        return (0, scene, sid, path.name)
    ts = flow_timestamp(path.stem)
    if ts:
        return (1, 0, ts, path.name)
    return (2, 0, f"{path.stat().st_mtime:020.6f}", path.name)


def scene_of(path):
    sid = shot_id(path.stem)
    return sid.split("-")[0] if sid else None


def load_order(folder, clips):
    order_file = folder / "order.txt"
    if order_file.exists():
        by_name = {c.name: c for c in clips}
        chosen = []
        for line in order_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and line in by_name:
                chosen.append(by_name[line])
        if chosen:
            print(f"Using order.txt ({len(chosen)} clips).")
            return chosen
    ordered = sorted(clips, key=sort_key)
    order_file.write_text(
        "# One file per line, top to bottom = order in the film.\n"
        "# Move lines to reorder, delete a line or start it with # to drop a clip,\n"
        "# then run the script again.\n" + "\n".join(c.name for c in ordered) + "\n",
        encoding="utf-8")
    print(f"Wrote {order_file} with {len(ordered)} clips.")
    return ordered


def find_font(user_font):
    for f in ([user_font] if user_font else []) + FONT_CANDIDATES:
        if f and Path(f).exists():
            return f
    return None


def prepare(clips, work, trim_head, trim_tail):
    prepared = []
    for i, src in enumerate(clips, 1):
        key = f"{src.name}|{src.stat().st_size}|{trim_head}|{trim_tail}|{GRADE}"
        dst = work / f"{hashlib.md5(key.encode('utf-8')).hexdigest()[:12]}.mp4"
        prepared.append(dst)
        if dst.exists() and dst.stat().st_mtime > src.stat().st_mtime:
            continue
        length = max(1.0, duration(src) - trim_head - trim_tail)
        cmd = ["ffmpeg", "-y", "-v", "error", "-ss", f"{trim_head}", "-t", f"{length}", "-i", str(src)]
        if has_audio(src):
            amap = ["-map", "0:a:0"]
        else:
            cmd += ["-f", "lavfi", "-t", f"{length}", "-i", "anullsrc=r=48000:cl=stereo"]
            amap = ["-map", "1:a:0"]
        cmd += ["-map", "0:v:0", *amap, "-vf", GRADE,
                "-af", "aresample=48000,aformat=channel_layouts=stereo",
                "-c:v", "libx264", "-preset", "medium", "-crf", "16",
                "-c:a", "aac", "-b:a", "192k", "-shortest", str(dst)]
        print(f"[{i}/{len(clips)}] grading {src.name}")
        run(cmd)
    return prepared


def title_card(work, font, seconds=6.0):
    dst = work / "title.mp4"
    opts = []
    if font:
        # Copy the font next to the work files so the filter never sees a
        # Windows drive letter (its colon breaks ffmpeg's option parsing).
        shutil.copyfile(font, work / "title_font.ttf")
        opts.append("fontfile=title_font.ttf")
    opts += [
        "text=" + TITLE, "fontsize=130", "fontcolor=0xF2C27B",
        "x=(w-text_w)/2", "y=(h-text_h)/2",
        # fade the title in over 1.2s and out over the last 1.4s
        "alpha=if(lt(t\\,1.2)\\,t/1.2\\,if(gt(t\\,4.6)\\,(6-t)/1.4\\,1))",
    ]
    vf = "drawtext=" + ":".join(opts) + ",format=yuv420p"
    run(["ffmpeg", "-y", "-v", "error",
         "-f", "lavfi", "-i", f"color=c=black:s={W}x{H}:r={FPS}:d={seconds}",
         "-f", "lavfi", "-t", f"{seconds}", "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", vf, "-c:v", "libx264", "-crf", "16", "-c:a", "aac", "-b:a", "192k",
         "-shortest", dst.name], cwd=work)
    return dst


def chain(durs, kinds):
    """Filters that join inputs 0..n-1 with xfade/acrossfade. Returns (filters, v, a, total)."""
    filters = []
    v, a, t = "[0:v]", "[0:a]", durs[0]
    for i in range(1, len(durs)):
        kind, d = kinds[i - 1]
        d = min(d, durs[i - 1] / 2, durs[i] / 2)
        t -= d
        filters.append(f"{v}[{i}:v]xfade=transition={kind}:duration={d:.3f}:offset={t:.3f}[v{i}]")
        filters.append(f"{a}[{i}:a]acrossfade=d={d:.3f}[a{i}]")
        v, a = f"[v{i}]", f"[a{i}]"
        t += durs[i]
    return filters, v, a, t


def join_group(work, parts, name):
    """Join one scene's shots with soft dissolves into an intermediate file."""
    dst = work / name
    if len(parts) == 1:
        return parts[0]
    durs = [duration(p) for p in parts]
    filters, v, a, _ = chain(durs, [("fade", DISSOLVE)] * (len(parts) - 1))
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for p in parts:
        cmd += ["-i", p.name]
    cmd += ["-filter_complex", ";".join(filters), "-map", v, "-map", a,
            "-c:v", "libx264", "-preset", "medium", "-crf", "16", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", dst.name]
    run(cmd, cwd=work)
    return dst


def assemble(work, parts, scenes, music, out):
    # Group consecutive shots of the same scene (at most 12 per group, which
    # keeps memory low on a laptop), join each group, then join the groups.
    groups, keys = [], []
    for part, scene in zip(parts, scenes):
        if groups and keys[-1] == scene and len(groups[-1]) < 12:
            groups[-1].append(part)
        else:
            groups.append([part])
            keys.append(scene)
    joined = []
    for g, group in enumerate(groups, 1):
        print(f"Joining scene part {g}/{len(groups)} ({len(group)} shots)")
        joined.append(join_group(work, group, f"group_{g:03d}.mp4"))

    durs = [duration(p) for p in joined]
    kinds = [("fade", DISSOLVE) if keys[i] == keys[i - 1] else ("fadeblack", DIP)
             for i in range(1, len(joined))]
    filters, v, a, total = chain(durs, kinds) if len(joined) > 1 else ([], "[0:v]", "[0:a]", durs[0])
    filters.append(f"{v}fade=t=in:st=0:d=1.5,fade=t=out:st={total - 2:.3f}:d=2[vout]")
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats"]
    for p in joined:
        cmd += ["-i", p.name]
    if music:
        cmd += ["-stream_loop", "-1", "-i", str(music)]
        m = len(joined)
        filters.append(f"[{m}:a]atrim=0:{total:.3f},volume=0.35,"
                       f"afade=t=in:st=0:d=3,afade=t=out:st={total - 4:.3f}:d=4[mus]")
        filters.append(f"{a}[mus]amix=inputs=2:duration=first:normalize=0[mix]")
        a = "[mix]"
    filters.append(f"{a}afade=t=in:st=0:d=1.5,afade=t=out:st={total - 2:.3f}:d=2,"
                   f"loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    cmd += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    print(f"Assembling the film, about {total / 60:.1f} minutes...")
    p = subprocess.run(cmd, cwd=work)
    if p.returncode != 0:
        fail("ffmpeg failed while assembling the film.")
    return total


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("folder", help="folder that holds the clips")
    ap.add_argument("--music", help="music file (default: music.mp3/.wav/.m4a in the folder)")
    ap.add_argument("--no-title", action="store_true", help="skip the end title card")
    ap.add_argument("--font", help="font file for the title (must support Arabic)")
    ap.add_argument("--trim-head", type=float, default=0.0, help="seconds cut from the start of every clip")
    ap.add_argument("--trim-tail", type=float, default=0.25, help="seconds cut from the end of every clip")
    args = ap.parse_args()

    for tool in ("ffmpeg", "ffprobe"):
        if not shutil.which(tool):
            fail(f"{tool} was not found. On Windows run:  winget install Gyan.FFmpeg  then open a new terminal.")

    folder = Path(args.folder).expanduser().resolve()
    global LOG
    (folder / "output").mkdir(exist_ok=True)
    LOG = folder / "output" / "error_log.txt"
    clips = [p for p in folder.iterdir() if p.suffix.lower() in VIDEO_EXT and p.is_file()]
    if not clips:
        fail(f"No video files in {folder}")
    clips = load_order(folder, clips)

    work = folder / "output" / "_work"
    work.mkdir(parents=True, exist_ok=True)
    parts = prepare(clips, work, args.trim_head, args.trim_tail)
    scenes = [scene_of(c) for c in clips]

    if not args.no_title:
        font = find_font(args.font)
        if not font:
            print("No Arabic font found; the title card uses ffmpeg's default font.")
        parts.append(title_card(work, font))
        scenes.append("title")

    music = Path(args.music) if args.music else next(
        (folder / n for n in ("music.mp3", "music.wav", "music.m4a") if (folder / n).exists()), None)
    if music:
        print(f"Music bed: {music.name}")

    out = folder / "output" / "طائر_النار_مونتاج.mp4"
    total = assemble(work, parts, scenes, music, out)
    print(f"\nDone: {out}\nLength: {int(total // 60)}:{int(total % 60):02d}")
    print("Graded clips are cached in output/_work; delete that folder to regrade everything.")
    if hasattr(os, "startfile"):
        os.startfile(out.parent)


if __name__ == "__main__":
    try:
        main()
    except SystemExit:
        raise
    except Exception as e:  # keep the window readable instead of a bare traceback
        import traceback
        fail("Unexpected error:\n" + traceback.format_exc())
