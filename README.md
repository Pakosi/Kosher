# Doodle Reels

Automated, local-first pipeline that turns a series config into finished **2D doodle-style Instagram Reels**:
scroll-stopping hook → script → storyboard → assets → multi-voice narration → word-level captions and lip sync →
Remotion render → QA gate → review dashboard → scheduled publishing → analytics that feed back into hook scoring.

Built for an Apple Silicon Mac (tested target: MacBook Pro M5 Pro, 24 GB). Every heavy model runs locally and
is loaded **one at a time**; the only cloud call is one optional Claude polish per script.

```
idea pool ──► script ──► storyboard ──► assets ──► tts ──► align ──► timeline ──► render ──► qa ──► review ──► publish ──► analytics
 (Ollama)    (Ollama +   (Ollama)      (ComfyUI   (Kokoro/  (Whisper   (props +    (Remotion  (ffmpeg,  (dashboard) (Graph API)   (insights →
  judge)      Claude)                   SDXL+LoRA) F5/11L)   MLX)       bundle)     + loudnorm) VLM)                              formula priors)
```

---

## Quick start

```bash
git clone <this repo> doodle-reels && cd doodle-reels
./setup/macos.sh                      # brew deps, Ollama models, ComfyUI+SDXL, Python env, Remotion
source orchestrator/.venv/bin/activate
cp .env.example .env && $EDITOR .env   # ANTHROPIC_API_KEY (optional), IG tokens (for publishing)
reels doctor                           # shows what's installed / missing
reels make dirty-money                 # one episode end-to-end -> review queue
reels dashboard                        # http://127.0.0.1:8765 approve / reject
```

No models yet? Run everything offline with the test profile (mock LLM, espeak voices, estimated alignment,
built-in art): `REELS_PROFILE=test reels make dirty-money`.

## What's in the box

| Path | What |
|---|---|
| `config/pipeline.yaml` | models, endpoints, render + audio + QA settings (`pipeline.local.yaml` for personal overrides, `pipeline.test.yaml` offline profile) |
| `config/series/*.yaml` | one file per series/account: tone, topics, rules, main character, cast, palette, voices, captions, posting slots |
| `orchestrator/reels/` | Python package + `reels` CLI (steps, LLM/TTS/ASR backends, ComfyUI client, dashboard, publisher) |
| `orchestrator/reels/data/hook_formulas.yaml` | 24 hook formulas with examples (extend freely) |
| `remotion/` | the `Reel` composition: doodle draw-on props, line boil, procedural or rigged character with lip sync, kinetic captions, camera moves, transitions, SFX, ducked music |
| `episodes/<series>/<id>/` | everything one episode produced (JSON per step, audio, render bundle, final.mp4, qa.json, log) |
| `characters/<id>/` | reference art, LoRA dataset, pose sheet, `rig.json` |
| `library/music/<series>/`, `library/sfx/` | your music beds and SFX (procedural fallbacks are generated if empty) |
| `state/` | SQLite (episode index, hooks history, analytics, formula stats) + idea pools |

## The steps

Every step writes one file into the episode folder and is **cached by content hash** of its inputs (upstream files,
relevant config, code version). Edit any JSON by hand and re-run: only downstream steps redo.

```bash
reels run <episode>                    # resume; cached steps are skipped
reels run <episode> --from tts         # redo from a step
reels run <episode> --force storyboard # force one step
reels run <episode> --to timeline      # stop early
reels show <episode>                   # script + QA report
```

`<episode>` is `series/id`, a path, or any unique part of the id.

1. **Ideas** (`reels ideas <series>`): generates ~40 candidates, each built on a hook formula. Formulas are sampled
   with softmax weights from analytics priors (exploration kept). Candidates are deduped against every hook the series
   has used (trigram similarity), banned words kill outright, a judge model (different family from the writer) scores
   hook strength, curiosity gap, payoff, specificity, fit and visual potential, plus deterministic hook heuristics
   (length, numbers, direct address, slow openers). **Top 20% are kept**; `make`/`new` pop the best unused one.
2. **Script**: local draft with a strict beat structure — hook (≤14 words, 0–3 s) → setup → escalation → twist →
   payoff → loop line that flows back into the hook. Validated (beats, order, speakers, length 35–55 s, banned words)
   with up to two automatic repair passes, then **one Claude polish call** (structured output, same schema). Without
   a key it falls back to a local self-critique pass. Hand-write a script instead: `reels new <series> --script my.json`.
3. **Storyboard**: scenes with background, character pose + expression, 1–3 props appearing on the word that names
   them, camera move, on-screen text, SFX, transition. Output is coerced onto the shared vocabulary
   (`orchestrator/reels/vocab.py`) so the renderer never meets an unknown name.
4. **Assets**: 55 built-in doodle icons + 10 built-in backgrounds cost nothing. Anything else is generated via ComfyUI
   (SDXL + optional style LoRA), background-removed, vectorised with potrace (so it can draw on stroke by stroke) and
   stored in a **global asset cache** keyed by prompt, reused by every later episode.
5. **TTS**: one clip per line, per-line cache (edit one line → only that line is re-voiced). Engines per voice with
   fallbacks: `kokoro` (default), `mlx-kokoro`, `f5` (voice cloning on MLX), `elevenlabs`, `say`, `espeak`, `sine`.
   Emotion nudges speed; beat changes get a slightly longer pause. Numbers/money are normalised for speech.
6. **Align**: Whisper word timestamps per line (biased with the line text), mapped back onto the script's own tokens
   so captions keep correct spelling. Mouth shapes (A–H, X) from Rhubarb Lip Sync if installed, otherwise a fast
   letter-cluster model. Engines: `mlx-whisper` (default on Mac), `faster-whisper`, `whisper-cpp`, `estimate`.
7. **Timeline**: resolves everything into the Remotion props (`Timeline` in `spec.py` ⇄ `remotion/src/schema.ts`)
   and assembles the episode's render bundle (`public/`): narration, music bed, SFX, generated art, rig images.
8. **Render**: Remotion → `raw.mp4` (1080×1920 @ 30 fps, H.264, CRF 18) → two-pass **loudnorm to −14 LUFS / −1 dBTP**
   → `final.mp4`, plus `cover.png`.
9. **QA**: format, length, loudness, true peak, dead air, black frames, banned words, hook timing, cold open, safe
   zones, **caption sync** (re-transcribes the final mix: WER + median caption drift), flat-frame detection, and a
   local **vision-model frame check** (cut-off text, cropped character, glitches). Pass/warn → review; fail →
   `qa_failed`.

### Memory discipline (24 GB)

* Ollama calls use `keep_alive: 0`; after every LLM stage the runner evicts all Ollama models.
* ComfyUI gets `POST /free` (unload models + free memory) after every asset/character job.
* TTS and Whisper steps run in a **spawned child process**, so MLX/torch weights are released when the step exits.
* `reels batch` is **stage-major**: all scripts, then all storyboards, then all assets, then all TTS, then all
  alignment, then all renders — one kind of model resident at a time.
* `reels free` evicts everything manually.

## Series and characters

Copy `config/series/dirty-money.yaml` and edit. Key fields:

```yaml
character: { id: vinnie, speaker: vinnie, description: "...", personality: "...",
             lora: vinnie_v1.safetensors, lora_trigger: "vnnie raccoon",
             procedural: { species: raccoon, body: "#A7A7A7", accent: "#E63946", accessory: fedora } }
cast: []            # extra recurring characters (same shape)
voices:             # key = speaker name used in scripts
  narrator: { engine: kokoro, voice: am_michael, speed: 1.06, fallback: [mlx-kokoro, say] }
  vinnie:   { engine: f5, ref_audio: library/voices/vinnie.wav, ref_text: "...", fallback: [kokoro] }
caption: { font: Bangers, size: 96, highlight: "#FFD166", words_per_chunk: 3 }
```

Bundled caption fonts (offline): Bangers, Gochi Hand, Patrick Hand, Permanent Marker, Caveat Brush, Luckiest Guy.

**Out of the box** every character renders as a built-in **procedural SVG character** (raccoon, blob, cat or
human; 10 poses, 9 expressions, blinking, breathing, talk bob, full mouth-shape lip sync, accessories). That
already gives a consistent mascot per series with zero generation.

**Custom generated character** (Mac + ComfyUI), once per character:

```bash
reels character design dirty-money --n 8          # pick one -> characters/vinnie/reference.png
reels character dataset dirty-money --count 30    # IPAdapter variations + captions; delete off-model ones
reels character train dirty-money                 # writes characters/vinnie/lora/train.sh (kohya sd-scripts, MPS)
bash characters/vinnie/lora/train.sh              # ~1-2 h; copies the LoRA into ComfyUI; set `lora:` in the yaml
reels character sheet dirty-money --candidates 4  # 10 poses x 4 candidates, mouth closed
reels character pick dirty-money point characters/vinnie/candidates/point/2_0.png   # per pose
reels character autorig dirty-money               # vision model places mouth + eyes
reels dashboard                                   # Characters tab: click to fine-tune mouth/eyes, save
```

The renderer then uses the pose PNGs with a live mouth (skin patch + animated mouth shape) and blink lids.
Skip the LoRA and the sheet still works off `reference.png` via IPAdapter (less consistent).

## Review, scheduling, publishing

```bash
reels dashboard                      # Review / QA failed / Scheduled / Published / Characters / Stats
reels approve <ep>                   # next free slot from series publish.post_times (timezone aware)
reels approve <ep> --at 2026-11-02T19:00:00-05:00
reels reject <ep> --note "hook weak" --rerun script
reels publish due                    # publish everything whose slot has passed
reels install-scheduler              # launchd: `publish due` + `analytics` every 15 min
```

Publishing uses the Instagram Graph API **resumable upload** (`media_type=REELS`, `upload_type=resumable`), so the
video never needs a public URL: create container → upload bytes to `rupload.facebook.com` → poll `status_code` →
`media_publish`. Per series, set the env vars named in `publish.ig_user_id_env` / `publish.token_env` to the IG
professional account id and a long-lived token with `instagram_content_publish` and `instagram_manage_insights`.
Test without posting: `reels publish <ep> --dry-run`.

**Analytics loop** (`reels analytics`): pulls views, reach, likes, comments, shares, saves and average watch time;
computes a retention-weighted score; after 48 h the score is recorded against the episode's hook formula
(Welford running mean, shrunk toward the series mean). Those priors bias formula sampling and idea ranking, and
the best-performing hooks are shown to the writer model as few-shot "energy" references.

## Overnight batch

```bash
reels batch --series all --count 3              # 3 per series, ends in the review queue
reels batch --series dirty-money --count 5 --to timeline
```

Failures are isolated per episode (status `failed` + error + traceback in `log.txt`); `reels run <ep>` resumes.

## Remotion

```bash
cd remotion
npm run studio                       # preview with the sample props
reels studio-sample <episode>        # make any episode the Studio sample
npm run typecheck
```

Composition `Reel` reads the timeline JSON (`--props`) and the episode bundle (`--public-dir`). Visual system:
paper background + grain, built-in background doodles, props that **draw on stroke by stroke** then fill, potrace'd
generated props that trace then fill, **line boil** (turbulence displacement re-seeded 10×/s, 4-drawing cycle) on
art but not captions, per-scene camera (push-in, pull-out, pans, tilt, shake, whip-zoom, subtle drift on "static"),
transitions (whip, paper slide, zoom, ink wipe), on-screen text (stamp, marker swipe, counter, banner), kinetic
captions (3-word chunks, active-word pop, emphasis colour), SFX on cues, music ducked under speech with
attack/release ramps. Layout keeps IG safe zones: text 10–20%, props 24–42%, captions ~50%, character 55–90%.

## Mac-only vs tested here

Built and tested in a Linux container (no GPU, no model downloads): unit tests (`pytest tests`), the full offline
episode (`REELS_PROFILE=test`) through render and QA, Remotion typecheck. Not runnable there and therefore
**untested until you run them on the Mac**: Ollama models, Claude polish (needs your key), ComfyUI generation and
LoRA training, Kokoro / mlx-audio / F5 voices, mlx-whisper, Rhubarb, vision QA, Instagram publishing against the
real API (the request flow is unit-tested with a mock transport). `reels doctor` tells you what's ready.

## Troubleshooting

* `reels doctor` first.
* Render slow? Lower `render.concurrency` if memory-bound, raise it if CPU idle. Line boil is the most expensive
  effect: set `lineBoil` false via a series override or edit `timeline.json` for drafts.
* Remotion can't download Chrome (offline): set `render.browser_executable` in `config/pipeline.local.yaml`.
* Ollama model returns junk JSON: outputs are schema-constrained; if a model ignores it, try `qwen3:14b` or switch
  `draft` to an MLX server via the `openai` backend.
* Wrong pronunciation: edit the line text (numbers are normalised by `text.speakable`) or switch that voice's engine.

## Tests

```bash
source orchestrator/.venv/bin/activate
pytest tests                          # 20+ tests, offline, ~5 s
cd remotion && npm run typecheck
```
