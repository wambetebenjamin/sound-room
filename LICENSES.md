# Licences and provenance

This repo mixes **our own generated audio** with **third-party code and material**.
This file records which is which. Keep your proof of purchase / licence receipts
alongside this file — the repositories themselves do not carry a licence, so the
right to use them comes from *your* agreements, not from GitHub.

## 1. Audio we generate — entirely ours

Everything rendered by these scripts is original work: no samples, no loops, no
sample packs. The waveforms are computed from scratch.

- `scripts/build_original_beat.py`
- `scripts/build_worship_arrangement.py`
- `scripts/build_voice_track.py`
- `scripts/enhance_audio.py`

Karplus-Strong string synthesis (used for guitar and bass) is a public-domain
technique published in 1983. The implementation here is original.

## 2. Third-party repositories in `tools/` (git-ignored, not redistributed)

| Directory | Licence stated upstream | Our use |
| --- | --- | --- |
| `Amapiano-Beatpad` | **MIT** | Loops used in `demos/benjamin-voice-track.mp3` |
| `Le-Phonk` | **MIT** | Reference |
| `church-music-generator` | **MIT** | Reference |
| `stem-separator`, `StemForge`, `audiocraft`, `strudel-claude`, `aimusicmixer`, `claude-ai-music-skills`, `AI-Beat-Maker`, `amapiano-inspired` | see each repo | Tooling / reference |
| `ambientpad` | **none stated** | Live use at church; not sampled into any release |
| `javascript-karplus-strong`, `EKS-string-generator` | **none stated** | Study reference only |
| `worship-charts` | **none stated** (songs are publisher copyright) | Chart metadata: key, tempo, chord progression |

## 3. The user's assertion (recorded here)

The repository owner states they hold licences covering the material above that
lacks an open licence. If that is correct, keep the receipts with this file. Two
distinctions worth writing down:

- **Chord progressions and keys are not copyrightable.** Reading a chart's key,
  tempo and chord loop and generating a new arrangement is not a reproduction of
  the song. `scripts/backing_from_chart.py` never outputs lyrics or melody.
- **A CCLI-type church licence covers reproducing lyrics/chords for congregational
  use** (projection, chord sheets). It does **not** cover recording or distributing
  the song. If a release needs a cover of a copyrighted worship song, that needs a
  separate mechanical/streaming licence.

## 4. Release checklist

- [ ] Every sound in the track came from our scripts, or from an asset with a licence
      recorded above
- [ ] No audio sampled from `ambientpad`, phonk sample packs, or any unlicensed pack
- [ ] No lyrics or melody reproduced from a copyrighted song
- [ ] Receipts filed for anything the owner licensed
