# "Benjamin voice" — 100% original production

Source vocal: `benjamin voice.mp3` (repo `main`) — OGG, 16 kHz mono, 32.05 s, male, ~G2.

**Every other sound in this track was synthesised numerically by `scripts/build_original_beat.py`.**
No samples, no loops, no third-party audio, no contested licences. The composition and the
sound design are yours.

## What was generated
| Element | How |
| --- | --- |
| Kick | sine pitch-sweep 132→47 Hz + filtered click, soft-clipped |
| Clap | three-tap band-passed noise flam (1.1–3.6 kHz) |
| Hats / shaker | high-passed noise, closed + open, with 8th-note swing |
| Log drum | pitch-glide sine stab — the amapiano signature |
| 808 | driven sine sub (tanh), low-passed at 180 Hz — phonk weight |
| Electric piano | fundamental + 2 harmonics, struck on 1 and the "and" of 3 |
| Pad | 3-voice detuned stack, slow attack — worship texture |
| Bell lead | inharmonic partials (×2.76, ×5.4) |
| Cowbell | two detuned squares, band-passed — phonk accent |

Harmony: **G minor**, progression i–VI–III–VII (Gm–Eb–Bb–F) — anthemic and worship-friendly.
Tempo 114.8 BPM, matched to the vocal; no time-stretching of anything.

Arrangement: 2 bars pad intro → drums enter as the vocal enters → breakdown near the end →
2-bar outro. 39.11 s total.

## Measurements
Beat alone: sub 12.1% / bass 31.9% / low-mid 11.5% / mid 32.9% / high-mid 6.9% / presence 1.9%
(bass landed on a 32% target; total deviation from target across 7 bands: 19.3 points,
down from 48.7 on the first pass).

Final master: **−14.57 LUFS · −1.00 dBTP · peak −1.57 dBFS · crest 15.95 dB**
Vocal sits +5.6 dB over the bed (+5.4 dB in the presence band).

## Honest limitations
- The source is a 16 kHz recording, so **nothing above 8 kHz can exist**. The "dull top" flag is
  inherent to the recording, not a mixing failure.
- Stereo correlation is 0.975: the vocal is mono and the bass is folded to mono on purpose.
  This is mono-compatible, which is usually what you want through a church PA.
