#!/usr/bin/env python3
"""
backing_from_chart.py — read a worship chord chart, generate a matching backing.

Reads an .onsong / ChordPro file (e.g. from tools/worship-charts, which you hold
licences for), pulls out **key, tempo and the chord progression**, and renders an
acoustic worship backing in exactly that key and tempo.

It deliberately reads only metadata and chord symbols. Lyrics and melody — the
parts that remain the publisher's copyright — are never read into the output.

Usage:
    python3 scripts/backing_from_chart.py "tools/worship-charts/10000 Reasons.onsong" \
        -o out/music/chart-backing.wav --bars 12
    python3 scripts/backing_from_chart.py --list | head -40
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

CHART_DIR = Path(__file__).resolve().parent.parent / "tools/worship-charts"
CHORD_RE = re.compile(r"\[([A-G][#b]?(?:maj|min|sus|add|dim|aug|m|M)?\d*(?:/[A-G][#b]?)?)\]")
SECTION_RE = re.compile(r"^([A-Za-z][A-Za-z0-9 ]{0,24}):\s*$")


def metadata(text: str) -> dict:
    meta = {}
    for line in text.splitlines()[:20]:
        m = re.match(r"^([A-Za-z][A-Za-z ()/]+):\s*(.*)$", line)
        if m:
            meta[m.group(1).strip().lower()] = m.group(2).strip()
    return meta


def key_of(meta: dict) -> str:
    raw = meta.get("key", "").strip()
    m = re.search(r"\[?([A-G][#b]?)", raw)
    base = m.group(1) if m else "G"
    if re.search(r"\bm(?!aj)", raw.replace(base, "")) or raw.endswith("m"):
        return base + "m"
    return base


def tempo_of(meta: dict) -> float:
    raw = re.sub(r"[^0-9.]", "", str(meta.get("tempo", "")))
    try:
        t = float(raw)
    except ValueError:
        return 72.0
    return t if 40 <= t <= 200 else 72.0


def progression(text: str, limit: int = 4) -> list[str]:
    """Chords from the first section that has any (usually the chorus)."""
    sections: dict[str, list[str]] = {}
    current = None
    for line in text.splitlines():
        head = SECTION_RE.match(line.strip())
        if head:
            current = head.group(1).strip()
            sections.setdefault(current, [])
            continue
        if current:
            sections[current].extend(CHORD_RE.findall(line))

    for preferred in ("Chorus", "Verse 1", "Verse", "Pre-Chorus", "Intro", "Tag"):
        for name, chords in sections.items():
            if name.lower().startswith(preferred.lower()) and chords:
                return dedupe(chords)[:limit]

    # fallback: whatever the first section with chords is
    for chords in sections.values():
        if chords:
            return dedupe(chords)[:limit]
    return []


def dedupe(chords: list[str]) -> list[str]:
    out: list[str] = []
    for c in chords:
        if not out or out[-1] != c:
            out.append(c)
    return out


def read_chart(path: Path) -> dict:
    text = path.read_text(errors="replace")
    meta = metadata(text)
    return {
        "file": path.name,
        "title": meta.get("title", path.stem),
        "artist": meta.get("artist", ""),
        "key": key_of(meta),
        "tempo": tempo_of(meta),
        "progression": progression(text),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("chart", nargs="?", help="path to a .onsong / ChordPro file")
    ap.add_argument("-o", "--output")
    ap.add_argument("--bars", type=int, default=12)
    ap.add_argument("--list", action="store_true", help="list available charts")
    ap.add_argument("--json", action="store_true", help="print parsed data only")
    args = ap.parse_args()

    if args.list:
        charts = sorted(CHART_DIR.glob("*.onsong"))
        print(f"{len(charts)} charts in {CHART_DIR}")
        for c in charts[:40]:
            print("  " + c.stem)
        return 0

    if not args.chart:
        ap.error("provide a chart path (or --list)")

    info = read_chart(Path(args.chart))
    if not info["progression"]:
        print(f"No chord symbols found in {info['file']}", file=sys.stderr)
        return 1

    if args.json or not args.output:
        print(json.dumps(info, indent=2))
        if not args.output:
            return 0

    # import here so --list / --json stay fast
    from build_worship_arrangement import SR, build
    import soundfile as sf

    print(f"{info['title']} — {info['artist']}")
    print(f"key {info['key']} · {info['tempo']:g} BPM · {info['progression']}")

    audio = build(info["key"], info["tempo"], args.bars, SR, chords=info["progression"])
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    sf.write(args.output, audio, SR, subtype="PCM_24")
    print(f"wrote {args.output} · {len(audio)/SR:.2f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
