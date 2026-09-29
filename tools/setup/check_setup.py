# -*- coding: utf-8 -*-
"""Is this machine ready?  Read-only status check for the RTX 3060 machine (works on any machine).

Answers three questions separately -- geometry pipeline / PINN GPU training / Unreal app -- because the machine
can be ready for one and not the others, and each needs different things.  Never installs, writes, fetches or
reads patient data; it only looks at versions, paths, counts and git state.

Usage (repo root, venv active):   python tools/setup/check_setup.py          [--fetch]  update origin refs first
Exit 0 = everything required for all three purposes is in place; 1 = something missing (see NEXT STEPS).
"""
import argparse, glob, importlib, json, os, platform, re, shutil, subprocess, sys

REPO = os.environ.get("CARDIAC_REPO") or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
rows, nexts = [], []                      # rows: (section, check, status, detail, purposes)
PURPOSES = ("geometry", "pinn", "unreal")


def add(section, check, status, detail="", purposes=(), fix=None):
    rows.append((section, check, status, detail, tuple(purposes)))
    if status == "FAIL" and fix and fix not in nexts: nexts.append(fix)


def sh(cmd, cwd=None, timeout=20):
    try:
        r = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, errors="replace")
        return r.returncode, r.stdout.strip(), r.stderr.strip()
    except Exception as e:
        return 1, "", str(e)


def gib(n): return n / 2 ** 30


# ------------------------------------------------------------------ system
def check_system():
    wsl = "microsoft" in platform.uname().release.lower() or os.path.exists("/proc/sys/fs/binfmt_misc/WSLInterop")
    add("system", "platform", "OK" if wsl else "INFO", f"{'WSL2' if wsl else platform.system()} {platform.release()[:40]}")
    try:
        mem = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        st = "OK" if gib(mem) >= 20 else "WARN"
        add("system", "RAM visible", st, f"{gib(mem):.0f} GiB" + ("" if st == "OK" else " -- WSL gets half the machine by default; .wslconfig memory=24GB for the 20-case batch"), ("geometry",))
    except (ValueError, OSError, AttributeError):
        pass
    add("system", "CPU threads", "INFO", str(os.cpu_count()))
    for label, path, need in (("disk (repo)", REPO, 15), ("disk (data)", os.environ.get("CARDIAC_DATA", ""), 20)):
        if path and os.path.exists(path):
            free = gib(shutil.disk_usage(path).free)
            add("system", label, "OK" if free >= need else "WARN", f"{free:.0f} GiB free at {path}")


# ------------------------------------------------------------------ python
REQUIRED = {"numpy": "all", "scipy": "all", "pandas": "all", "sklearn": "pinn", "matplotlib": "all", "skimage": "geometry", "nibabel": "geometry",
            "trimesh": "geometry", "manifold3d": "geometry", "pymeshfix": "geometry", "shapely": "geometry", "networkx": "geometry",
            "fast_simplification": "geometry", "rtree": "geometry", "mapbox_earcut": "geometry", "torch": "pinn"}
OPTIONAL = {"triangle": "geometry (step 29 cut-face re-triangulation; without it the old cap is kept)"}


def check_python():
    v = sys.version_info
    add("python", "version", "OK" if (3, 10) <= v[:2] <= (3, 12) else "WARN", f"{v.major}.{v.minor}.{v.micro}  ({sys.executable})", PURPOSES)
    in_venv = sys.prefix != getattr(sys, "base_prefix", sys.prefix)
    on_ntfs = sys.prefix.startswith("/mnt/")
    add("python", "venv", "OK" if in_venv and not on_ntfs else "WARN",
        ("active: " + sys.prefix) if in_venv else "no venv active -- run: source ~/.venvs/cardiac/bin/activate  (or the 'cardiac' alias)"
        + (" (venv on /mnt/* is slow; keep it in the Linux filesystem)" if on_ntfs else ""), PURPOSES)
    for mod, purpose in REQUIRED.items():
        try:
            m = importlib.import_module(mod); ver = getattr(m, "__version__", "?")
            add("python", mod, "OK", str(ver), (purpose,) if purpose != "all" else PURPOSES)
        except Exception as e:
            add("python", mod, "FAIL", f"not importable ({type(e).__name__})", (purpose,) if purpose != "all" else PURPOSES,
                fix="install the Python packages: bash tools/setup/setup_wsl.sh")
    for mod, why in OPTIONAL.items():
        try:
            importlib.import_module(mod); add("python", mod, "OK", "optional, present")
        except Exception:
            add("python", mod, "WARN", f"optional, missing -- {why}")


# ------------------------------------------------------------------ gpu
def check_gpu():
    nvsmi = shutil.which("nvidia-smi") or ("/usr/lib/wsl/lib/nvidia-smi" if os.path.exists("/usr/lib/wsl/lib/nvidia-smi") else None)
    if nvsmi:
        rc, out, _ = sh([nvsmi, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"])
        add("gpu", "driver (nvidia-smi)", "OK" if rc == 0 and out else "FAIL", out.replace("\n", " | ") or "nvidia-smi failed", ("pinn",),
            fix="install/update the NVIDIA driver on WINDOWS (never inside WSL), then `wsl --shutdown` and reopen the terminal")
    else:
        add("gpu", "driver (nvidia-smi)", "FAIL", "nvidia-smi not found", ("pinn",),
            fix="install/update the NVIDIA driver on WINDOWS (never inside WSL), then `wsl --shutdown` and reopen the terminal")
    try:
        import torch
    except Exception:
        add("gpu", "torch CUDA", "FAIL", "torch not installed", ("pinn",), fix="install the Python packages: bash tools/setup/setup_wsl.sh"); return
    if torch.version.cuda is None:
        add("gpu", "torch CUDA build", "FAIL", f"torch {torch.__version__} is a CPU-only build", ("pinn",),
            fix="reinstall torch with CUDA: pip uninstall -y torch && pip install torch   (Linux PyPI wheels are CUDA builds)")
        return
    if not torch.cuda.is_available():
        add("gpu", "torch sees GPU", "FAIL", f"torch {torch.__version__} (CUDA {torch.version.cuda}) but no device", ("pinn",),
            fix="torch has CUDA but no device: update the Windows NVIDIA driver, then `wsl --shutdown`")
        return
    name = torch.cuda.get_device_name(0)
    add("gpu", "torch sees GPU", "OK" if "3060" in name else "WARN", f"{name} via torch {torch.__version__} / CUDA {torch.version.cuda}", ("pinn",))


# ------------------------------------------------------------------ repo
def check_repo(fetch):
    add("repo", "path", "OK" if REPO.startswith("/mnt/") else "WARN", REPO + ("" if REPO.startswith("/mnt/") else "  (Unreal on Windows cannot build a clone that lives only inside WSL)"), ("unreal",))
    rc, url, _ = sh(["git", "-C", REPO, "remote", "get-url", "origin"])
    if rc != 0:
        add("repo", "git", "FAIL", "not a git clone", PURPOSES, fix="clone the repository to /mnt/c/work/Cardiac (see SETUP.md step C1)"); return
    add("repo", "origin", "INFO", re.sub(r"//[^@/]+@", "//***@", url))       # never print a token embedded in the URL
    if fetch: sh(["git", "-C", REPO, "fetch", "--quiet", "origin"], timeout=60)
    _, br, _ = sh(["git", "-C", REPO, "rev-parse", "--abbrev-ref", "HEAD"])
    _, head, _ = sh(["git", "-C", REPO, "log", "-1", "--format=%h %s"])
    _, cnt, _ = sh(["git", "-C", REPO, "rev-list", "--left-right", "--count", f"origin/{br}...HEAD"])
    behind, ahead = (cnt.split() + ["?", "?"])[:2]
    add("repo", "HEAD", "OK" if behind in ("0", "?") else "WARN", f"{br} @ {head[:70]}  (behind {behind} / ahead {ahead} of origin{'' if fetch else ', local refs -- add --fetch'})")
    _, dirty, _ = sh(["git", "-C", REPO, "status", "--porcelain"])
    n = len([l for l in dirty.splitlines() if l.strip()])
    add("repo", "working tree", "OK" if n == 0 else "WARN", "clean" if n == 0 else f"{n} changed/untracked file(s)")
    _, fm, _ = sh(["git", "-C", REPO, "config", "core.filemode"])
    if REPO.startswith("/mnt/"):
        add("repo", "core.filemode", "OK" if fm == "false" else "WARN", fm or "unset" + ("" if fm == "false" else " -- set false, or every file shows as modified on NTFS"))
    for rel, purpose in (("fusion_ready/case_paths.py", "geometry"), ("pinn_hamiltonian_v5.py", "pinn"), ("fusion_ready/UNREAL/HeartTeach/HeartTeach.uproject", "unreal")):
        add("repo", rel, "OK" if os.path.exists(os.path.join(REPO, rel)) else "FAIL", "", (purpose,), fix="pull the latest commit: git pull")


# ------------------------------------------------------------------ data
def check_data():
    root = os.environ.get("CARDIAC_DATA")
    if not root:
        add("data", "CARDIAC_DATA", "FAIL", "not set", ("geometry",), fix="open a new shell after setup_wsl.sh (it sets CARDIAC_DATA), or export CARDIAC_DATA=/mnt/d/data"); return
    add("data", "CARDIAC_DATA", "OK" if os.path.isdir(root) else "FAIL", root, ("geometry",), fix=f"mkdir -p {root}/MM-WHS/ct_train")
    sys.path.insert(0, os.path.join(REPO, "fusion_ready"))
    try:
        from case_paths import resolve_mmwhs
        ct = resolve_mmwhs()
    except Exception:
        ct = os.path.join(root, "MM-WHS", "ct_train")
    imgs = glob.glob(os.path.join(ct, "ct_train_*_image.nii.gz")); labs = glob.glob(os.path.join(ct, "ct_train_*_label.nii.gz"))
    st = "OK" if len(imgs) == 20 and len(labs) == 20 else ("WARN" if imgs else "FAIL")
    add("data", "MM-WHS ct_train", st, f"{len(imgs)} images / {len(labs)} labels in {ct}  (expect 20/20)", ("geometry",),
        fix="copy MM-WHS from the transfer drive: bash tools/setup/unpack_transfer.sh <drive folder>")
    for name in ("MIMIC IV", "eicu", "INSPIRE", "vitaldb"):            # presence only; contents are never opened
        p = os.path.join(root, name)
        if os.path.isdir(p): add("data", name, "INFO", "present (not opened -- PhysioNet/registration terms apply)")


# ------------------------------------------------------------------ geometry assets (from the drive)
ASSET_SENTINELS = ["fusion_ready/BLENDER_OUT/LV_v6_noplate.stl", "fusion_ready/CT/hires/LV_myocardium_CT_hires.stl",
                   "fusion_ready/CT/whole_heart_hollow/whole_heart_hollow_v2_4ch_A.stl", "fusion_ready/CT/whole_heart_hollow/parts/LV_myocardium.ply",
                   "fusion_ready/CT/coronary/territories/LV_myocardium_territories.ply"]


def check_assets():
    have = [a for a in ASSET_SENTINELS if os.path.exists(os.path.join(REPO, a))]
    add("assets", "case-1009 geometry", "OK" if len(have) == len(ASSET_SENTINELS) else "FAIL",
        f"{len(have)}/{len(ASSET_SENTINELS)} sentinel files", ("unreal",),
        fix="unpack the geometry assets from the transfer drive: bash tools/setup/unpack_transfer.sh <drive folder>")
    tracked = [a for a in have if sh(["git", "-C", REPO, "check-ignore", "-q", a])[0] != 0]
    if have:
        add("assets", "ignored by git", "OK" if not tracked else "FAIL", "all ignored" if not tracked else f"TRACKABLE: {tracked}", ("unreal",),
            fix="assets must never be committed: check .gitignore before any `git add`")


# ------------------------------------------------------------------ unreal
def check_unreal():
    eds = sorted(glob.glob("/mnt/c/Program Files/Epic Games/UE_5.*/Engine/Binaries/Win64/UnrealEditor.exe"))
    vers = [re.search(r"UE_(5\.\d+)", e).group(1) for e in eds]
    add("unreal", "Unreal Engine", "OK" if vers else "FAIL", ", ".join(vers) if vers else "no UE_5.x under C:\\Program Files\\Epic Games", ("unreal",),
        fix="install Unreal Engine 5.4+ from the Epic Games Launcher (Windows)")
    up = os.path.join(REPO, "fusion_ready/UNREAL/HeartTeach/HeartTeach.uproject")
    if os.path.exists(up) and vers:
        want = json.load(open(up, encoding="utf-8")).get("EngineAssociation", "?")
        add("unreal", "EngineAssociation", "OK" if want in vers else "WARN", f"uproject asks {want}, installed {', '.join(vers)}" + ("" if want in vers else " -- TASK_UNREAL step 2 sets it"))
    vsw = "/mnt/c/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe"
    if os.path.exists(vsw):
        rc, out, _ = sh([vsw, "-latest", "-products", "*", "-requires", "Microsoft.VisualStudio.Component.VC.Tools.x86.x64", "-property", "displayName"])
        add("unreal", "Visual Studio C++", "OK" if rc == 0 and out else "FAIL", out or "no VS with the C++ (VC.Tools) workload", ("unreal",),
            fix="install Visual Studio 2022 with 'Desktop development with C++' and 'Game development with C++'")
    else:
        add("unreal", "Visual Studio C++", "FAIL", "vswhere.exe not found (Visual Studio not installed)", ("unreal",),
            fix="install Visual Studio 2022 with 'Desktop development with C++' and 'Game development with C++'")
    pack = os.path.join(REPO, "fusion_ready/UNREAL/1009")
    n = len(glob.glob(os.path.join(pack, "**/*.glb"), recursive=True))
    add("unreal", "asset pack", "OK" if n >= 20 and os.path.exists(os.path.join(pack, "unreal_manifest.json")) else "WARN",
        f"{n} glb in fusion_ready/UNREAL/1009" + ("" if n >= 20 else " -- generate it: python fusion_ready/export_unreal.py (after the assets are unpacked)"), ("unreal",))


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--fetch", action="store_true"); a = ap.parse_args()
    for f in (check_system, check_python, check_gpu, lambda: check_repo(a.fetch), check_data, check_assets, check_unreal):
        try: f()
        except Exception as e: add("internal", getattr(f, "__name__", "check"), "WARN", f"{type(e).__name__}: {e}")
    mark = {"OK": "✓", "WARN": "!", "FAIL": "✗", "INFO": "·"}
    sec = None
    print(f"check_setup   repo {REPO}")
    for s, c, st, d, _ in rows:
        if s != sec: print(f"\n[{s}]"); sec = s
        print(f"  {mark[st]} {c:26s} {d}")
    print("\n" + "=" * 78)
    ready = {}
    for p in PURPOSES:
        blockers = [c for s, c, st, d, ps in rows if st == "FAIL" and p in ps]
        ready[p] = not blockers
        print(f"  {p:9s} {'READY' if not blockers else 'NOT READY  <- ' + ', '.join(blockers)}")
    if nexts:
        print("\nNEXT STEPS"); [print(f"  {i}. {n}") for i, n in enumerate(nexts, 1)]
    return 0 if all(ready.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
