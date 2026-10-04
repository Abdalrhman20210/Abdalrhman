#!/usr/bin/env python3
"""Expand [TOKEN] placeholders in 03-shot-prompts.md using 02-character-bible.md.

Writes 03-shot-prompts-expanded.md with ready-to-paste prompts (STYLE appended
to every IMAGE line) and prints shot count and total duration.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIBLE = ROOT / "02-character-bible.md"
SHOTS = ROOT / "03-shot-prompts.md"
OUT = ROOT / "03-shot-prompts-expanded.md"

# Video tools already see the character in the start frame, so motion prompts
# use short nouns instead of the full description.
MOTION_NAMES = {
    "HALIMA": "the woman", "SALMA": "the girl", "JAMR": "the phoenix",
    "EGG": "the egg", "MUHALLAB": "the prince", "QIRWASH": "the merchant",
    "SOLDIERS": "the soldiers", "OASIS": "the oasis", "TENT": "the tent",
    "PALACE": "the palace", "SQUARE": "the square",
}


def load_tokens():
    text = BIBLE.read_text(encoding="utf-8")
    tokens = {}
    for block in re.findall(r"```\n(.*?)\n```", text, re.S):
        m = re.match(r"\[([A-Z\-]+)\]\s+(.*)", block.strip(), re.S)
        if m:
            tokens[m.group(1)] = m.group(2).strip()
    style = re.search(r"```\nSTYLE: (.*?)\n```", text, re.S).group(1).strip()
    negative = re.search(r"```\nNEGATIVE: (.*?)\n```", text, re.S).group(1).strip()
    return tokens, style, negative


def main():
    tokens, style, negative = load_tokens()
    lines = SHOTS.read_text(encoding="utf-8").splitlines()
    out = [
        "# البرومبتات الموسّعة – جاهزة للنسخ",
        "",
        "> هذا الملف مولَّد تلقائياً من `03-shot-prompts.md` بواسطة `tools/expand_prompts.py`. لا تعدّله يدوياً.",
        "",
        f"**NEGATIVE (لكل الصور):** `{negative}`",
        "",
    ]
    shots, seconds = 0, 0
    started = False
    for line in lines:
        if line.startswith("## المشهد 1 "):
            started = True
        if not started:
            continue
        m = re.match(r"\*\*([\w\-]+)\*\* · (\d+)s", line)
        if m:
            shots += 1
            seconds += int(m.group(2))
        if line.startswith("- IMAGE:"):
            body = line[len("- IMAGE:"):].strip()
            for name, desc in tokens.items():
                body = body.replace(f"[{name}]", desc)
            missing = re.findall(r"\[[A-Z\-]+\]", body)
            if missing:
                raise SystemExit(f"Unknown token(s) {missing} in: {line}")
            out.append("- IMAGE:")
            out.append("```")
            out.append(f"{body}. {style}")
            out.append("```")
            continue
        if line.startswith("- MOTION:"):
            body = line[len("- MOTION:"):].strip()
            for name in tokens:
                body = body.replace(f"[{name}]", MOTION_NAMES.get(name.split("-")[0], "it"))
            out.append("- MOTION:")
            out.append("```")
            out.append(body)
            out.append("```")
            continue
        out.append(line)
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"shots={shots} total={seconds}s ({seconds / 60:.1f} min) -> {OUT.name}")


if __name__ == "__main__":
    main()
