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

`tools/` holds nine cloned repositories. Each keeps its own license, `.git` directory,
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
| `tools/amapiano-inspired` | `mizcausevic-dev/amapiano-inspired` | Amapiano MIDI studies (28 files, 112 BPM) + drum map + patch recipes |
| `tools/Amapiano-Beatpad` | `Eazyguy/Amapiano-Beatpad` | 12 Amapiano beat loops (`.m4a`), MIT — playable via `index.html` |

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

**Amapiano flavour — `tools/amapiano-inspired` + `tools/Amapiano-Beatpad`**

The genre's identity is the **log drum** (a pitch-gliding sub-bass stab), sparse jazzy
pads, and a swung 110–115 BPM grid. Two ready sources:

```bash
# A. MIDI studies: 4 arrangements × 112 BPM (keys C#, E, G, D)
tools/amapiano-inspired/midi/
  ap01-room-tone/{drums,sub_bass,chord_pulse,principal_motif,counter_texture,vocal_like_synth}.mid
  ap01-room-tone/ap01-room-tone-combined.mid     # combined arrangement — never stack
                                                 # part files on top of this one
```
- `catalog/drum-map.csv` documents the kit mapping (36 kick, 38 snare, 39 clap,
  42 closed hat, 46 open hat) and `catalog/patch-recipes.json` maps each role to a
  MIDI channel plus its polyphony cap.
- The MIDI carries **no program changes or samples**, so a generic player substitutes its
  own sounds. Render it with your own log-drum/bass patches, then retune and retime to the
  song — the studies are fixed at 112 BPM in a fixed key:
  ```bash
  fluidsynth -F /tmp/part.wav <your-logdrum-bank>.sf2 tools/amapiano-inspired/midi/ap01-room-tone/sub_bass.mid
  # then conform to the song's tempo/key (librosa or ffmpeg):
  #   librosa.effects.time_stretch(y, rate=112/song_bpm)
  #   librosa.effects.pitch_shift(y, sr=sr, n_steps=<semitones to song key>)
  ```
- `preview/amapiano-inspired-simple-synth-preview.mp3` is reference audio only; the
  `tools/*.py` scripts build the release and a **video** visualizer, not audio renders.

```bash
# B. Beat loops: 12 royalty-free .m4a files — fastest route to an Amapiano groove
ls tools/Amapiano-Beatpad/Assets/          # Beat1.m4a … Beat12.m4a (MIT licensed)
```
Time-stretch a loop to the song's BPM (`ffmpeg -i Beat3.m4a -filter:a
"atempo=<song_bpm/loop_bpm>" out.wav`), then layer it under the drums, and write the
result to `public/music/beats/<song-slug>/`.

> **Licensing — check before releasing.** `Amapiano-Beatpad` is **MIT** (free, including
> commercial use). `amapiano-inspired` ships under a **proprietary "MIDI BUYER LICENSE
> v1.0"** that grants rights only to purchasers of the pack; cloning it for study and
> reference is fine, but shipping a commercial track built on those MIDI files requires
> buying the pack. Prefer the MIT loops when the output is going public, and tell the user
> which source a given beat came from.

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

### Rule 4 — "Amplify this" (single-file enhancement, no stems needed)

When the ask is simply *"make this sound better/louder"* on one file, do not reach for
stem separation. Measure first, then correct — never guess at the chain.

```bash
pip install -r requirements-music.txt          # CPU-only, ~60 MB, no GPU needed

# 1. Diagnose: loudness, true peak, band balance, stereo width, tempo, key
python3 scripts/analyze_audio.py public/music/uploads/<song>.mp3

# 2. Apply the chain (see presets in the script) and render a 24-bit master
python3 scripts/enhance_audio.py public/music/uploads/<song>.mp3 \
  -o out/music/<song-slug>-master.wav --preset amapiano_balanced --report

# 3. Re-measure the output and confirm the fix
python3 scripts/analyze_audio.py out/music/<song-slug>-master.wav
```

`build_voice_track.py` does the end-to-end version of this for a voice memo: it cleans
the vocal, picks a bed loop by measured tempo/key/chroma match, arranges intro/vocal/outro
on bar boundaries, ducks the bed under the vocal and masters to −14 LUFS.

`enhance_audio.py` runs: corrective EQ → harmonic excitation → stereo repair → glue
compression → loudness normalisation to a **true-peak** ceiling. Presets are
`neutral`, `amapiano_balanced`, `amapiano_lift`, `bright`, `warm`.

Rules of thumb learned the hard way:
- **Bass owns the peak ceiling.** On bass-heavy material you cannot reach -14 LUFS at
  -1 dBTP without distorting the low end; ~-15 LUFS cleanly is the honest result.
  Do not force it — and never report a loudness you did not measure.
- **The limiter must be true-peak, not sample-peak.** Sample-peak limiting leaves
  inter-sample overshoots that platforms later clip.
- **Tune presets against measurements**, not by ear-by-proxy: sweep one parameter and
  re-measure band balance before committing.
- Targets: ~-14 LUFS integrated (streaming), ≤ -1.0 dBTP, 40–55% of energy below
  250 Hz for bass-forward genres, and >2% above 8 kHz so it is not dull.
- Always write a short before/after report next to the output.

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
