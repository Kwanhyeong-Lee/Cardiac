# -*- coding: utf-8 -*-
"""Repository guard: keeps patient data, MM-WHS-derived meshes, engine build output and secrets out of git.

Two modes, same rules:
  python3 tools/repo_guard.py --staged     what the pre-commit hook runs: checks only files being committed
  python3 tools/repo_guard.py              full scan of every tracked file (+ HEAD vs origin), e.g. before a push

Rules (HANDOVER §3, CLAUDE.md):
  * data-type extensions (csv parquet nii gz stl ply vtp glb fbx npz npy jsonl mat bin pt pth zip xlsx ...) are refused
    unless whitelisted below -- the whitelist is the four files tracked since the bundle plus two summary files
  * any file over 20 MB is refused (real data and meshes are big; code and figures are not)
  * Unreal build output (Binaries/ Intermediate/ Saved/ DerivedDataCache/ Content/ under fusion_ready/UNREAL/) is refused
  * data-like text files (json csv tsv txt) with >= 20 patient identifiers (subject_id, hadm_id, stay_id, caseid,
    patientunitstayid, op_id) are refused -- code and SQL that merely NAME those columns are fine
  * secret-looking strings (GitHub tokens, private keys, AWS keys) are refused
Stdlib only, so any python3 on PATH can run it.  Exit 0 = clean, 1 = refused (reasons printed).
There is no override flag on purpose: a real exception belongs in WHITELIST below, in a reviewed commit.
"""
import argparse, os, re, subprocess, sys

DATA_EXT = {".csv", ".tsv", ".parquet", ".feather", ".nii", ".gz", ".nrrd", ".mha", ".dcm", ".stl", ".ply", ".vtp", ".vtk", ".vtu",
            ".glb", ".gltf", ".fbx", ".obj", ".npz", ".npy", ".jsonl", ".mat", ".h5", ".hdf5", ".bin", ".pt", ".pth", ".ckpt",
            ".zip", ".7z", ".tar", ".xlsx", ".xls", ".db", ".sqlite", ".blend"}
WHITELIST = {
    "heart_failure_clinical_records.csv",              # UCI public dataset (tracked since the bundle)
    "lv_cfd/mitral_flow_profile.csv",                  # synthetic inflow profile
    "manuscript/pH_PINN_JBHI_arXiv_source.tar.gz",     # manuscript LaTeX source
    "manuscript/pH_PINN_JBHI_LaTeX_main.zip",          # manuscript LaTeX bundle (HANDOVER §3 allow-list: "LaTeX zip")
    "synth_cardiotox_dataset.csv",                     # synthetic
    "business/COGS_model_v1.xlsx",                     # cost model (no patient data)
    "fusion_ready/CT/cases/SUMMARY.csv",               # per-case aggregate table, no voxels
}
BUILD = re.compile(r"^fusion_ready/UNREAL/[^/]+/(Binaries|Intermediate|Saved|DerivedDataCache|Content|Build)/")
IDS = re.compile(r"\b(subject_id|hadm_id|stay_id|caseid|patientunitstayid|op_id)\b")
SECRET = re.compile(r"(ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,}|gho_[A-Za-z0-9]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|AKIA[0-9A-Z]{16})")
TEXT_EXT = {".py", ".md", ".txt", ".json", ".csv", ".tsv", ".js", ".ts", ".sh", ".ps1", ".yml", ".yaml", ".ini", ".cfg", ".toml",
            ".cs", ".cpp", ".h", ".r", ".R", ".m", ".sql", ".tex", ".html"}
ID_EXT = {".json", ".csv", ".tsv", ".txt"}                 # where an identifier count means rows, not column names
MAX_MB = 20


def git(*args, repo):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True)
    return r.returncode, r.stdout


def ext_of(path):
    p = path.lower()
    return ".gz" if p.endswith(".nii.gz") or p.endswith(".tar.gz") else os.path.splitext(p)[1]


def content(path, staged, repo):
    """bytes of the version being committed (staged) or of the working-tree file (full scan)."""
    if staged:
        rc, out = git("show", f":{path}", repo=repo)
        return out if rc == 0 else b""
    try:
        with open(os.path.join(repo, path), "rb") as f: return f.read()
    except OSError:
        return b""


def check(paths, staged, repo):
    problems = []
    for p in paths:
        e = ext_of(p)
        if e in DATA_EXT and p not in WHITELIST:
            problems.append(f"data-type file: {p}   (patient data / MM-WHS-derived meshes never go into git -- HANDOVER §3)")
            continue
        if BUILD.match(p):
            problems.append(f"Unreal build output: {p}"); continue
        size = None
        if staged:
            rc, out = git("cat-file", "-s", f":{p}", repo=repo)
            size = int(out.strip() or 0) if rc == 0 else 0
        elif os.path.exists(os.path.join(repo, p)):
            size = os.path.getsize(os.path.join(repo, p))
        if size and size > MAX_MB * 2 ** 20:
            problems.append(f"file over {MAX_MB} MB: {p} ({size / 2 ** 20:.0f} MB)"); continue
        if e in TEXT_EXT or os.path.basename(p) in (".gitignore", ".gitattributes"):
            b = content(p, staged, repo)
            if len(b) > 5 * 2 ** 20: continue
            t = b.decode("utf-8", "ignore")
            n = len(IDS.findall(t)) if e in ID_EXT else 0
            if n >= 20 and p not in WHITELIST:
                problems.append(f"{n} patient identifiers in {p}   (per-patient tables stay outside the repo)")
            s = SECRET.search(t)
            if s and not p.endswith("repo_guard.py"):
                problems.append(f"secret-like string in {p}: {s.group(0)[:12]}...")
    return problems


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--staged", action="store_true"); ap.add_argument("--repo", default=None)
    a = ap.parse_args()
    repo = a.repo or subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or "."
    if a.staged:
        rc, out = git("diff", "--cached", "--name-only", "--diff-filter=ACMR", "-z", repo=repo)
        paths = [p for p in out.decode("utf-8", "replace").split("\0") if p]
    else:
        rc, out = git("ls-files", "-z", repo=repo)
        paths = [p for p in out.decode("utf-8", "replace").split("\0") if p]
    problems = check(paths, a.staged, repo)
    label = "staged" if a.staged else "tracked"
    if problems:
        print(f"repo_guard: REFUSED -- {len(problems)} problem(s) in {len(paths)} {label} file(s):", file=sys.stderr)
        for p in problems[:40]: print("  - " + p, file=sys.stderr)
        if a.staged:
            print("Unstage them (git restore --staged <file>) and check .gitignore. Do not bypass with --no-verify.", file=sys.stderr)
        return 1
    print(f"repo_guard: OK ({len(paths)} {label} file(s))")
    if not a.staged:                                                       # full mode: also say whether HEAD is pushed
        git("fetch", "--quiet", "origin", repo=repo)
        _, br = git("rev-parse", "--abbrev-ref", "HEAD", repo=repo)
        _, cnt = git("rev-list", "--left-right", "--count", f"origin/{br.decode().strip()}...HEAD", repo=repo)
        parts = cnt.decode().split()
        if len(parts) == 2: print(f"repo_guard: behind origin {parts[0]}, ahead {parts[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
