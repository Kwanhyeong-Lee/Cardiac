# -*- coding: utf-8 -*-
"""Paper 2 — waveform-input pH-PINN and the three ablation comparators.

The energy structure is carried over unchanged from Paper 1 (PROTOCOL.md §4); only the
input encoder differs, taking waveform morphology descriptors instead of an 11-dimensional
clinical feature vector.

Guarantees in model A, by construction rather than by penalty:
    T, V >= 0            softplus outputs
    H  = T + V           algebraic composition, H is never predicted separately
    R  = L L^T  >= 0     Cholesky parameterisation of the dissipation matrix
so the passivity inequality dH/dt <= y^T u holds pointwise for every input, including
inputs outside the training distribution.
"""
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# ---- model inputs: waveform shape only. None of these enters a target formula. ----
MORPH_COLS = [
    "SBP", "DBP", "PP", "MAP", "HR",
    "t_sys_peak", "t_notch", "notch_frac_time", "P_notch", "notch_frac",
    "max_dPdt", "min_dPdt", "area_sys", "area_dia", "area_ratio",
    "form_factor", "upstroke_time", "beat_len", "skew", "kurt", "beat_sd",
]
# level-only subset, for the "morphology removed" negative control (PROTOCOL.md §4.1)
LEVEL_COLS = ["SBP", "DBP", "PP", "MAP", "HR"]

# v3 (PROTOCOL.md §6, 2026-07-30). FloTrac computes CO as HR*sigma(AP)*chi, where chi is
# calibrated on patient demographics. Asking a model to reproduce that from waveform alone
# withholds an input the reference device has. Demographics are not arguments of the
# thermodilution measurement, so adding them does not affect the primary endpoint's
# independence.
DEMO_COLS = ["age", "sex", "height", "weight", "bmi", "bsa"]
MORPH_DEMO_COLS = MORPH_COLS + DEMO_COLS
DEMO_ONLY_COLS = DEMO_COLS + ["HR", "MAP"]   # control: how far do demographics alone go?

STATE_DIM = 5          # x = (q, p): q = (V_LV, V_LA, V_art), p = (p_mv, p_ao)


class Encoder(nn.Module):
    def __init__(self, n_in, width=128, depth=3, p_drop=0.1):
        super().__init__()
        layers, d = [], n_in
        for _ in range(depth):
            layers += [nn.Linear(d, width), nn.SiLU(), nn.Dropout(p_drop)]
            d = width
        self.net = nn.Sequential(*layers)
        self.out_dim = width

    def forward(self, x):
        return self.net(x)


class PHPINN(nn.Module):
    """Model A — hard architectural constraints."""

    def __init__(self, n_in, n_out, width=128):
        super().__init__()
        self.enc = Encoder(n_in, width)
        h = self.enc.out_dim
        self.state = nn.Linear(h, STATE_DIM)
        self.T_head = nn.Linear(h, 1)
        self.V_head = nn.Linear(h, 1)
        # lower-triangular Cholesky factor of R
        self.n_tri = STATE_DIM * (STATE_DIM + 1) // 2
        self.L_head = nn.Linear(h, self.n_tri)
        self.dec = nn.Sequential(nn.Linear(h + STATE_DIM + 2, width), nn.SiLU(),
                                 nn.Linear(width, n_out))
        idx = torch.tril_indices(STATE_DIM, STATE_DIM)
        self.register_buffer("tri_i", idx[0])
        self.register_buffer("tri_j", idx[1])

    def energies(self, h):
        T = F.softplus(self.T_head(h))          # T >= 0 by construction
        V = F.softplus(self.V_head(h))          # V >= 0 by construction
        return T, V, T + V                      # H = T + V, never predicted directly

    def dissipation(self, h):
        v = self.L_head(h)
        L = h.new_zeros(h.shape[0], STATE_DIM, STATE_DIM)
        L[:, self.tri_i, self.tri_j] = v
        d = torch.arange(STATE_DIM, device=h.device)
        L[:, d, d] = F.softplus(L[:, d, d]) + 1e-6      # positive diagonal
        return L @ L.transpose(1, 2)                     # R = L L^T >= 0

    def forward(self, x):
        h = self.enc(x)
        T, V, H = self.energies(h)
        R = self.dissipation(h)
        s = self.state(h)
        y = self.dec(torch.cat([h, s, T, V], dim=1))
        return y, H, T, V, R


class VanillaMLP(nn.Module):
    """Model B — no physics structure. Energies are free outputs."""

    def __init__(self, n_in, n_out, width=160):
        super().__init__()
        self.enc = Encoder(n_in, width)
        h = self.enc.out_dim
        self.head = nn.Linear(h, n_out)
        self.aux = nn.Linear(h, 3)              # H, T, V, unconstrained and unrelated

    def forward(self, x):
        h = self.enc(x)
        a = self.aux(h)
        return self.head(h), a[:, 0:1], a[:, 1:2], a[:, 2:3], None


class NoStructurePINN(nn.Module):
    """Model C — topology identical to A, hard constraints removed."""

    def __init__(self, n_in, n_out, width=128):
        super().__init__()
        self.enc = Encoder(n_in, width)
        h = self.enc.out_dim
        self.state = nn.Linear(h, STATE_DIM)
        self.T_head = nn.Linear(h, 1)
        self.V_head = nn.Linear(h, 1)
        self.H_head = nn.Linear(h, 1)           # H predicted separately, not composed
        self.n_tri = STATE_DIM * (STATE_DIM + 1) // 2
        self.R_head = nn.Linear(h, STATE_DIM * STATE_DIM)
        self.dec = nn.Sequential(nn.Linear(h + STATE_DIM + 2, width), nn.SiLU(),
                                 nn.Linear(width, n_out))

    def forward(self, x):
        h = self.enc(x)
        T, V, H = self.T_head(h), self.V_head(h), self.H_head(h)   # no softplus
        M = self.R_head(h).view(-1, STATE_DIM, STATE_DIM)
        R = 0.5 * (M + M.transpose(1, 2))       # symmetric, but not PSD
        s = self.state(h)
        y = self.dec(torch.cat([h, s, T, V], dim=1))
        return y, H, T, V, R


class SoftConstraintPINN(NoStructurePINN):
    """Model D — same as C; the constraints are added to the loss, not the architecture.
    Distinguished from C only by how it is trained (see `physics_penalty`)."""
    pass


def physics_penalty(H, T, V, R, weight=1.0):
    """Penalty used only by model D. It makes violations rare, not impossible."""
    loss = F.relu(-T).pow(2).mean() + F.relu(-V).pow(2).mean()
    loss = loss + (H - (T + V)).pow(2).mean()
    if R is not None:
        loss = loss + F.relu(-torch.linalg.eigvalsh(R)).pow(2).mean()
    return weight * loss


def violations(H, T, V, R):
    """Physical-validity diagnostics on a held-out set."""
    H, T, V = H.detach(), T.detach(), V.detach()
    R = R.detach() if R is not None else None
    out = {
        "T_neg": int((T < 0).sum()),
        "V_neg": int((V < 0).sum()),
        "HTV_mse": float(((H - (T + V)) ** 2).mean()),
    }
    if R is None:
        out["R_nonpsd"] = -1                     # model has no dissipation matrix
    else:
        # A *relative* tolerance is required. R = LL^T is positive semidefinite as a
        # matter of algebra, but its eigenvalues span 10^3-10^4 at extreme inputs, and a
        # float32 eigendecomposition then returns values around -1e-4 -- a relative
        # magnitude of ~1e-7, i.e. float32 epsilon. Judged against a fixed -1e-6 those
        # register as violations of a property that cannot actually be violated. The
        # earlier absolute threshold produced exactly such phantom counts (2026-07-30).
        ev = torch.linalg.eigvalsh(R.double())
        lam_min = ev.min(dim=1).values
        lam_max = ev.max(dim=1).values.clamp_min(1e-30)
        out["R_nonpsd"] = int((lam_min < -1e-6 * lam_max).sum())
        out["R_min_rel"] = float((lam_min / lam_max).min())
    return out


class OutputConstrainedPHPINN(PHPINN):
    """Model E — model A with the guarantee propagated to the output.

    The out-of-distribution probe (2026-07-30) showed that A keeps T, V and R admissible
    at every input, while the quantity a clinician actually reads -- cardiac output -- went
    to -17.6 L/min at 12 sigma, no better than the unconstrained model C. The softplus and
    the Cholesky factorisation constrain the internal energy objects; the decoder that
    produces y is an ordinary linear map and is free to emit anything.

    Here the output is not decoded freely. Stroke volume and heart period are emitted as
    strictly positive quantities and the output is formed as their quotient:

        CO = SV / T_period,     SV > 0,  T_period > 0

    so CO > 0 holds for every input, by the same kind of construction that makes T >= 0
    hold. The constraint is a property of the architecture's range, not of the training
    distribution.

    Reported on the standardised scale like every other model, so the comparison with
    A/B/C/D is unaffected: `_scale` and `_shift` are learned affine parameters that let the
    positive physical quantity match the standardised target the loss is computed against.
    """

    def __init__(self, n_in, n_out, width=128):
        super().__init__(n_in, n_out, width)
        h = self.enc.out_dim
        self.sv_head = nn.Linear(h + STATE_DIM + 2, 1)      # stroke volume,  > 0
        self.tp_head = nn.Linear(h + STATE_DIM + 2, 1)      # heart period,   > 0
        self._scale = nn.Parameter(torch.ones(1))
        self._shift = nn.Parameter(torch.zeros(1))
        self.dec = None                                      # unused; kept out of the graph

    def forward(self, x):
        h = self.enc(x)
        T, V, H = self.energies(h)
        R = self.dissipation(h)
        s = self.state(h)
        z = torch.cat([h, s, T, V], dim=1)
        sv = F.softplus(self.sv_head(z)) + 1e-4              # > 0 by construction
        tp = F.softplus(self.tp_head(z)) + 1e-2              # > 0 by construction
        co = sv / tp                                         # > 0 for every input
        y = self._scale * co + self._shift
        return y, H, T, V, R

    def physical_output(self, x):
        """The output on its physical scale, before the affine map to the target scale."""
        with torch.no_grad():
            h = self.enc(x)
            T, V, _ = self.energies(h)
            z = torch.cat([h, self.state(h), T, V], dim=1)
            return ((F.softplus(self.sv_head(z)) + 1e-4)
                    / (F.softplus(self.tp_head(z)) + 1e-2))


class TrueOutputConstrainedPHPINN(PHPINN):
    """Model E3 — the output guarantee made architectural instead of learned.

    WHY E AND E2 DO NOT ACTUALLY GUARANTEE ANYTHING (independent audit, 2026-08-12).
    Models E and E2 form CO = softplus(sv)/softplus(tp) > 0 and then map it to the
    standardised target scale with two *free* parameters:

        y = _scale * co + _shift          _scale, _shift unconstrained nn.Parameter

    Nothing prevents `_scale < 0`, which makes y unbounded below and voids the guarantee
    entirely. In the six fits actually run, `_scale` landed in [0.989, 1.003] and `_shift`
    in [-0.936, -0.913], so the *learned* offset put a floor at 3.43-3.49 L/min. Every
    "0 negative outputs at 40 sigma" for E and E2 is that offset, not the softplus: the
    reported minimum was identical to three decimals at 0, 6, 12, 24 and 40 sigma because
    it is the analytic floor, reached in every condition.

    Worse, the floor is not free. 15.9% of the reference cardiac outputs lie below
    3.43 L/min -- the clinically dangerous end -- and E/E2 cannot represent them. On
    held-out windows 13.6-14.0% of predictions sit within 0.10 L/min of the floor with
    softplus(sv_head) saturated to ~5e-13.

    THE FIX. The map to the standardised scale is not a free affine layer; it is the
    inverse of a known standardisation. Registering the target scaler's mean and scale as
    buffers makes it exact:

        y = (co - y_mean) / y_scale,    co > 0

    so y > -y_mean/y_scale, which is the standardised image of CO = 0, and CO > 0 holds by
    algebra for every input with no learned quantity involved and no floor above zero.
    `set_target_scale` must be called before training; the model refuses to run otherwise.
    """

    def __init__(self, n_in, n_out, width=128, head_width=64):
        super().__init__(n_in, n_out, width)
        z_dim = self.enc.out_dim + STATE_DIM + 2
        self.sv_head = nn.Sequential(nn.Linear(z_dim, head_width), nn.SiLU(),
                                     nn.Linear(head_width, 1))
        self.tp_head = nn.Sequential(nn.Linear(z_dim, head_width), nn.SiLU(),
                                     nn.Linear(head_width, 1))
        self.dec = None
        self.register_buffer("y_mean", torch.full((1,), float("nan")))
        self.register_buffer("y_scale", torch.full((1,), float("nan")))

    def set_target_scale(self, mean, scale):
        """Fix the affine map from the fitted target StandardScaler. Not learned."""
        self.y_mean.fill_(float(mean))
        self.y_scale.fill_(float(scale))
        return self

    def physical_output(self, x):
        h = self.enc(x)
        T, V, _ = self.energies(h)
        z = torch.cat([h, self.state(h), T, V], dim=1)
        sv = F.softplus(self.sv_head(z)) + 1e-4
        tp = F.softplus(self.tp_head(z)) + 1e-2
        return sv / tp                                   # L/min, > 0 for every input

    def forward(self, x):
        if torch.isnan(self.y_scale).any():
            raise RuntimeError("call set_target_scale(mean, scale) before using model E3")
        h = self.enc(x)
        T, V, H = self.energies(h)
        R = self.dissipation(h)
        s = self.state(h)
        z = torch.cat([h, s, T, V], dim=1)
        sv = F.softplus(self.sv_head(z)) + 1e-4
        tp = F.softplus(self.tp_head(z)) + 1e-2
        co = sv / tp                                     # > 0 by construction
        y = (co - self.y_mean) / self.y_scale             # exact inverse standardisation
        return y, H, T, V, R


class CapacityMatchedOutputConstrainedPHPINN(OutputConstrainedPHPINN):
    """Model E2 — model E with its parameter count restored to model A's.

    Model E removes A's decoder block (17,537 parameters) and replaces it with two linear
    heads (272 parameters), leaving it 17,263 parameters smaller than A. Every accuracy
    comparison involving E was therefore confounded: a null result could mean 'the output
    constraint is free' or 'the missing capacity and the constraint happened to cancel'.

    E2 restores the deficit by giving each positive head a hidden layer of width
    `head_width`, so the extra capacity sits where the output is actually formed:

        sv = softplus(W2 SiLU(W1 z)),   tp = softplus(W2' SiLU(W1' z)),   CO = sv / tp

    With head_width = 64 the total is 56,986 against A's 56,983 -- a difference of three
    parameters in fifty-seven thousand (0.005%). The positivity construction is unchanged,
    so CO > 0 still holds for every input by the same algebra as in E.
    """

    def __init__(self, n_in, n_out, width=128, head_width=64):
        super().__init__(n_in, n_out, width)
        z_dim = self.enc.out_dim + STATE_DIM + 2
        self.sv_head = nn.Sequential(nn.Linear(z_dim, head_width), nn.SiLU(),
                                     nn.Linear(head_width, 1))
        self.tp_head = nn.Sequential(nn.Linear(z_dim, head_width), nn.SiLU(),
                                     nn.Linear(head_width, 1))


MODELS = {"A": PHPINN, "B": VanillaMLP, "C": NoStructurePINN,
          "D": SoftConstraintPINN, "E": OutputConstrainedPHPINN,
          "E2": CapacityMatchedOutputConstrainedPHPINN,
          "E3": TrueOutputConstrainedPHPINN}


def output_range_probe(net, Z, scY, lo=0.5, hi=20.0):
    """Two-sided range probe on the physical output.

    Counting only negative outputs is a one-sided test, and for E and E2 the learned
    offset makes it trivially zero. Cardiac output above 20 L/min is as impossible as
    cardiac output below zero; the audit found E reaching +1,266 L/min and E2 +622 L/min
    at 40 sigma while both scored 0 on the negative-only count. Both bounds are reported.
    """
    with torch.no_grad():
        y = net(Z)[0].numpy().ravel() * scY.scale_ + scY.mean_
    return {"n": int(len(y)),
            "n_negative": int((y < 0).sum()),
            "n_below_lo": int((y < lo).sum()),
            "n_above_hi": int((y > hi).sum()),
            "n_outside": int(((y < lo) | (y > hi)).sum()),
            "min": round(float(y.min()), 3), "max": round(float(y.max()), 3)}
