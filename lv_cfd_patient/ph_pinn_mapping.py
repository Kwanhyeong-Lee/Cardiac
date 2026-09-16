#!/usr/bin/env python3
"""
pH-PINN v5 Windkessel-to-Port-Hamiltonian Mapping
==================================================
Maps CFD-extracted Windkessel parameters to a port-Hamiltonian neural
network model for the cardiac digital twin.

Two complementary port-Hamiltonian formulations:

MODEL A — Full 3-Element Windkessel (downstream vasculature model)
    State: x = [q, phi]  (charge on C, flux through L)
    H(x) = q^2/(2C) + phi^2/(2L)
    Matrices calibrated from Windkessel R, C, L with optimised R_c split

MODEL B — Calibrated LV Impedance (direct CFD cavity dynamics)
    State: x = [phi]  (flow momentum)
    H(x) = phi^2/(2*L_eff)
    R_eff and L_eff fitted to match p_LV = L*dQ/dt + R*Q from CFD data
    This achieves R^2 > 0.91 against CFD pressure

Both models use the port-Hamiltonian form:
    dx/dt = [J(x) - R(x)] * dH/dx + g(x) * u

Physical conventions:
    - CFD kinematic pressure [m^2/s^2] -> multiply by rho for Pa
    - Mitral flow negative (inflow) -> take absolute value
    - All internal computation in SI (Pa, m^3, s)
    - Display in clinical units (mmHg, mL/s)

Author: Cardiac Digital Twin Project (Case 1009, MM-WHS CT)
"""

import json
import numpy as np
from scipy.integrate import solve_ivp
from scipy.interpolate import interp1d
from scipy.optimize import minimize_scalar, minimize
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

# ══════════════════════════════════════════════════════════════════════
# 0. PATHS & CONSTANTS
# ══════════════════════════════════════════════════════════════════════
BASE = Path(__file__).resolve().parent
FLOW_FILE = BASE / "postProcessing" / "flowRateMitral" / "0" / "surfaceFieldValue_0.dat"
PRESSURE_FILE = BASE / "postProcessing" / "probes1" / "0" / "p"
RESULTS_JSON = BASE / "cfd_windkessel_results.json"
OUTPUT_FIG = BASE / "ph_cfd_comparison.png"
OUTPUT_JSON = BASE / "ph_pinn_params.json"

RHO = 1060.0
PA_TO_MMHG = 1.0 / 133.322

# ══════════════════════════════════════════════════════════════════════
# 1. LOAD DATA
# ══════════════════════════════════════════════════════════════════════
print("=" * 72)
print("  pH-PINN v5 Windkessel-to-Port-Hamiltonian Mapping")
print("=" * 72)

with open(RESULTS_JSON) as f:
    wk = json.load(f)
R_total = wk["R_Pa_s_m3"]
C_val = wk["C_m3_Pa"]
L_val = wk["L_Pa_s2_m3"]

print(f"\n  Windkessel parameters (SI):")
print(f"    R = {R_total:.2f} Pa*s/m^3  ({wk['R_mmHg_s_mL']:.6f} mmHg*s/mL)")
print(f"    C = {C_val:.4e} m^3/Pa  ({wk['C_mL_mmHg']:.2f} mL/mmHg)")
print(f"    L = {L_val:.2f} Pa*s^2/m^3  ({wk['L_mmHg_s2_mL']:.6f} mmHg*s^2/mL)")

# Flow
flow_lines = []
with open(FLOW_FILE) as f:
    for ln in f:
        ln = ln.strip()
        if ln.startswith('#') or not ln:
            continue
        p = ln.split()
        flow_lines.append((float(p[0]), float(p[1])))
flow_arr = np.array(flow_lines)
t_flow_raw, Q_flow_raw = flow_arr[:, 0], np.abs(flow_arr[:, 1])

# Pressure (probe 0)
press_lines = []
with open(PRESSURE_FILE) as f:
    for ln in f:
        ln = ln.strip()
        if ln.startswith('#') or not ln:
            continue
        p = ln.split()
        press_lines.append([float(x) for x in p])
press_arr = np.array(press_lines)
t_press_raw = press_arr[:, 0]
p_cfd_raw = press_arr[:, 1] * RHO  # kinematic -> physical [Pa]

print(f"\n  Flow: {len(t_flow_raw)} pts, peak = {Q_flow_raw.max()*1e6:.1f} mL/s")
print(f"  Pressure: {len(t_press_raw)} pts, range = [{p_cfd_raw.min()*PA_TO_MMHG:.4f}, "
      f"{p_cfd_raw.max()*PA_TO_MMHG:.4f}] mmHg")

# ══════════════════════════════════════════════════════════════════════
# 2. CARDIAC CYCLE IDENTIFICATION
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'─'*72}")
print("  Cardiac cycle identification")
print(f"{'─'*72}")

FLOW_THRESH = 1e-6
episodes = []
in_fill = False
for i in range(len(Q_flow_raw)):
    if Q_flow_raw[i] > FLOW_THRESH and not in_fill:
        in_fill = True
        ep_s = i
    elif Q_flow_raw[i] <= FLOW_THRESH and in_fill:
        in_fill = False
        episodes.append((ep_s, i - 1))
if in_fill:
    episodes.append((ep_s, len(Q_flow_raw) - 1))

for idx, (s, e) in enumerate(episodes):
    dur = t_flow_raw[e] - t_flow_raw[s]
    pk = np.max(Q_flow_raw[s:e+1])
    vol = np.trapezoid(Q_flow_raw[s:e+1], t_flow_raw[s:e+1])
    print(f"    Episode {idx}: t=[{t_flow_raw[s]:.4f},{t_flow_raw[e]:.4f}] "
          f"dur={dur*1000:.0f}ms  peak={pk*1e6:.0f}mL/s  SV={vol*1e6:.1f}mL")

T_cardiac = (t_flow_raw[episodes[1][0]] - t_flow_raw[episodes[0][0]]
             if len(episodes) >= 2 else 0.8)
HR = 60.0 / T_cardiac
print(f"\n    Period = {T_cardiac:.3f} s  ({HR:.0f} bpm)")

# Use 2nd complete cycle
cyc_start = t_flow_raw[episodes[1][0]]
cyc_end = (t_flow_raw[episodes[2][0]] if len(episodes) >= 3
           else cyc_start + T_cardiac)
print(f"    Selected cycle: [{cyc_start:.4f}, {cyc_end:.4f}] s")

# ══════════════════════════════════════════════════════════════════════
# 3. PREPARE SIMULATION DATA
# ══════════════════════════════════════════════════════════════════════
dt_sim = 0.0005
t_sim = np.arange(cyc_start, cyc_end, dt_sim)

flow_interp = interp1d(t_flow_raw, Q_flow_raw, kind='linear',
                       bounds_error=False, fill_value=0.0)
press_interp = interp1d(t_press_raw, p_cfd_raw, kind='linear',
                        bounds_error=False, fill_value=0.0)

u_sim = flow_interp(t_sim)       # input flow [m^3/s]
p_cfd_sim = press_interp(t_sim)  # target pressure [Pa]
dQdt_sim = np.gradient(u_sim, dt_sim)  # flow acceleration [m^3/s^2]

u_func = interp1d(t_sim, u_sim, bounds_error=False, fill_value=0.0)
dQdt_func = interp1d(t_sim, dQdt_sim, bounds_error=False, fill_value=0.0)

N_pts = len(t_sim)
print(f"\n    Simulation: {N_pts} pts, dt = {dt_sim*1000:.1f} ms")

# ══════════════════════════════════════════════════════════════════════
# 4. MODEL B — CALIBRATED LV IMPEDANCE (LINEAR FIT)
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'─'*72}")
print("  MODEL B: Calibrated LV Impedance")
print(f"{'─'*72}")
print("    Fitting p_LV = L_eff * dQ/dt + R_eff * Q + p_base")

A_lin = np.column_stack([dQdt_sim, u_sim, np.ones(N_pts)])
coeffs_lin, _, _, _ = np.linalg.lstsq(A_lin, p_cfd_sim, rcond=None)
L_eff, R_eff, p_base = coeffs_lin

p_modelB = A_lin @ coeffs_lin
resB = p_cfd_sim - p_modelB
rmseB = np.sqrt(np.mean(resB**2))
ss_tot = np.sum((p_cfd_sim - np.mean(p_cfd_sim))**2)
r2B = 1 - np.sum(resB**2) / ss_tot
corrB = np.corrcoef(p_modelB, p_cfd_sim)[0, 1]
maeB = np.mean(np.abs(resB))
peakB_err = abs(p_modelB.max() - p_cfd_sim.max()) / abs(p_cfd_sim.max()) * 100

print(f"    L_eff  = {L_eff:.2f} Pa*s^2/m^3  (WK: {L_val:.2f})")
print(f"    R_eff  = {R_eff:.2f} Pa*s/m^3   (WK: {R_total:.2f})")
print(f"    p_base = {p_base:.4f} Pa = {p_base*PA_TO_MMHG:.4f} mmHg")
print(f"    RMSE   = {rmseB*PA_TO_MMHG:.6f} mmHg ({rmseB:.4f} Pa)")
print(f"    R^2    = {r2B:.6f}")
print(f"    r      = {corrB:.6f}")
print(f"    Peak err = {peakB_err:.2f}%")

# ══════════════════════════════════════════════════════════════════════
# 5. MODEL A — FULL 3-ELEMENT WINDKESSEL pH MODEL
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'─'*72}")
print("  MODEL A: Full 3-Element Windkessel (port-Hamiltonian)")
print(f"{'─'*72}")

J_A = np.array([[0.0, -1.0],
                [1.0,  0.0]])
g_A = np.array([[0.0], [1.0]])

def simulate_modelA(params, return_full=False):
    """Simulate full WK3 pH model with given R_c fraction."""
    R_c_frac = params[0]
    R_c = R_c_frac * R_total
    R_p = (1.0 - R_c_frac) * R_total

    R_A = np.array([[1.0/R_p, 0.0], [0.0, R_c]])

    p0 = press_interp(cyc_start)
    Q0 = flow_interp(cyc_start)
    q0 = C_val * p0
    phi0 = L_val * Q0

    def rhs(t, x):
        dHdx = np.array([x[0]/C_val, x[1]/L_val])
        return (J_A - R_A) @ dHdx + g_A.flatten() * u_func(t)

    sol = solve_ivp(rhs, (t_sim[0], t_sim[-1]), [q0, phi0],
                    method='RK45', t_eval=t_sim,
                    rtol=1e-9, atol=1e-13, max_step=dt_sim)

    if not sol.success:
        return 1e10 if not return_full else None

    q, phi = sol.y[0], sol.y[1]
    p_C = q / C_val
    Q_L = phi / L_val
    p_ao = p_C + R_c * Q_L

    if return_full:
        return {'q': q, 'phi': phi, 'p_C': p_C, 'p_ao': p_ao, 'Q_L': Q_L,
                'R_A': R_A, 'R_c': R_c, 'R_p': R_p, 'R_c_frac': R_c_frac}

    # Compare p_ao to CFD (Windkessel output = inlet pressure)
    return np.sqrt(np.mean((p_ao - p_cfd_sim)**2))

# Optimise R_c fraction
print("    Optimising R_c fraction...")
fracs = np.linspace(0.01, 0.99, 50)
rmses_scan = [simulate_modelA([f]) for f in fracs]
rmses_scan = np.array(rmses_scan)
best_idx = np.argmin(rmses_scan)
best_frac_coarse = fracs[best_idx]

# Fine optimisation
res_opt = minimize(lambda p: simulate_modelA(p), [best_frac_coarse],
                   method='Nelder-Mead',
                   options={'xatol': 1e-6, 'fatol': 1e-6, 'maxiter': 2000})
best_frac = np.clip(res_opt.x[0], 0.01, 0.99)

resA = simulate_modelA([best_frac], return_full=True)
R_c_A = resA['R_c']
R_p_A = resA['R_p']
R_mat_A = resA['R_A']

# Compare BOTH p_C and p_ao to CFD
for label, p_model in [('p_C (capacitor)', resA['p_C']),
                        ('p_ao (aortic)',   resA['p_ao'])]:
    res = p_model - p_cfd_sim
    rmse = np.sqrt(np.mean(res**2))
    r2 = 1 - np.sum(res**2) / ss_tot
    corr = np.corrcoef(p_model, p_cfd_sim)[0, 1]
    pk_err = abs(p_model.max() - p_cfd_sim.max()) / abs(p_cfd_sim.max()) * 100
    print(f"\n    {label}:")
    print(f"      R_c_frac = {best_frac:.4f} ({best_frac*100:.1f}%)")
    print(f"      RMSE = {rmse*PA_TO_MMHG:.6f} mmHg")
    print(f"      R^2  = {r2:.6f}")
    print(f"      r    = {corr:.6f}")
    print(f"      Peak err = {pk_err:.2f}%")

# Use p_ao for Model A metrics (inlet pressure = R_c*Q + p_C)
resA_pa = resA['p_ao'] - p_cfd_sim
rmseA = np.sqrt(np.mean(resA_pa**2))
r2A = 1 - np.sum(resA_pa**2) / ss_tot
corrA = np.corrcoef(resA['p_ao'], p_cfd_sim)[0, 1]
maeA = np.mean(np.abs(resA_pa))
peakA_err = abs(resA['p_ao'].max() - p_cfd_sim.max()) / abs(p_cfd_sim.max()) * 100

# Model A energy
H_A = resA['q']**2/(2*C_val) + resA['phi']**2/(2*L_val)
H_el = resA['q']**2/(2*C_val)
H_kin = resA['phi']**2/(2*L_val)

# Energy balance
P_diss_A = np.zeros(N_pts)
P_in_A = np.zeros(N_pts)
for i in range(N_pts):
    dHdx = np.array([resA['q'][i]/C_val, resA['phi'][i]/L_val])
    P_diss_A[i] = dHdx @ R_mat_A @ dHdx
    P_in_A[i] = dHdx @ g_A.flatten() * u_sim[i]

E_in_A = np.trapezoid(P_in_A, t_sim)
E_diss_A = np.trapezoid(P_diss_A, t_sim)
dH_A = H_A[-1] - H_A[0]

# ══════════════════════════════════════════════════════════════════════
# 5b. MODEL B in PORT-HAMILTONIAN FORM
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'─'*72}")
print("  MODEL B: Port-Hamiltonian formulation")
print(f"{'─'*72}")

# Model B is: p = L_eff * dQ/dt + R_eff * Q + p_base
# This is a 1-state pH model:
#   state: phi = L_eff * Q  (flux linkage / flow momentum)
#   H(phi) = phi^2 / (2*L_eff)
#   dH/dphi = phi/L_eff = Q
#   dphi/dt = -R_eff * Q + (p_in - p_base) = -R_eff * phi/L_eff + u_eff(t)
#   where u_eff(t) = p_in(t) - p_base (net driving pressure)
#
# Equivalently, u(t) is the FLOW input and the output is pressure:
#   phi represents flow momentum through the LV inlet
#   dphi/dt = -R_eff * (phi/L_eff) + u_eff(t)
#
# But for the pH-PINN, we want the FORWARD model:
#   Given inlet flow Q(t), predict cavity pressure p_LV(t)
#   p_LV(t) = L_eff * dQ/dt + R_eff * Q(t) + p_base
#
# pH form with state phi, dissipation R_eff:
J_B = np.array([[0.0]])  # no interconnection (1-state)
R_B = np.array([[R_eff]])  # dissipation
g_B = np.array([[1.0]])  # input port

# Simulate Model B as pH-ODE
phi0_B = L_eff * flow_interp(cyc_start)

def rhs_B(t, x):
    dHdx = np.array([x[0] / L_eff])
    # u_eff = external driving force that produces the observed flow
    # We use the pressure forcing term
    u_t = p_cfd_sim[min(int((t - cyc_start)/dt_sim), N_pts-1)] - p_base
    return (J_B - R_B) @ dHdx + g_B.flatten() * u_t

sol_B = solve_ivp(rhs_B, (t_sim[0], t_sim[-1]), [phi0_B],
                  method='RK45', t_eval=t_sim,
                  rtol=1e-9, atol=1e-13, max_step=dt_sim)

phi_B = sol_B.y[0]
Q_B = phi_B / L_eff  # predicted flow
H_B = phi_B**2 / (2 * L_eff)

# For Model B, the output equation gives the pressure:
# p_LV = L_eff * dQ/dt + R_eff * Q + p_base  (algebraic, not ODE output)
# This is the direct linear fit which already has R^2 = 0.914
# The pH-ODE version captures the dynamics in state-space form

print(f"    1-state pH model:")
print(f"      J_B = [[0]]   (no interconnection)")
print(f"      R_B = [[{R_eff:.2f}]]  (dissipation = R_eff)")
print(f"      g_B = [[1]]   (input port)")
print(f"      H_B = phi^2/(2*L_eff),  L_eff = {L_eff:.2f}")
print(f"      Output: p = L_eff*dQ/dt + R_eff*Q + p_base")

print(f"\n    pH-ODE flow prediction:")
print(f"      Q range: [{Q_B.min()*1e6:.2f}, {Q_B.max()*1e6:.2f}] mL/s")
print(f"      Q vs CFD flow r = {np.corrcoef(Q_B, u_sim)[0,1]:.4f}")

# ══════════════════════════════════════════════════════════════════════
# 6. COMPARISON SUMMARY
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'─'*72}")
print("  MODEL COMPARISON")
print(f"{'─'*72}")
print(f"  {'Metric':<20} {'Model A (WK3-pH)':<20} {'Model B (LV-imp)':<20}")
print(f"  {'─'*60}")
print(f"  {'States':<20} {'2 (q, phi)':<20} {'algebraic':<20}")
print(f"  {'R^2':<20} {r2A:<20.4f} {r2B:<20.6f}")
print(f"  {'RMSE [mmHg]':<20} {rmseA*PA_TO_MMHG:<20.6f} {rmseB*PA_TO_MMHG:<20.6f}")
print(f"  {'Pearson r':<20} {corrA:<20.4f} {corrB:<20.6f}")
print(f"  {'Peak err [%]':<20} {peakA_err:<20.2f} {peakB_err:<20.2f}")

nrmseA = rmseA / (p_cfd_sim.max() - p_cfd_sim.min())
nrmseB = rmseB / (p_cfd_sim.max() - p_cfd_sim.min())

# ══════════════════════════════════════════════════════════════════════
# 7. GENERATE COMPARISON FIGURE
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'─'*72}")
print("  Generating figure")
print(f"{'─'*72}")

fig = plt.figure(figsize=(20, 20))
gs = fig.add_gridspec(4, 2, hspace=0.38, wspace=0.28)
fig.suptitle('pH-PINN v5: Windkessel $\\to$ Port-Hamiltonian Mapping\n'
             'Case 1009 (MM-WHS CT, Patient-Specific LV)',
             fontsize=15, fontweight='bold', y=0.98)

t_ms = (t_sim - t_sim[0]) * 1000
t_flow_ms = (t_flow_raw - t_sim[0]) * 1000
mf = (t_flow_raw >= t_sim[0]) & (t_flow_raw <= t_sim[-1])
p_cfd_mmHg = p_cfd_sim * PA_TO_MMHG

# ── A: Input flow ──
ax = fig.add_subplot(gs[0, 0])
ax.plot(t_flow_ms[mf], Q_flow_raw[mf]*1e6, 'b-', lw=2.5, label='CFD mitral flow')
ax.fill_between(t_flow_ms[mf], 0, Q_flow_raw[mf]*1e6, alpha=0.12, color='blue')
ax.set_xlabel('Time [ms]'); ax.set_ylabel('Flow [mL/s]')
ax.set_title('(A) Input: Mitral Inflow $u(t)$')
ax.legend(); ax.grid(True, alpha=0.3)

# ── B: Model A pressure comparison ──
ax = fig.add_subplot(gs[0, 1])
ax.plot(t_ms, p_cfd_mmHg, 'k-', lw=2.5, label='CFD (probe 0)', zorder=3)
ax.plot(t_ms, resA['p_ao']*PA_TO_MMHG, 'r--', lw=2,
        label=f'Model A: $p_{{ao}} = q/C + R_c Q$', zorder=4)
ax.plot(t_ms, resA['p_C']*PA_TO_MMHG, 'b:', lw=1.5,
        label=f'Model A: $p_C = q/C$', zorder=2)
ax.set_xlabel('Time [ms]'); ax.set_ylabel('Pressure [mmHg]')
ax.set_title(f'(B) Model A: WK3 pH  ($R^2$={r2A:.4f})')
ax.legend(fontsize=9); ax.grid(True, alpha=0.3)

# ── C: Model B pressure comparison ──
ax = fig.add_subplot(gs[1, 0])
ax.plot(t_ms, p_cfd_mmHg, 'k-', lw=2.5, label='CFD (probe 0)', zorder=3)
ax.plot(t_ms, p_modelB*PA_TO_MMHG, 'r--', lw=2,
        label=f'Model B: $L \\dot{{Q}} + RQ + p_0$', zorder=4)
ax.set_xlabel('Time [ms]'); ax.set_ylabel('Pressure [mmHg]')
ax.set_title(f'(C) Model B: LV Impedance  ($R^2$={r2B:.4f})')
ax.legend(fontsize=9); ax.grid(True, alpha=0.3)

# ── D: Residuals comparison ──
ax = fig.add_subplot(gs[1, 1])
ax.plot(t_ms, resA_pa*PA_TO_MMHG, 'r-', lw=1.2, alpha=0.8, label=f'Model A (RMSE={rmseA*PA_TO_MMHG:.4f})')
ax.plot(t_ms, resB*PA_TO_MMHG, 'b-', lw=1.2, alpha=0.8, label=f'Model B (RMSE={rmseB*PA_TO_MMHG:.4f})')
ax.axhline(0, color='k', lw=0.5)
ax.set_xlabel('Time [ms]'); ax.set_ylabel('Residual [mmHg]')
ax.set_title('(D) Pressure Residuals')
ax.legend(fontsize=9); ax.grid(True, alpha=0.3)

# ── E: Hamiltonian energy (Model A) ──
ax = fig.add_subplot(gs[2, 0])
ax.plot(t_ms, H_A*1e6, 'k-', lw=2, label='$H_{total}$')
ax.plot(t_ms, H_el*1e6, 'r--', lw=1.5, label=r'$H_{elastic}=q^2/2C$')
ax.plot(t_ms, H_kin*1e6, 'b:', lw=1.5, label=r'$H_{kinetic}=\phi^2/2L$')
ax.set_xlabel('Time [ms]'); ax.set_ylabel(r'Energy [$\mu$J]')
ax.set_title('(E) Model A: Hamiltonian Energy')
ax.legend(); ax.grid(True, alpha=0.3)

# ── F: Power balance (Model A) ──
ax = fig.add_subplot(gs[2, 1])
ax.plot(t_ms, P_in_A*1e3, 'g-', lw=2, label='$P_{in}$')
ax.plot(t_ms, -P_diss_A*1e3, 'r-', lw=2, label='$-P_{diss}$')
dHdt_A = np.gradient(H_A, t_sim)
ax.plot(t_ms, dHdt_A*1e3, 'b--', lw=1.5, label='$dH/dt$ (num)')
ax.axhline(0, color='k', lw=0.5)
ax.set_xlabel('Time [ms]'); ax.set_ylabel('Power [mW]')
ax.set_title('(F) Model A: Power Balance')
ax.legend(fontsize=9); ax.grid(True, alpha=0.3)

# ── G: Phase portrait (Model A) ──
ax = fig.add_subplot(gs[3, 0])
sc = ax.scatter(resA['q']*1e6, resA['phi']*1e3, c=t_ms, cmap='viridis', s=8, zorder=3)
ax.plot(resA['q'][0]*1e6, resA['phi'][0]*1e3, 'go', ms=12, label='Start', zorder=5)
ax.plot(resA['q'][-1]*1e6, resA['phi'][-1]*1e3, 'rs', ms=12, label='End', zorder=5)
plt.colorbar(sc, ax=ax, label='Time [ms]')
ax.set_xlabel(r'$q$ (charge) [$\mu$L]')
ax.set_ylabel(r'$\phi$ (flux) [mPa$\cdot$s]')
ax.set_title('(G) Model A: State-Space Trajectory')
ax.legend(); ax.grid(True, alpha=0.3)

# ── H: Summary panel ──
ax = fig.add_subplot(gs[3, 1])
ax.axis('off')
txt = (
    "PORT-HAMILTONIAN STRUCTURE\n"
    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
    "MODEL A: 3-Element Windkessel\n"
    r"  $\dot{x}=[J-R]\partial H/\partial x + gu$" + "\n"
    f"  x = [q, phi]^T  (dim=2)\n"
    f"  J = [[0,-1],[1,0]]\n"
    f"  R = diag(1/Rp, Rc)\n"
    f"    Rc = {R_c_A:.0f} ({best_frac*100:.1f}%)\n"
    f"    Rp = {R_p_A:.0f} ({(1-best_frac)*100:.1f}%)\n"
    f"  H = q^2/(2C) + phi^2/(2L)\n"
    f"  R^2 = {r2A:.4f}, RMSE = {rmseA*PA_TO_MMHG:.4f} mmHg\n\n"
    "MODEL B: LV Impedance (calibrated)\n"
    r"  $p = L_{eff}\dot{Q} + R_{eff}Q + p_0$" + "\n"
    f"  L_eff = {L_eff:.0f} Pa*s^2/m^3\n"
    f"  R_eff = {R_eff:.0f} Pa*s/m^3\n"
    f"  p_base = {p_base*PA_TO_MMHG:.4f} mmHg\n"
    f"  R^2 = {r2B:.4f}, RMSE = {rmseB*PA_TO_MMHG:.4f} mmHg\n\n"
    "━━━ CFD Source ━━━\n"
    f"  Case 1009 (MM-WHS CT)\n"
    f"  HR = {HR:.0f} bpm, SV = {wk['SV_mL']:.1f} mL\n"
    f"  CO = {wk['CO_Lmin']:.2f} L/min"
)
ax.text(0.02, 0.98, txt, transform=ax.transAxes, fontsize=9.5,
        va='top', fontfamily='monospace',
        bbox=dict(boxstyle='round,pad=0.5', fc='lightyellow', alpha=0.9))

plt.savefig(OUTPUT_FIG, dpi=200, bbox_inches='tight')
print(f"    Saved: {OUTPUT_FIG}")

# ══════════════════════════════════════════════════════════════════════
# 8. BUILD & SAVE pH-PINN PARAMETER DICTIONARY
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'─'*72}")
print("  Building pH-PINN parameter dictionary")
print(f"{'─'*72}")

pH_params = {
    'model_A': {
        'description': '3-element Windkessel in port-Hamiltonian form',
        'J': J_A.tolist(),
        'R': R_mat_A.tolist(),
        'g': g_A.tolist(),
        'H_coeffs': {
            'C': C_val,
            'L': L_val,
            'C_mL_mmHg': wk['C_mL_mmHg'],
            'L_mmHg_s2_mL': wk['L_mmHg_s2_mL'],
        },
        'resistance': {
            'R_total': R_total,
            'R_c': float(R_c_A),
            'R_p': float(R_p_A),
            'R_c_fraction': float(best_frac),
        },
        'state_dim': 2,
        'input_dim': 1,
        'output_dim': 1,
        'states': {
            'x0': {'name': 'q', 'unit': 'm^3',
                    'description': 'charge (stored volume on C)'},
            'x1': {'name': 'phi', 'unit': 'Pa*s',
                    'description': 'flux linkage (flow momentum through L)'},
        },
        'output_eq': 'p_ao = q/C + R_c * phi/L',
        'hamiltonian_form': 'H = q^2/(2C) + phi^2/(2L)',
        'validation': {
            'rmse_Pa': float(rmseA),
            'rmse_mmHg': float(rmseA * PA_TO_MMHG),
            'mae_mmHg': float(maeA * PA_TO_MMHG),
            'nrmse': float(nrmseA),
            'r_squared': float(r2A),
            'pearson_r': float(corrA),
            'peak_error_pct': float(peakA_err),
        },
        'energy': {
            'E_input_J': float(E_in_A),
            'E_dissipated_J': float(E_diss_A),
            'dH_J': float(dH_A),
            'H_range_J': [float(H_A.min()), float(H_A.max())],
        },
    },
    'model_B': {
        'description': 'Calibrated LV impedance model (algebraic, highest accuracy)',
        'form': 'p_LV = L_eff * dQ/dt + R_eff * Q + p_base',
        'L_eff': float(L_eff),
        'R_eff': float(R_eff),
        'p_base': float(p_base),
        'pH_form': {
            'J': [[0.0]],
            'R': [[float(R_eff)]],
            'g': [[1.0]],
            'H_coeff_L_eff': float(L_eff),
            'state_dim': 1,
            'state': {'name': 'phi', 'unit': 'Pa*s',
                      'description': 'flow momentum = L_eff * Q'},
        },
        'validation': {
            'rmse_Pa': float(rmseB),
            'rmse_mmHg': float(rmseB * PA_TO_MMHG),
            'mae_mmHg': float(maeB * PA_TO_MMHG),
            'nrmse': float(nrmseB),
            'r_squared': float(r2B),
            'pearson_r': float(corrB),
            'peak_error_pct': float(peakB_err),
        },
    },
    'recommended_model': 'model_B',
    'recommendation_reason': (
        'Model B achieves R^2=0.914 vs Model A R^2={:.3f}. '
        'The LV cavity pressure is dominated by inertial (L*dQ/dt) and '
        'resistive (R*Q) effects of the inlet flow, which Model B '
        'captures directly. Model A provides the full Windkessel structure '
        'needed for downstream vasculature coupling.'
    ).format(r2A),

    # Windkessel source parameters
    'windkessel_source': {
        'R_Pa_s_m3': R_total,
        'C_m3_Pa': C_val,
        'L_Pa_s2_m3': L_val,
        'R_mmHg_s_mL': wk['R_mmHg_s_mL'],
        'C_mL_mmHg': wk['C_mL_mmHg'],
        'L_mmHg_s2_mL': wk['L_mmHg_s2_mL'],
    },

    # Common metadata
    'rho': RHO,
    'units': 'SI (Pa, m^3, s)',
    'source': {
        'case': 'Case 1009 (MM-WHS CT)',
        'method': 'OpenFOAM LV CFD -> Windkessel extraction -> pH mapping',
        'cardiac_cycle': {
            'period_s': float(T_cardiac),
            'HR_bpm': float(HR),
            'SV_mL': wk['SV_mL'],
            'CO_L_min': wk['CO_Lmin'],
        },
    },

    # Neural network training configuration
    'nn_training': {
        'model_A_scaling': {
            'q_scale': float(np.max(np.abs(resA['q']))),
            'phi_scale': float(np.max(np.abs(resA['phi']))),
            'u_scale': float(np.max(u_sim)),
            'p_scale': float(np.max(np.abs(resA['p_ao']))),
            'H_scale': float(H_A.max()),
        },
        'model_B_scaling': {
            'Q_scale': float(np.max(u_sim)),
            'dQdt_scale': float(np.max(np.abs(dQdt_sim))),
            'p_scale': float(np.max(np.abs(p_cfd_sim))),
        },
        'time_scale': float(T_cardiac),
        'suggested_loss_weights': {
            'data_loss': 1.0,
            'hamiltonian_loss': 0.1,
            'skew_symmetry_loss': 0.01,
            'dissipation_psd_loss': 0.01,
            'energy_conservation_loss': 0.05,
        },
    },
}

with open(OUTPUT_JSON, 'w') as f:
    json.dump(pH_params, f, indent=2)
print(f"    Saved: {OUTPUT_JSON}")

# ══════════════════════════════════════════════════════════════════════
# FINAL SUMMARY
# ══════════════════════════════════════════════════════════════════════
print(f"\n{'='*72}")
print("  FINAL SUMMARY")
print(f"{'='*72}")
print(f"\n  MODEL A (3-element WK3 port-Hamiltonian):")
print(f"    dx/dt = [J - R] dH/dx + g u")
print(f"    States: x = [q, phi]  (dim=2)")
print(f"    H = q^2/(2C) + phi^2/(2L)")
print(f"    R_c = {R_c_A:.0f} ({best_frac*100:.1f}%),  R_p = {R_p_A:.0f}")
print(f"    R^2 = {r2A:.4f},  RMSE = {rmseA*PA_TO_MMHG:.4f} mmHg,  r = {corrA:.4f}")

print(f"\n  MODEL B (calibrated LV impedance):")
print(f"    p_LV = L_eff * dQ/dt + R_eff * Q + p_base")
print(f"    L_eff = {L_eff:.2f},  R_eff = {R_eff:.2f},  p_base = {p_base:.4f} Pa")
print(f"    R^2 = {r2B:.4f},  RMSE = {rmseB*PA_TO_MMHG:.4f} mmHg,  r = {corrB:.4f}")

print(f"\n  RECOMMENDED: Model B for LV pressure prediction (R^2={r2B:.4f})")
print(f"               Model A for vascular coupling & energy analysis")

print(f"\n  Output files:")
print(f"    {OUTPUT_FIG}")
print(f"    {OUTPUT_JSON}")
print(f"    {Path(__file__).resolve()}")
print(f"\n  Ready for pH-PINN v5 neural network training.")
print(f"{'='*72}")
