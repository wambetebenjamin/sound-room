# OFFline / ON-site — running this repo at church with no internet

Short version: **the parts that matter for a live service already run offline today.**
The heavy AI (stem separation, MusicGen) needs a one-time download and a GPU to be
useful; on a laptop CPU it is too slow to be live.

---

## 1. What works with zero internet right now

| Thing | Offline? | Notes |
| --- | --- | --- |
| `scripts/analyze_audio.py` | ✅ | Pure numpy/scipy/librosa, local |
| `scripts/enhance_audio.py` | ✅ | EQ, compression, limiting, mastering |
| `scripts/build_original_beat.py` | ✅ | Synthesises a beat from code — no assets |
| `scripts/build_voice_track.py` | ✅ | Voice + bed → finished track |
| `tools/Amapiano-Beatpad` | ✅ | Static page + local `.m4a`; only Bootstrap CSS comes from a CDN (cosmetic) |
| `tools/ambientpad` | ⚠️ | Worship pads as a PWA — **mount it once online** so the service worker caches the pads |
| `tools/church-music-generator` | ⚠️ | `pnpm install` once online, then generates chord/lyric sheets offline |
| `tools/strudel-claude` | ❌ | Loads the Strudel engine from `unpkg.com` at runtime — **silent with no internet** |
| `tools/stem-separator` | ⚠️ | Works offline *after* Demucs weights (~300 MB) are cached; CPU is ~5–15 min/song |
| `tools/audiocraft` (MusicGen) | ⚠️ | ~6 GB weights; 10–50× slower than real time on CPU → unusable live |
| `tools/StemForge` | ⚠️ | ~20 GB of models on first run |

**Rule of thumb:** anything that has to feel instant (pads, loops, our synthesised
beats) is offline-ready. Anything with a neural model is a "prepare tonight" job.

---

## 2. Tonight's checklist (do this on the wifi you have)

```bash
# 1. Dependencies for our own scripts (no GPU, ~60 MB)
pip install -r requirements-music.txt
pip install imageio-ffmpeg          # only if you need to decode .m4a/.aac

# 2. Prove it runs before you rely on it
python3 scripts/offline_check.py

# 3. Pre-render anything you want in the service — do not generate live
python3 scripts/build_original_beat.py -o public/music/beats/tonight.wav --bpm 114.8 --key Gm --bars 24

# 4. Optional: cache the worship pads for offline use
cd tools/ambientpad && python3 -m http.server 8100   # open once, let the SW cache, then close

# 5. Optional: church chord sheets
cd tools/church-music-generator && pnpm install && pnpm generate songs/your-song.json
```

Then **switch the laptop to airplane mode and run the whole chain once** to be sure.
That is the only test that counts.

---

## 3. What to bring

- Laptop **already charged + charger** (audio work drains fast)
- Audio interface or a USB mic for the voice; a DI/1-4" jack to the desk
- The rendered `.wav` files **on the laptop and a USB stick** (redundancy beats hope)
- `demos/` in this repo has playable MP3s you can test on the desk before the service

## 4. Live rig that actually works

| Want | Use | Latency |
| --- | --- | --- |
| Background pads under prayer | `tools/ambientpad` (offline PWA) | none (just playback) |
| A beat to sing over, fixed tempo | pre-rendered beat from `build_original_beat.py` played from any player | none |
| Trigger loops by hand | `tools/Amapiano-Beatpad` in a browser | ~10–20 ms |
| Live-coded patterns | Strudel — **only if you vendor the engine first** | ~20 ms |

**Do not attempt live AI generation.** Latency is seconds, not milliseconds, and it will
fail in front of a congregation.

## 5. Making Strudel truly offline (the one real gap)

`tools/strudel-claude/src/hooks/use-strudel.ts` references
`https://unpkg.com/@strudel/repl@latest`. To fix:

```bash
cd tools/strudel-claude
npm install @strudel/repl
# then point STRUDEL_CDN at the local /node_modules copy and serve it from /public
```

Until that is done, do not put Strudel on the plan for an offline set.
