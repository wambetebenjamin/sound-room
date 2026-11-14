# CLAUDE.md

This file mirrors [`AGENTS.md`](./AGENTS.md), which is the **canonical** source of
instructions for this repo. Read it for full detail, tool versions, and gotchas. If you
change one file, change both.

@AGENTS.md

---

## Summary for Claude Code

`sound-room` is an AI music production workspace. `tools/` is git-ignored and holds seven
vendored repositories; re-create it with `./scripts/setup-tools.sh`.

### The three rules

**1. Split uploaded songs into stems.**
When a file appears in `public/music/uploads/`, use `tools/stem-separator` (primary) or
`tools/StemForge` to separate **drums, bass, guitar, strings, vocals**.

```bash
cd tools/stem-separator && python -m stem_separator \
  ../../public/music/uploads/<song>.wav \
  --model htdemucs_6s --stems vocals,drums,bass,guitar,other \
  --format wav -o ../../public/music/stems/<song-slug>/
```
`htdemucs_6s` has no strings stem — strings and other instruments land in `other`.

**2. Compose new parts around the song's tempo and key.**
Use `tools/strudel-claude` (patterns via `npm run dev`), `tools/AI-Beat-Maker`
(`python main.py --track=<wav> --drums=True --bass=True`), or
`tools/audiocraft` MusicGen-Melody (`facebook/musicgen-melody` +
`generate_with_chroma(...)`) for beats, basslines, guitar riffs, and string themes.
Detect BPM/key first (`curl -F file=@<song> localhost:5000/analyze`), and write parts to
`public/music/beats/<song-slug>/`.

**3. Blend original + new parts and export to `out/music/`.**
Use `tools/aimusicmixer` (`POST /mix` with `track1`, `track2`, `crossfade_sec`,
`ai_mode`) and follow the mixing rules in
`tools/claude-ai-music-skills/skills/mix-engineer/` (apply with
`tools/mixing/mix_tracks.py`). Export the finished track to `out/music/<song-slug>_mix.wav`.

### Guardrails
- Never commit audio — `public/music/**` and `out/music/**` contents are git-ignored.
- Never edit `tools/` (disposable clones); never commit model weights.
- Order is fixed: separate → analyze → compose → mix → export.
