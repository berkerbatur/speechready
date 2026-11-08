#!/usr/bin/env bash
# Evaluate the local models that need a GPU: Chatterbox, XTTS v2 and Orpheus.
#
#   bash eval/gpu/run.sh [chatterbox,xtts,orpheus]
#
# Run from a clone on a CUDA machine (used on a RunPod RTX 4090 with the image
# runpod/pytorch:1.0.2-cu1281-torch280-ubuntu2404). Each model gets its own venv
# because their torch and vLLM pins disagree; every model writes its clips with
# --synth-only, then one venv transcribes all of them with faster-whisper on the
# GPU and scores them into eval/out/results.jsonl. Copy results.jsonl and
# eval/out/audio back and run `report` and `showcase` as usual.
set -euo pipefail
cd "$(dirname "$0")/../.."
PROVIDERS=${1:-chatterbox,xtts,orpheus}
export SPEECHREADY_EVAL_DEVICE=cuda COQUI_TOS_AGREED=1 HF_HUB_DISABLE_XET=1 PIP_DISABLE_PIP_VERSION_CHECK=1
command -v ffmpeg >/dev/null || { apt-get update -qq && apt-get install -y -qq ffmpeg >/dev/null; }

has() { case ",$PROVIDERS," in *",$1,"*) return 0 ;; *) return 1 ;; esac; }
venv() {  # venv NAME [--system-site-packages] PACKAGES...
  local name=$1 flags=""; shift
  [ "${1:-}" = "--system-site-packages" ] && { flags=$1; shift; }
  [ -x ".venv-$name/bin/python" ] || python3 -m venv $flags ".venv-$name"
  ".venv-$name/bin/pip" install -q "$@" -e python -e eval
}
stamp() { date "+%H:%M:%S $*"; }

if has chatterbox; then
  stamp "chatterbox: install"; venv chatterbox chatterbox-tts
  stamp "chatterbox: synth"; .venv-chatterbox/bin/python -m speechready_eval.run --providers chatterbox --synth-only
fi
if has orpheus; then
  stamp "orpheus: install"; venv orpheus orpheus-speech "vllm==0.7.3"
  stamp "orpheus: synth"; .venv-orpheus/bin/python -m speechready_eval.run --providers orpheus --synth-only
fi
stamp "main: install"; venv main --system-site-packages coqui-tts "faster-whisper>=1.1"
if has xtts; then
  stamp "xtts: synth"; .venv-main/bin/python -m speechready_eval.run --providers xtts --synth-only
fi
# CTranslate2 (faster-whisper) loads cuBLAS and cuDNN from the nvidia wheels that pip's torch brings.
LIBS=$(.venv-main/bin/python -c 'import os, nvidia.cublas.lib, nvidia.cudnn.lib; print(os.path.dirname(nvidia.cublas.lib.__file__) + ":" + os.path.dirname(nvidia.cudnn.lib.__file__))' 2>/dev/null || true)
export LD_LIBRARY_PATH="${LIBS:+$LIBS:}${LD_LIBRARY_PATH:-}"
stamp "whisper: transcribe $PROVIDERS"; .venv-main/bin/python -m speechready_eval.run --providers "$PROVIDERS" --stt whisper
stamp "done"
