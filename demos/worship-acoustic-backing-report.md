# Acoustic worship backing — D major, 72 BPM

Modelled on the instrumentation of a stripped-back / acoustic Hillsong-style live set.
Every sound is synthesised in `scripts/build_worship_arrangement.py`. No samples, no sample
packs, no third-party audio — the recording is your own production.

## The arrangement (12 bars, 40.0 s)

| Bars | Section | What enters |
| --- | --- | --- |
| 1–2 | Intro | Fingerpicked acoustic guitar + felt piano |
| 3–6 | Verse | Upright-style bass, cajon, brushes |
| 7–10 | Chorus | String swells, pad, double-tracked guitar, Rhodes |
| 11–12 | Outro | Strips back to guitar, piano, pad |

Harmony: **D major**, I–V–vi–IV (D–A–Bm–G) — the standard worship progression.
Tempo 72 BPM (ballad feel). Hall reverb, 2.4 s tail, for the "spacious" quality.

## How each instrument is made

| Instrument | Method |
| --- | --- |
| Acoustic guitar | **Karplus-Strong** delay-line pluck, double-tracked L/R 8 ms apart |
| Felt piano | Additive synthesis with string inharmonicity; soft hammer attack, no click |
| Rhodes | FM synthesis, decaying modulation index for the bell-like strike |
| Upright bass | Karplus-Strong with heavy damping, low-passed at 900 Hz |
| Cajon | Tuned sine thump + filtered noise "slap" on the backbeat |
| Brushes | Slow-swelling band-passed noise (2.5–9 kHz) on 8ths, not a hard hit |
| Strings | Bowed harmonic stack with 5.2 Hz vibrato + bow noise, slow swell |
| Pad | Detuned 3-voice stack, slow in/out |

Guitar is high-passed at 150 Hz and the piano's upper voices sit an octave up, which
leaves the 100–250 Hz region free — that is where your vocal's body will live.

## Measurements
Final master: **−14.14 LUFS · −1.00 dBTP · −1.14 dBFS peak**

Band balance: sub 0.1% · bass 34.2% · low-mid 23.1% · mid 30.8% · high-mid 4.7% ·
presence 5.2% · air 1.9% (deviation from target down from 35.4 to 23.0 across three passes).

## Putting your own voice on it
```bash
cp "your song.mp3" public/music/uploads/
python3 scripts/analyze_audio.py "public/music/uploads/your song.mp3"     # tempo + key first
# if the key differs, regenerate in your key:
python3 scripts/build_worship_arrangement.py -o public/music/beats/mine.wav --key Bb --bpm 68
python3 scripts/build_voice_track.py --voice "public/music/uploads/your song.mp3" \
  --bed public/music/beats/mine.wav -o out/music/mysong.wav --bpm 68 --no-bed-eq --bed-start 0
```
Match `--key` to whatever `analyze_audio.py` reports, and `--bpm` to the arrangement's tempo.
