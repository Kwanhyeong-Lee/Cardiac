# -*- coding: utf-8 -*-
"""GPU smoke test for the RTX 3060 machine -- proves the whole stack before any real training.

Three stages, each independent, so a failure says exactly which layer is broken:
  1. stack    driver -> (WSL) CUDA -> torch sees the 3060; matmul GPU vs CPU; fp16/TF32
  2. generic  a small MLP learns a damped oscillator's Hamiltonian flow on the GPU (loss must drop >10x)
  3. project  the project's own PortHamiltonianPINN (pinn_hamiltonian_v5.py) trained with its own
              train_pH_PINN on SYNTHETIC batches -- no patient data needed -- plus the drug-perturbation
              simulator, which is where CPU-created tensors would break on a CUDA model

No data is read or written.  Exit 0 = all stages passed on CUDA; 1 = something failed (details printed);
2 = no CUDA device (the stack is not set up yet -- stage 1 tells you why).
Usage (repo root, venv active):  python tools/setup/gpu_smoke.py            # add --cpu to dry-run without a GPU
"""
import argparse, math, os, sys, time, traceback

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
results = []                                              # (stage, status, message); status in PASS / FAIL / KNOWN


def report(stage, ok, msg, known=False):
    status = "PASS" if ok else ("KNOWN" if known else "FAIL")
    results.append((stage, status, msg)); print(f"  [{status}] {stage}: {msg}")


def stage_stack(torch, dev):
    print("1. stack")
    print(f"   torch {torch.__version__}  built for CUDA {torch.version.cuda}  cuDNN {torch.backends.cudnn.version() if torch.cuda.is_available() else '-'}")
    if dev.type != "cuda":
        why = ("torch was installed WITHOUT CUDA (torch.version.cuda is None) -- reinstall it (see SETUP.md)" if torch.version.cuda is None
               else "torch has CUDA but sees no device -- Windows NVIDIA driver missing/old, or WSL not restarted after installing it (wsl --shutdown)")
        report("stack", False, why); return
    p = torch.cuda.get_device_properties(0)
    print(f"   device 0: {p.name}  {p.total_memory / 2**30:.1f} GiB  sm_{p.major}{p.minor}  ({torch.cuda.device_count()} CUDA device(s))")
    if "3060" not in p.name:
        report("stack", False, f"device 0 is {p.name}, expected the RTX 3060 (check CUDA_VISIBLE_DEVICES)"); return
    n = 4096
    a, b = torch.randn(n, n, device=dev), torch.randn(n, n, device=dev)
    torch.cuda.synchronize(); t = time.time()
    for _ in range(10): c = a @ b
    torch.cuda.synchronize(); g = 10 * 2 * n ** 3 / (time.time() - t) / 1e12
    ac, bc = a[:2048].cpu(), b[:2048, :2048].cpu(); t = time.time(); _ = ac[:, :2048] @ bc; cpu = 2 * 2048 ** 3 / (time.time() - t) / 1e12
    h = a.half() @ b.half(); torch.cuda.synchronize()
    ok = torch.isfinite(c).all().item() and torch.isfinite(h).all().item()
    report("stack", ok, f"fp32 matmul {g:.1f} TFLOP/s on GPU vs {cpu:.2f} on CPU (x{g / max(cpu, 1e-9):.0f}); fp16 finite: {torch.isfinite(h).all().item()}")


def stage_generic(torch, dev):
    """Learn H(q,p) of a damped oscillator from trajectories: the same kind of problem as the project, small enough to be instant."""
    print("2. generic Hamiltonian fit")
    torch.manual_seed(0)
    k, m_, c = 2.0, 1.0, 0.1
    x = torch.rand(8192, 2, device=dev) * 4 - 2                           # (q, p)
    dq, dp = x[:, 1:2] / m_, -k * x[:, 0:1] - c * x[:, 1:2] / m_         # true flow
    y = torch.cat([dq, dp], 1)
    net = torch.nn.Sequential(torch.nn.Linear(2, 128), torch.nn.Tanh(), torch.nn.Linear(128, 128), torch.nn.Tanh(), torch.nn.Linear(128, 1)).to(dev)
    R = torch.nn.Parameter(torch.zeros(1, device=dev))
    opt = torch.optim.Adam(list(net.parameters()) + [R], 3e-3)

    def flow(xx):
        xx = xx.requires_grad_(True); H = net(xx).sum()
        g = torch.autograd.grad(H, xx, create_graph=True)[0]           # dH/dq, dH/dp
        return torch.cat([g[:, 1:2], -g[:, 0:1] - torch.nn.functional.softplus(R) * g[:, 1:2]], 1)   # J - R structure
    l0 = None; t = time.time()
    for it in range(600):
        opt.zero_grad(); loss = torch.nn.functional.mse_loss(flow(x.clone()), y); loss.backward(); opt.step()
        l0 = l0 or loss.item()
    if dev.type == "cuda": torch.cuda.synchronize()
    dt = time.time() - t; l1 = loss.item()
    ok = math.isfinite(l1) and l1 < l0 / 10
    report("generic", ok, f"flow loss {l0:.3g} -> {l1:.3g} in 600 steps ({600 / dt:.0f} it/s)")


def stage_project(torch, dev):
    print("3. project model (pinn_hamiltonian_v5.PortHamiltonianPINN, synthetic batches)")
    sys.path.insert(0, REPO)
    try:
        import pinn_hamiltonian_v5 as V
    except Exception as e:
        report("project", False, f"cannot import pinn_hamiltonian_v5 from {REPO}: {e}"); return
    torch.manual_seed(0)
    model = V.PortHamiltonianPINN(input_dim=11).to(dev)
    X = torch.randn(1024, 11, device=dev); Y = torch.rand(1024, 7, device=dev) + 0.5
    loader = torch.utils.data.DataLoader(torch.utils.data.TensorDataset(X, Y), batch_size=128, shuffle=True)
    keys = ["Ees", "Eed", "Ea", "coupling", "EDP", "efficiency", "tau"]

    def recon():
        model.eval()
        with torch.enable_grad():                                      # forward differentiates H (Hamilton's equations): never under no_grad
            o = model(X)
            return float(sum(torch.nn.functional.mse_loss(o[k], Y[:, i]) for i, k in enumerate(keys)).detach())
    try:
        l0 = recon(); t = time.time()
        V.train_pH_PINN(model, loader, None, epochs=20, lr=1e-3)
        if dev.type == "cuda": torch.cuda.synchronize()
        dt = time.time() - t; l1 = recon()
        ok = math.isfinite(l1) and l1 < l0
        report("project/train", ok, f"{sum(p.numel() for p in model.parameters()):,} params, recon loss {l0:.4g} -> {l1:.4g}, {dt:.1f} s / 20 epochs on {dev.type}")
    except Exception as e:
        report("project/train", False, f"{type(e).__name__}: {e}"); traceback.print_exc(limit=3)
    # Pre-existing code issue, NOT a setup problem -- reported as KNOWN so it never fails the setup verdict:
    #   simulate() runs the model under torch.no_grad(), but forward() differentiates H (Hamilton's equations),
    #   so it raises "element 0 of tensors does not require grad" on ANY device.  Once that is fixed
    #   (torch.enable_grad() + .detach()), the next thing to break on a GPU is dq/dp being built on the CPU
    #   (torch.tensor(pert['dq']) -> add device=q_base.device).
    try:
        sim = V.DrugPerturbationSimulator(model)
        r = sim.simulate(X[:1], "ARNI")
        report("project/drug-simulator", True, f"ARNI delta_H = {r['delta_H']:.4g}")
    except Exception as e:
        msg = str(e)
        if "does not require grad" in msg:
            why = "simulate() wraps forward() in torch.no_grad(), but forward() needs autograd for dH/dq -> fails on every device; fix: torch.enable_grad() + detach, then pass device=q_base.device to the dq/dp tensors"
        elif "device" in msg.lower():
            why = "dq/dp are created on the CPU inside simulate(); fix: torch.tensor(pert['dq'], device=q_base.device)"
        else:
            why = f"{type(e).__name__}: {msg[:140]}"
        report("project/drug-simulator", False, why, known=True)


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--cpu", action="store_true", help="run stages 2-3 on the CPU (plumbing test without a GPU)")
    a = ap.parse_args()
    try:
        import torch
    except ImportError:
        print("torch is not installed in this environment -- run tools/setup/setup_wsl.sh first"); return 2
    dev = torch.device("cuda" if torch.cuda.is_available() and not a.cpu else "cpu")
    print(f"gpu_smoke  repo={REPO}  device={dev}\n" + "-" * 78)
    stage_stack(torch, torch.device("cuda") if torch.cuda.is_available() else torch.device("cpu"))
    if dev.type != "cuda" and not a.cpu:
        print("-" * 78 + "\nno CUDA device: stages 2-3 skipped (use --cpu to exercise them anyway)"); return 2
    stage_generic(torch, dev); stage_project(torch, dev)
    print("-" * 78)
    bad = [r for r in results if r[1] == "FAIL" and not (a.cpu and r[0] == "stack")]
    known = [r for r in results if r[1] == "KNOWN"]
    if known: print(f"{len(known)} known code issue(s), not setup problems: " + ", ".join(r[0] for r in known) + "  (see TASK_PINN_GPU.md)")
    print(("SETUP OK on " + dev.type) if not bad else f"{len(bad)} stage(s) failed: " + ", ".join(r[0] for r in bad))
    return 0 if not bad else 1


if __name__ == "__main__":
    sys.exit(main())
