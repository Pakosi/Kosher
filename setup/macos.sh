#!/usr/bin/env bash
# One-shot macOS (Apple Silicon) setup for Doodle Reels.
# Installs: Homebrew deps, Ollama + models, ComfyUI (+ SDXL, IPAdapter), Python env
# (MLX whisper/audio, Kokoro), Remotion deps. Safe to re-run.
#
#   ./setup/macos.sh              # everything
#   SKIP_COMFY=1 ./setup/macos.sh # skip ComfyUI + SDXL download (~7GB)
#   SKIP_MODELS=1 ./setup/macos.sh
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMFY_DIR="${COMFY_DIR:-$HOME/ComfyUI}"
say() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }

[[ "$(uname -s)" == "Darwin" ]] || { echo "macOS only"; exit 1; }
[[ "$(uname -m)" == "arm64" ]] || echo "warning: not Apple Silicon; MLX engines won't work"

say "Homebrew packages"
command -v brew >/dev/null || /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
eval "$(/opt/homebrew/bin/brew shellenv 2>/dev/null || true)"
brew install ffmpeg python@3.12 potrace git git-lfs uv espeak-ng
# keep an existing Node (>=20) and Ollama (e.g. Ollama.app) instead of replacing them
command -v node >/dev/null || { brew install node@22; brew link --overwrite node@22 >/dev/null 2>&1 || true; }
command -v ollama >/dev/null || brew install ollama
brew install rhubarb-lip-sync 2>/dev/null || echo "rhubarb not in brew on this system; lipsync falls back to rules"

say "Python environment (orchestrator)"
cd "$ROOT/orchestrator"
uv venv -p 3.12 .venv
# shellcheck disable=SC1091
source .venv/bin/activate
uv pip install -e ".[mac,torch,claude,dev]"
uv pip install f5-tts-mlx || echo "f5-tts-mlx optional (voice cloning) failed to install"

say "Remotion"
cd "$ROOT/remotion"
npm ci || npm install
npx remotion browser ensure || true

if [[ -z "${SKIP_MODELS:-}" ]]; then
  say "Ollama models (one at a time is loaded during runs)"
  curl -sf http://127.0.0.1:11434/api/version >/dev/null || brew services start ollama || (ollama serve >/dev/null 2>&1 &)
  sleep 3
  ollama pull qwen3:14b       # drafting (~9GB, Q4)
  ollama pull gemma3:12b      # judging (~8GB)
  ollama pull qwen2.5vl:7b    # vision QA + auto-rig (~6GB)

  say "Warm TTS + Whisper weights"
  cd "$ROOT/orchestrator"
  python - <<'PY'
from kokoro import KPipeline
KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
import mlx_whisper, numpy as np, soundfile as sf, tempfile, os
p = os.path.join(tempfile.gettempdir(), "silence.wav"); sf.write(p, np.zeros(16000, dtype="float32"), 16000)
mlx_whisper.transcribe(p, path_or_hf_repo="mlx-community/whisper-large-v3-turbo")
print("tts + whisper ready")
PY
fi

if [[ -z "${SKIP_COMFY:-}" ]]; then
  say "ComfyUI at $COMFY_DIR"
  if [[ ! -d "$COMFY_DIR" ]]; then git clone https://github.com/comfyanonymous/ComfyUI "$COMFY_DIR"; fi
  cd "$COMFY_DIR"
  # an interrupted clone leaves an empty repo: fetch the default branch into it
  [[ -f main.py ]] || { git fetch origin && git checkout -B master origin/master; }
  git pull --ff-only || true
  [[ -d venv ]] || python3.12 -m venv venv
  ./venv/bin/pip install -q --upgrade pip
  ./venv/bin/pip install -q torch torchvision torchaudio
  ./venv/bin/pip install -q -r requirements.txt
  mkdir -p custom_nodes models/checkpoints models/loras models/ipadapter models/clip_vision
  [[ -d custom_nodes/ComfyUI_IPAdapter_plus ]] || git clone https://github.com/cubiq/ComfyUI_IPAdapter_plus custom_nodes/ComfyUI_IPAdapter_plus
  if [[ ! -f models/checkpoints/sd_xl_base_1.0.safetensors ]]; then
    curl -L -o models/checkpoints/sd_xl_base_1.0.safetensors \
      https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0/resolve/main/sd_xl_base_1.0.safetensors
  fi
  [[ -f models/ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors ]] || curl -L -o models/ipadapter/ip-adapter-plus_sdxl_vit-h.safetensors \
    https://huggingface.co/h94/IP-Adapter/resolve/main/sdxl_models/ip-adapter-plus_sdxl_vit-h.safetensors
  [[ -f models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors ]] || curl -L -o models/clip_vision/CLIP-ViT-H-14-laion2B-s32B-b79K.safetensors \
    https://huggingface.co/h94/IP-Adapter/resolve/main/models/image_encoder/model.safetensors
  cat > "$ROOT/setup/start-comfy.sh" <<SH
#!/usr/bin/env bash
cd "$COMFY_DIR" && exec ./venv/bin/python main.py --listen 127.0.0.1 --port 8188 --force-fp16
SH
  chmod +x "$ROOT/setup/start-comfy.sh"
fi

say "Done"
cat <<TXT
Next:
  cd $ROOT && source orchestrator/.venv/bin/activate
  cp .env.example .env            # add ANTHROPIC_API_KEY, IG tokens (optional)
  ./setup/start-comfy.sh &        # only needed for generated props / characters
  reels doctor
  reels make dirty-money          # first episode -> review queue
  reels dashboard                 # approve / reject
TXT
