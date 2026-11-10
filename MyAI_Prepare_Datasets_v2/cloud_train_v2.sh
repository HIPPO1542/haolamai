#!/usr/bin/env bash
# Use on a Linux GPU instance ONLY AFTER installing matching CUDA/PyTorch and requirements.
# Does not download or install anything during training; all files must be prepositioned.
set -euo pipefail
echo 'Legacy prepared_v2 training is retired. Use scripts.finetune --run-preflight with the approved v2.4 splits; see docs/VASTAI_DEPLOYMENT.md.' >&2
exit 2
