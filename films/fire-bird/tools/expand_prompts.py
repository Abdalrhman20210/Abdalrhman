#!/usr/bin/env python3
"""Expand [TOKEN] placeholders in 03-shot-prompts.md using 02-character-bible.md.

Writes 03-shot-prompts-expanded.md with ready-to-paste prompts (STYLE appended
to every IMAGE line), 04-veo-prompts.md with one combined text-to-video prompt
per shot for Google Veo, and prints shot count and total duration.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BIBLE = ROOT / "02-character-bible.md"
SHOTS = ROOT / "03-shot-prompts.md"
OUT = ROOT / "03-shot-prompts-expanded.md"
VEO_OUT = ROOT / "04-veo-prompts.md"
BOARD_TEMPLATE = ROOT / "tools" / "prompt_board_template.html"
BOARD_OUT = ROOT / "prompt-board.html"

# Names of the characters as saved in Google Flow's character library.
FLOW_CHARACTERS = {
    "HALIMA": "حليمة", "JAMR-CHICK": "جمر فرخ", "JAMR-YOUNG": "جمر صغير",
    "JAMR-TEEN": "جمر شاب", "JAMR-REBORN": "جمر منبعث", "SALMA": "سلمى",
    "MUHALLAB": "مهلّب", "QIRWASH": "قرواش",
}

VEO_AUDIO = (
    "Audio: natural ambient sound effects only, no dialogue, no speech, "
    "no music, no subtitles, no on-screen text, no film borders."
)

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
    veo = [
        "# برومبتات Veo – برومبت واحد لكل لقطة",
        "",
        "> مولَّد تلقائياً بواسطة `tools/expand_prompts.py`. انسخ البرومبت كاملاً والصقه في Veo.",
        "> كل لقطة تخرج 8 ثوانٍ. الصوت فيها مؤثرات فقط، والحوار والتعليق الصوتي تضيفهما في المونتاج.",
        "> 👤 بجانب كل لقطة أسماء الشخصيات التي ترفقها من مكتبة الشخصيات في Flow قبل الإرسال.",
        "",
    ]
    veo_style = style.replace("film still, ", "").replace(", 16:9", "")
    shot_id, image_body, scene, duration = None, None, None, 0
    board = []
    shots, seconds = 0, 0
    started = False
    for line in lines:
        if line.startswith("## المشهد 1 "):
            started = True
        if not started:
            continue
        m = re.match(r"\*\*([\w\-]+)\*\* · (\d+)s", line)
        if m:
            shot_id = m.group(1)
            duration = int(m.group(2))
            shots += 1
            seconds += int(m.group(2))
        if line.startswith("- IMAGE:"):
            body = line[len("- IMAGE:"):].strip()
            cast = [v for k, v in FLOW_CHARACTERS.items() if f"[{k}]" in body]
            for name, desc in tokens.items():
                body = body.replace(f"[{name}]", desc)
            missing = re.findall(r"\[[A-Z\-]+\]", body)
            if missing:
                raise SystemExit(f"Unknown token(s) {missing} in: {line}")
            image_body = body
            out.append("- IMAGE:")
            out.append("```")
            out.append(f"{body}. {style}")
            out.append("```")
            continue
        if line.startswith("- MOTION:"):
            body = line[len("- MOTION:"):].strip()
            for name in tokens:
                body = body.replace(f"[{name}]", MOTION_NAMES.get(name.split("-")[0], "it"))
            prompt = f"Create a video: {image_body}. {body}. Style: {veo_style}. {VEO_AUDIO}"
            board.append({"id": shot_id, "scene": scene, "seconds": duration,
                          "cast": cast, "prompt": prompt})
            veo.append(f"**{shot_id}** · 👤 أرفق: {'، '.join(cast) if cast else 'لا شيء'}")
            veo.append("```")
            veo.append(prompt)
            veo.append("```")
            veo.append("")
            out.append("- MOTION:")
            out.append("```")
            out.append(body)
            out.append("```")
            continue
        if line.startswith("## "):
            scene = line[3:].strip()
            veo.append(line)
            veo.append("")
        out.append(line)
    data = json.dumps(board, ensure_ascii=False).replace("</", "<\\/")
    BOARD_OUT.write_text(
        BOARD_TEMPLATE.read_text(encoding="utf-8").replace("__SHOTS_JSON__", data),
        encoding="utf-8",
    )
    VEO_OUT.write_text("\n".join(veo) + "\n", encoding="utf-8")
    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"shots={shots} total={seconds}s ({seconds / 60:.1f} min) -> {OUT.name}")


if __name__ == "__main__":
    main()
