# Candle Guard (horror short)

Twelve candles burn in the town square. Every candle that goes out lets the Snuffer take one
step closer. 87 shots, ~97 s, voice recorded with Gemini TTS.

| File | What it is |
|---|---|
| `script.txt` | narration (word order drives the edit, do not change words) |
| `voice_gemini.txt` | style prompt + tagged script used for the recording |
| `creature.md` | Snuffer design notes |
| `shots.py`, `props.py` | the shots + the night square, candles, Snuffer, Mr. Hollis |
| `audio/` | processed voice, word timings, sound cues |
| `sfx_extra/` | synthesized horror SFX, `pack.json`, `horror_bed.wav` music, and the script that makes them |

## Full-quality render on a Mac

1. Set up the kit once: `python setup.py` from the roblox-story-kit skill folder (installs to `~/RobloxStories`).
2. Copy this folder to `~/RobloxStories/videos/candle_guard` (keep `audio/`, drop `audio/raw.wav` if you like).
3. Copy `sfx_extra/*.wav` and `sfx_extra/pack.json` into `~/RobloxStories/sfx/`, and `horror_bed.wav` into `~/RobloxStories/music/` (remove other music there).
4. From `~/RobloxStories`, with the kit's python (`PY` = the `python` path in `~/.roblox-story-kit.json`):

```bash
$PY tools/blend.py candle_guard cues
```

```bash
$PY tools/blend.py candle_guard final
```

```bash
$PY tools/finish.py candle_guard
```

The video lands in `videos/candle_guard/out/final.mp4` (1080x1920, captions burned in).
