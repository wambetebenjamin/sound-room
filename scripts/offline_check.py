#!/usr/bin/env python3
"""
offline_check.py — what will actually work when there is no internet?

Run this on the wifi you have, before you rely on the repo somewhere else.
Exits non-zero if anything needed for the live path is missing.

Usage:
    python3 scripts/offline_check.py            # human readable (default)
    python3 scripts/offline_check.py --strict   # treat warnings as failures
"""
from __future__ import annotations

import argparse
import importlib.util
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OK, WARN, FAIL, SKIP = "OK", "WARN", "FAIL", "SKIP"
ICON = {OK: "✅", WARN: "⚠️ ", FAIL: "❌", SKIP: "– "}

results: list[tuple[str, str, str]] = []


def add(status: str, name: str, detail: str = "") -> None:
    results.append((status, name, detail))


def check_python() -> None:
    required = ["numpy", "scipy", "soundfile", "pyloudnorm", "librosa"]
    optional = ["imageio_ffmpeg"]
    for mod in required:
        if importlib.util.find_spec(mod):
            add(OK, f"python:{mod}")
        else:
            add(FAIL, f"python:{mod}", "pip install -r requirements-music.txt")
    for mod in optional:
        if importlib.util.find_spec(mod):
            add(OK, f"python:{mod}")
        else:
            add(WARN, f"python:{mod}", "needed to decode .m4a/.aac beds")


def check_ffmpeg() -> None:
    if shutil.which("ffmpeg"):
        add(OK, "ffmpeg", "system binary")
        return
    try:
        import imageio_ffmpeg
        add(OK, "ffmpeg", f"bundled: {Path(imageio_ffmpeg.get_ffmpeg_exe()).name}")
    except Exception:
        add(WARN, "ffmpeg", "no system ffmpeg and no imageio-ffmpeg")


def check_files() -> None:
    for rel, label in [
        ("scripts/analyze_audio.py", "analyzer"),
        ("scripts/enhance_audio.py", "mastering chain"),
        ("scripts/build_original_beat.py", "original beat synth"),
        ("scripts/build_voice_track.py", "voice→track"),
        ("tools/Amapiano-Beatpad/Assets", "beatpad loops"),
        ("tools/ambientpad/pads", "worship pads"),
    ]:
        p = ROOT / rel
        add(OK if p.exists() else WARN, f"file:{label}", rel if not p.exists() else "")


def check_strudel() -> None:
    """Strudel pulls its engine from a CDN — the one genuine offline gap."""
    f = ROOT / "tools/strudel-claude/src/hooks/use-strudel.ts"
    if not f.exists():
        add(SKIP, "strudel:engine", "not cloned")
        return
    text = f.read_text(errors="replace")
    if "unpkg.com" in text or "cdn" in text.lower():
        add(FAIL, "strudel:engine", "loads from unpkg — silent offline; vendor @strudel/repl")
    else:
        add(OK, "strudel:engine", "local")


def check_models() -> None:
    """Neural weights must be cached before going offline."""
    torch_cache = Path.home() / ".cache/torch/hub/checkpoints"
    hf_cache = Path.home() / ".cache/huggingface"
    demucs = any(torch_cache.glob("*htdemucs*")) if torch_cache.exists() else False
    musicgen = hf_cache.exists() and any(hf_cache.glob("**/musicgen*"))
    add(OK if demucs else WARN, "model:demucs",
        "" if demucs else "not cached — stem separation will need internet (~300 MB)")
    add(OK if musicgen else WARN, "model:musicgen",
        "" if musicgen else "not cached — MusicGen needs ~6 GB (not recommended live)")


def check_tools() -> None:
    tools = ROOT / "tools"
    if not tools.exists():
        add(FAIL, "tools/", "run ./scripts/setup-tools.sh")
        return
    for d in sorted(p.name for p in tools.iterdir() if p.is_dir()):
        add(OK, f"tool:{d}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true", help="warnings count as failures")
    args = ap.parse_args()

    check_python()
    check_ffmpeg()
    check_files()
    check_tools()
    check_strudel()
    check_models()

    width = max(len(n) for _, n, _ in results) + 2
    for status, name, detail in results:
        print(f"{ICON[status]} {name:<{width}}{detail}")

    fails = sum(1 for s, _, _ in results if s == FAIL)
    warns = sum(1 for s, _, _ in results if s == WARN)
    print(f"\n{fails} blocking · {warns} warning(s)")

    live_ready = fails == 0 and not (args.strict and warns)
    print("Live path (pads + pre-rendered beats + our scripts): "
          + ("READY offline" if live_ready else "NOT ready — fix the ❌ items"))
    return 0 if live_ready else 1


if __name__ == "__main__":
    raise SystemExit(main())
