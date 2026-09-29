#!/usr/bin/env bash
# Put the transferred files where the code expects them.  RTX 3060 machine, WSL, repo root, venv active:
#     bash tools/setup/unpack_transfer.sh /mnt/e/cardiac_transfer_2026-09-29 [--unreal]     # drive from make_transfer.ps1
#     bash tools/setup/unpack_transfer.sh /mnt/c/Users/wjsdm/Downloads [--unreal]           # or loose downloads
# The source can be the drive layout written by make_transfer.ps1, OR any folder holding the same things loose --
# e.g. downloaded from OneDrive on the web: sync_assets_*.zip, and the ct_train files either unzipped or as a zip
# (OneDrive zips a folder when you download it).  Inputs are found by name, not by position.
#   1. verifies every file against SHA256SUMS.txt when there is one (make_transfer.ps1 writes it)
#   2. ct_train_*.nii.gz -> $CARDIAC_DATA/MM-WHS/ct_train
#   3. sync_assets zip   -> the repo (fusion_ready/...), after proving every path in it is git-IGNORED
#   4. patient/          -> $CARDIAC_DATA/<name>   (only if present; never into the repo)
#   5. --unreal          -> python fusion_ready/export_unreal.py (the Unreal asset pack, ~1 min)
# Safe to rerun.  Nothing here writes to git.
set -uo pipefail
SRC="${1:?usage: unpack_transfer.sh <transfer folder> [--unreal]}"; shift || true
UNREAL=0; for a in "$@"; do [ "$a" = "--unreal" ] && UNREAL=1; done
REPO="${CARDIAC_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
DATA="${CARDIAC_DATA:-}"
[ -n "$DATA" ] || { echo "CARDIAC_DATA is not set -- run tools/setup/setup_wsl.sh first, then open a new shell"; exit 1; }
[ -d "$SRC" ] || { echo "no such folder: $SRC  (drive letters appear under /mnt/<letter> in WSL)"; exit 1; }
say() { printf '\n\033[1m== %s\033[0m\n' "$*"; }

say "1. verify (sha256; a few minutes for several GB over USB)"
if [ -f "$SRC/SHA256SUMS.txt" ]; then
  ( cd "$SRC" && tr -d '\r' < SHA256SUMS.txt | sha256sum -c --quiet ) || { echo "CHECKSUM MISMATCH -- recopy the drive, do not use these files"; exit 1; }
  echo "  all $(grep -c . "$SRC/SHA256SUMS.txt") files match"
else
  echo "  ! no SHA256SUMS.txt on the drive -- cannot verify; continuing"
fi

# ---- locate the MM-WHS files: a folder holding them (drive layout or unzipped download), else a zip that contains them.
#      No temp directory on purpose: a zip is extracted straight into the destination, so a failing mktemp can never
#      make unzip fall back to the current directory (= the repo).
DEST="$DATA/MM-WHS/ct_train"
CTDIR=$(find "$SRC" -maxdepth 4 -name 'ct_train_*_image.nii.gz' -printf '%h\n' 2>/dev/null | head -1)
CTZIP=""
if [ -z "$CTDIR" ]; then
  while IFS= read -r z; do
    if unzip -Z1 "$z" 2>/dev/null | grep -q 'ct_train_[0-9]*_image\.nii\.gz'; then CTZIP="$z"; break; fi
  done < <(find "$SRC" -maxdepth 3 -iname '*.zip' ! -name 'sync_assets_*' 2>/dev/null)
fi
if [ -n "$CTDIR" ] || [ -n "$CTZIP" ]; then
  say "2. MM-WHS (${CTDIR:-$CTZIP}) -> $DEST"
  mkdir -p "$DEST" || { echo "  cannot create $DEST"; exit 1; }
  if [ -n "$CTDIR" ]; then
    rsync -a --include='ct_train_*.nii.gz' --exclude='*' "$CTDIR/" "$DEST/"
  else
    unzip -o -q -j "$CTZIP" '*ct_train_*.nii.gz' -d "$DEST" || { echo "  unzip failed: $CTZIP"; exit 1; }
  fi
  ni=$(ls "$DEST"/ct_train_*_image.nii.gz 2>/dev/null | wc -l)
  nl=$(ls "$DEST"/ct_train_*_label.nii.gz 2>/dev/null | wc -l)
  echo "  $ni images / $nl labels (expect 20 / 20)"
else
  echo "  (no MM-WHS files found under $SRC -- skipped)"
fi

ZIP=$(find "$SRC" -maxdepth 3 -name 'sync_assets_*.zip' 2>/dev/null | head -1)
if [ -n "$ZIP" ]; then
  say "3. geometry assets -> repo"
  # prove BEFORE extracting that git will never pick any of these up (check-ignore works on paths that do not exist yet)
  bad=$(unzip -Z1 "$ZIP" | grep -v '/$' | while read -r f; do git -C "$REPO" check-ignore -q "$f" || echo "$f"; done)
  if [ -n "$bad" ]; then
    echo "  REFUSING: these paths would NOT be ignored by git (MM-WHS-derived meshes must never be committed):"
    echo "$bad" | head -20 | sed 's/^/    /'
    echo "  fix .gitignore first (git pull the latest commit), then rerun"; exit 1
  fi
  unzip -o -q "$ZIP" -d "$REPO" && echo "  $(unzip -Z1 "$ZIP" | grep -vc '/$') files unpacked, all git-ignored"
else
  echo "  (no sync_assets_*.zip found under $SRC -- geometry assets skipped; Unreal needs them)"
fi

if [ -d "$SRC/patient" ]; then
  say "4. patient-level data -> $DATA  (PhysioNet DUA: this machine only; never into the repo or a cloud folder)"
  for d in "$SRC"/patient/*/; do
    name=$(basename "$d"); mkdir -p "$DATA/$name"
    rsync -a "$d" "$DATA/$name/" && echo "  $name -> $DATA/$name"
  done
  echo "  when done: wipe the drive (or keep it encrypted)"
fi

if [ "$UNREAL" = 1 ]; then
  say "5. Unreal asset pack"
  ( cd "$REPO/fusion_ready" && python export_unreal.py ) || echo "  ! export_unreal.py failed -- is the venv active and were the geometry assets unpacked?"
fi

say "status"
python "$REPO/tools/setup/check_setup.py"
