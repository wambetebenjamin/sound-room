# AGENTS.md

Canonical instructions for AI agents (Claude Code, Cursor, Codex, etc.) working in
this repository. `CLAUDE.md` mirrors this file — **if you change one, change both.**

This repo (`sound-room`) is an AI-assisted music production workspace: a song goes in,
it gets split into stems, new parts are composed around it, and a finished mix comes out.

---

## 1. Repository layout

| Path | Purpose | Tracked in git? |
| --- | --- | --- |
| `public/music/uploads/` | **Input.** Songs dropped here for processing. | Folder only (`.gitkeep`) |
| `public/music/stems/` | Separated stems, one subfolder per song. | Folder only |
| `public/music/beats/` | Newly composed beats / basslines / riffs / themes. | Folder only |
| `out/music/` | **Output.** Final blended/exported tracks. | Folder only |
| `tools/` | Vendored third-party tools, cloned here. | **No** — git-ignored |
| `scripts/setup-tools.sh` | Re-clones `tools/` at pinned commits. | Yes |

Audio files inside the four music folders are git-ignored on purpose — the folders
themselves are committed via `.gitkeep`. Never commit `.wav`/`.mp3`/`.flac` payloads.
Re-create `tools/` at any time with `./scripts/setup-tools.sh`.

---

## 2. Vendored tools

`tools/` holds seven cloned repositories. Each keeps its own license, `.git` directory,
and upstream history; treat them as read-only dependencies.

| Directory | Upstream | Role |
| --- | --- | --- |
| `tools/stem-separator` | `Su1ph3r/stem-separator` | Demucs stem splitting — **primary** separator |
| `tools/StemForge` | `tsondo/StemForge` | GUI stem workstation (Demucs/MDXNet) — alternative separator |
| `tools/strudel-claude` | `renatoworks/strudel-claude` | Live-coding composer (Strudel/Tidal) with a REST API |
| `tools/AI-Beat-Maker` | `guyyariv/AI-Beat-Maker` | Sample-remix + LSTM drum/bass generator |
| `tools/audiocraft` | `facebookresearch/audiocraft` | MusicGen / **MusicGen-Melody** generation |
| `tools/aimusicmixer` | `EnriqueJRZ/aimusicmixer-backend` | Flask service: tempo/key analysis + track blending |
| `tools/claude-ai-music-skills` | `bitwize-music-studio/claude-ai-music-skills` | Mix/master skill rules + `mix_tracks.py` |

Run `./scripts/setup-tools.sh` if `tools/` is empty or a directory is missing.

---

## 3. Rules

### Rule 1 — Split every uploaded song into stems

**Trigger:** a new audio file appears in `public/music/uploads/`.

Use `tools/stem-separator` (preferred) or `tools/StemForge`. Produce the five parts the
project cares about: **drums, bass, guitar, strings, vocals**.

```bash
cd tools/stem-separator
python3 -m venv .venv && source .venv/bin/activate   # first run only
pip install -r requirements.txt                       # or: pip install -e .

# 6-stem model is required for guitar; plain htdemucs only yields 4 stems.
python -m stem_separator ../../public/music/uploads/<song>.wav \
  --model htdemucs_6s \
  --stems vocals,drums,bass,guitar,other \
  --format wav \
  --naming "{name}_{stem}" \
  -o ../../public/music/stems/<song-slug>/
```

- `htdemucs_6s` separates `drums, bass, vocals, guitar, piano, other`.
  **There is no dedicated strings stem** — strings/keys/brass land in `other`. Keep
  `other` as the strings source and say so in your notes; don't claim a strings stem exists.
- Use `--model htdemucs_ft` when quality matters more than speed.
- Prefer `stem-separator` CLI over StemForge for automation: StemForge is a browser GUI
  (`cd tools/StemForge && uv run stemforge --port 8765`) and downloads ~20 GB of models
  on first run. Reach for it only when a human wants to audition/interactively edit stems.
- Write stems as `<song-slug>/<stem>.wav` under `public/music/stems/`.

### Rule 2 — Compose new parts around the song's tempo and key

**Before composing, detect tempo + key** (see Rule 3's `/analyze` endpoint, or `librosa`).
Every generated part must match the source song's BPM and key. If a tool can't be
conditioned, retune/time-stretch the result afterwards.

Pick the right tool per part:

**Beats & percussion — `tools/AI-Beat-Maker`**
```bash
cd tools/AI-Beat-Maker
pip install -r requirements.txt
# input must be a .wav placed in samples/
python main.py --track=<sample_name_without_extension> --drums=True --bass=False --k=4
```

**Beats, basslines, riffs & themes — `tools/strudel-claude`**
```bash
cd tools/strudel-claude
npm install && npm run dev      # serves the live-coding UI + REST API
```
Use it for pattern-based parts built from code (e.g. a bassline locked to the song's
tempo). Existing sets live in `tools/strudel-claude/tracks/`.

**Melodic parts (guitar riffs, string themes) — `tools/audiocraft` MusicGen-Melody**
```python
from audiocraft.models import MusicGen
from audiocraft.data.audio import audio_write

model = MusicGen.get_pretrained("facebook/musicgen-melody")  # melody-conditioned
model.set_generation_params(duration=30)
wav = model.generate_with_chroma(
    descriptions=["warm string section, <key>, <bpm> bpm"],
    melody_wavs=melody,          # tensor [B, C, T] from the song's stem
    melody_sample_rate=sr,
    progress=True,
)
```
Condition it on a stem of the original (e.g. `other.wav` for strings, the guitar stem
for riffs) so the generated line follows the existing harmony. GPU strongly recommended.

Save all generated parts to `public/music/beats/<song-slug>/` with a descriptive name
(e.g. `bassline_96bpm_Am.wav`).

### Rule 3 — Blend everything and export to `out/music/`

Two layers, both required:

**(a) Tempo/key analysis + crossfade blending — `tools/aimusicmixer`**
```bash
cd tools/aimusicmixer
pip install -r requirements.txt
python app.py                       # → http://localhost:5000 (PORT env overrides)

# Analyze the song
curl -F "file=@../../public/music/uploads/<song>.wav" http://localhost:5000/analyze
# → {"bpm": 96.0, "key": "A", "duration_sec": ...}

# Blend original + new part (returns MP3)
curl -F "track1=@../../public/music/uploads/<song>.wav" \
     -F "track2=@../../public/music/beats/<song-slug>/<part>.wav" \
     -F "crossfade_sec=16" -F "ai_mode=true" \
     -o ../../out/music/<song-slug>_mix.mp3 http://localhost:5000/mix
```

**(b) Mixing rules — `tools/claude-ai-music-skills`**
Read `tools/claude-ai-music-skills/skills/mix-engineer/SKILL.md` (per-stem cleanup, EQ,
compression) and `skills/mix-engineer/mix-presets.md` (genre presets) before mixing.
Apply them with the bundled script:
```bash
pip install noisereduce scipy numpy soundfile
python tools/claude-ai-music-skills/tools/mixing/mix_tracks.py \
  public/music/stems/<song-slug>/ \
  --genre <genre> \
  --output-dir out/music \
  --dry-run        # drop this to actually render
```
Optional final step: `skills/mastering-engineer/SKILL.md` + `tools/mastering/` for
loudness/streaming targets (`matchering`, `pyloudnorm`).

**Export rule:** the finished track goes to `out/music/` as
`<song-slug>_mix.wav` (or `.mp3`). Always report the output path and the bpm/key used.

---

## 4. Working notes

- **Ordering matters:** separate stems → analyze → compose → mix → export. Never compose
  before you know the tempo and key.
- **Big downloads:** Demucs weights, MusicGen (~1.5 B) and StemForge's AceStep (~20 GB)
  download on first use. Warn the user before kicking those off; cache under
  `.cache/` and never commit weights.
- **Dependencies:** install per-tool inside `tools/<tool>/.venv`. Do not add these to a
  root dependency file — `tools/` is disposable.
- **Long runs:** separation/generation can take minutes; use background processes rather
  than blocking, and report the output path when done.
- **Don't edit `tools/` contents.** If a tool is broken, note it in your summary or fix it
  upstream; local patches vanish on the next `setup-tools.sh --force`.
- **Licenses:** each vendored repo keeps its own. Check before redistributing generated
  audio or shipping any of this commercially (audiocraft is MIT, Demucs weights are
  CC-BY-NC for some models — verify per model).

## 5. Conventions

- Slug songs consistently: `lowercase-with-dashes`, used for stem folders, beat folders,
  and output filenames.
- Keep `public/music/**` audio out of git; `.gitkeep` files must stay.
- `main` is the default branch; work happens on feature branches.
