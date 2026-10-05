#!/usr/bin/env bash
# WSL setup for the RTX 3060 machine (works on any WSL2 Ubuntu).  Idempotent: rerun it after any failure or timeout,
# every step skips what is already done.  From the repo root:
#     bash tools/setup/setup_wsl.sh
# It never calls sudo (the password is yours): missing apt packages are printed as a command for you to run.
# Env overrides: CARDIAC_VENV (default ~/.venvs/cardiac), CARDIAC_DATA (default /mnt/d/data if D: exists, else ~/data),
#                TORCH_INDEX (default: plain PyPI, whose Linux wheels are CUDA builds; e.g. .../whl/cu126 to pin a flavour)
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VENV="${CARDIAC_VENV:-$HOME/.venvs/cardiac}"
TORCH_INDEX="${TORCH_INDEX:-}"
say()  { printf '\n\033[1m== %s\033[0m\n' "$*"; }
ok()   { printf '  \342\234\223 %s\n' "$*"; }
warn() { printf '  ! %s\n' "$*"; }

say "0. where am I"
if grep -qi microsoft /proc/version 2>/dev/null; then ok "WSL2"; else warn "not WSL -- this script targets WSL2 Ubuntu (continuing anyway)"; fi
case "$REPO" in
  /mnt/[a-z]/*) ok "repo on the Windows drive: $REPO (Unreal can build it)";;
  *) warn "repo is inside the Linux filesystem ($REPO): fast for Python, but Unreal on Windows cannot build it. Recommended clone location: /mnt/c/work/Cardiac";;
esac

say "1. system packages"
need=()
for p in python3-venv python3-dev build-essential git unzip rsync; do dpkg -s "$p" >/dev/null 2>&1 || need+=("$p"); done
if ((${#need[@]})); then
  warn "missing: ${need[*]}"
  echo "    run this yourself, then rerun the script:"
  echo "    sudo apt update && sudo apt install -y ${need[*]}"
  exit 1
fi
ok "apt packages present"

say "2. Python (3.10-3.12: the range the pipeline and the PINN results were produced on)"
# Do not just take the first `python3` on PATH: a conda/miniforge base (3.13, 3.14 ...) usually shadows the system one,
# and outside 3.10-3.12 some packages have no wheels (triangle then fails to compile) and results drift from the record.
inrange() { local v; v=$("$1" -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>/dev/null) || return 1; case "$v" in 3.10|3.11|3.12) return 0;; esac; return 1; }
PY=""
for c in ${CARDIAC_PYTHON:-} python3.12 python3.11 python3.10 /usr/bin/python3 python3; do
  command -v "$c" >/dev/null 2>&1 && inrange "$c" && { PY=$(command -v "$c"); break; }
done
if [ -n "$PY" ]; then
  ok "using $PY ($("$PY" -V 2>&1))"
  [ "$(command -v python3)" != "$PY" ] && echo "    (python3 on PATH is $(command -v python3), $(python3 -V 2>&1) -- not used on purpose)"
else
  PY=$(command -v python3)
  warn "no Python 3.10-3.12 found; falling back to $PY ($("$PY" -V 2>&1)). Install one (Ubuntu: python3.12 python3.12-venv) or set CARDIAC_PYTHON."
fi

say "3. venv in the Linux filesystem: $VENV"
# not under /mnt/c: a venv on NTFS is several times slower and a Windows venv and a Linux venv cannot share a folder
if [ -x "$VENV/bin/python" ] && ! inrange "$VENV/bin/python"; then
  old="$VENV-py$("$VENV/bin/python" -c 'import sys; print("%d%d" % sys.version_info[:2])')"
  if [ "${CARDIAC_RECREATE_VENV:-0}" = 1 ]; then
    mv "$VENV" "$old" && warn "existing venv was $("$old/bin/python" -V 2>&1) -> moved to $old (delete it once the new one works)"
  else
    warn "existing venv uses $("$VENV/bin/python" -V 2>&1), outside 3.10-3.12. Rerun with CARDIAC_RECREATE_VENV=1 to move it aside and rebuild."
  fi
fi
if [ ! -x "$VENV/bin/python" ]; then "$PY" -m venv "$VENV" || { warn "venv creation failed (Ubuntu: sudo apt install python3-venv, or python3.X-venv for $PY)"; exit 1; }; fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"
python -m pip install -q -U pip wheel && ok "venv ready: $(python -V)"

say "4. PyTorch with CUDA"
NVSMI=$(command -v nvidia-smi || { [ -x /usr/lib/wsl/lib/nvidia-smi ] && echo /usr/lib/wsl/lib/nvidia-smi; } || true)
if [ -n "$NVSMI" ]; then
  "$NVSMI" --query-gpu=name,driver_version,memory.total --format=csv,noheader | sed 's/^/  GPU: /'
else
  warn "nvidia-smi not found: install/update the NVIDIA driver on WINDOWS (never a Linux driver inside WSL), then 'wsl --shutdown' and reopen"
fi
if python -c "import torch, sys; sys.exit(0 if torch.version.cuda else 1)" 2>/dev/null; then
  ok "torch with CUDA already installed: $(python -c 'import torch; print(torch.__version__, "cuda", torch.version.cuda)')"
else
  echo "  installing torch (the CUDA runtime comes as pip wheels, ~2.5 GB -- takes a while)"
  if [ -n "$TORCH_INDEX" ]; then pip install -q torch --index-url "$TORCH_INDEX"; else pip install -q torch; fi \
    && ok "torch $(python -c 'import torch; print(torch.__version__, "cuda", torch.version.cuda)')" \
    || warn "torch install failed -- rerun this script (it resumes here)"
fi

say "5. project packages"
pip install -q -r "$REPO/requirements.txt" && ok "requirements.txt" || warn "requirements.txt failed -- see the pip output above"
pip install -q triangle && ok "triangle (optional: step-29 cut-face re-triangulation)" || warn "triangle failed (optional; the pipeline falls back to the old cap)"

say "6. environment -- managed block in ~/.bashrc"
if [ -n "${CARDIAC_DATA:-}" ]; then DATA="$CARDIAC_DATA"; elif [ -d /mnt/d ]; then DATA=/mnt/d/data; else DATA="$HOME/data"; fi
mkdir -p "$DATA/MM-WHS/ct_train"
python - "$HOME/.bashrc" "$REPO" "$DATA" "$VENV" <<'PYEOF'
import os, re, sys
rc, repo, data, venv = sys.argv[1:5]
block = (f'# >>> cardiac >>>  (written by tools/setup/setup_wsl.sh -- rerun it instead of editing)\n'
         f'export CARDIAC_REPO="{repo}"\n'
         f'export CARDIAC_DATA="{data}"          # data ROOT: MM-WHS is found in $CARDIAC_DATA/MM-WHS/ct_train\n'
         f'alias cardiac=\'source "{venv}/bin/activate" && cd "{repo}"\'\n'
         f'# <<< cardiac <<<\n')
s = open(rc).read() if os.path.exists(rc) else ""
s = re.sub(r"# >>> cardiac >>>.*?# <<< cardiac <<<\n?", "", s, flags=re.S)
open(rc, "w").write(s.rstrip("\n") + "\n\n" + block)
PYEOF
export CARDIAC_REPO="$REPO" CARDIAC_DATA="$DATA"
ok "CARDIAC_REPO=$REPO"
ok "CARDIAC_DATA=$DATA   (new shells get these; type 'cardiac' to activate the venv and cd to the repo)"

say "7. git settings for a clone on NTFS"
case "$REPO" in
  /mnt/[a-z]/*)
    git -C "$REPO" config core.filemode false
    git -C "$REPO" config core.autocrlf input
    ok "core.filemode=false, core.autocrlf=input (otherwise WSL sees every file as modified on the Windows drive)";;
  *) ok "clone is in the Linux filesystem -- nothing to change";;
esac
if [ -f "$REPO/tools/git-hooks/install.sh" ]; then
  sh "$REPO/tools/git-hooks/install.sh" >/dev/null && ok "pre-commit guard on (tools/repo_guard.py refuses data files, meshes, build output, secrets)"
fi

say "8. memory visible to WSL"
mem=$(awk '/MemTotal/ {printf "%d", $2/1024/1024}' /proc/meminfo)
if [ "$mem" -lt 20 ]; then
  warn "WSL sees ${mem} GiB (by default it gets half the machine). For the 20-case batch create C:\\Users\\<you>\\.wslconfig with:"
  printf '      [wsl2]\n      memory=24GB\n      swap=16GB\n'
  echo "    then run 'wsl --shutdown' in PowerShell and reopen WSL."
else
  ok "WSL sees ${mem} GiB"
fi

say "9. status"
python "$REPO/tools/setup/check_setup.py"
echo
echo "next: copy the transfer drive in (bash tools/setup/unpack_transfer.sh <drive folder>), then python tools/setup/gpu_smoke.py"
