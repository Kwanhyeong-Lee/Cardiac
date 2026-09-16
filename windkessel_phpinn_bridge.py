#!/usr/bin/env python3
"""
Windkessel -> pH-PINN Bridge (v2 with dissipation)
====================================================
Port-Hamiltonian formulation WITH learnable R(x) != 0

dx/dt = [J(x) - R(x)] dH/dx + g(x)u
  J(x) = skew-symmetric (energy-conserving interconnection)
  R(x) = r_diss * I, r_diss > 0 (viscous dissipation)
  g(x)u = external input (preload/afterload)

r_diss is estimated from Windkessel characteristic impedance Zc (= R1).
Physical basis: Zc represents wave reflection and viscous loss at the
aortic root — exactly the dissipation pH frameworks should capture.

References:
- Westerhof et al. (2009) Med Biol Eng Comput — Windkessel
- Rashad et al. (2021) — port-Hamiltonian blood flow
- Suga & Sagawa (1974) — PVA framework
"""

import numpy as np
import json
import os
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class WindkesselParams:
    R1: float   # Proximal resistance [mmHg*s/mL]
    R2: float   # Distal resistance [mmHg*s/mL]
    C: float    # Compliance [mL/mmHg]
    L: float = 0.0

    @property
    def R_total(self): return self.R1 + self.R2
    @property
    def tau(self): return self.R2 * self.C
    @property
    def Zc(self): return self.R1


@dataclass
class PHPINNParams:
    """pH-PINN parameters with dissipation."""
    Emax: float       # End-systolic elastance [mmHg/mL]
    Vd: float         # Dead volume [mL]
    Ea: float         # Arterial elastance [mmHg/mL]
    tau_sys: float    # Systolic time constant [s]
    tau_dia: float    # Diastolic time constant [s]
    HR: float         # Heart rate [bpm]
    r_diss: float = 0.0  # Scalar dissipation [mmHg*s/mL]

    @property
    def T_cycle(self): return 60.0 / self.HR
    @property
    def coupling_ratio(self):
        return self.Ea / self.Emax if self.Emax > 0 else float('inf')


@dataclass
class CFDDerivedData:
    time: np.ndarray
    flow_rate: np.ndarray
    pressure_aortic: np.ndarray
    pressure_lv: np.ndarray
    volume_lv: np.ndarray

    @property
    def SV(self): return float(np.max(self.volume_lv) - np.min(self.volume_lv))
    @property
    def HR(self):
        T = self.time[-1] - self.time[0]
        return 60.0 / T if T > 0 else 75.0
    @property
    def CO(self): return self.SV * self.HR / 1000.0
    @property
    def mean_aortic_pressure(self): return float(np.mean(self.pressure_aortic))
    @property
    def mean_flow(self): return float(np.mean(self.flow_rate))


# ============================================================
# WINDKESSEL ESTIMATION
# ============================================================

def estimate_windkessel_from_cfd(cfd):
    mean_P = cfd.mean_aortic_pressure
    mean_Q = cfd.mean_flow
    if abs(mean_Q) < 1e-10:
        raise ValueError("Mean flow rate is zero")
    R_total = mean_P / mean_Q
    P_sys = np.max(cfd.pressure_aortic)
    P_dia = np.min(cfd.pressure_aortic)
    pp = P_sys - P_dia
    if pp < 1e-10:
        raise ValueError("Pulse pressure is zero")
    C = cfd.SV / pp
    R1 = 0.06 * R_total
    R2 = R_total - R1
    return WindkesselParams(R1=R1, R2=R2, C=C)


# ============================================================
# DISSIPATION ESTIMATION
# ============================================================

def estimate_dissipation(wk, HR=75.0):
    """
    Estimate r_diss from Windkessel Zc (= R1).

    r_diss = R1 * (T_sys / T_cycle)
    Scales Zc by the ejection duty cycle.

    Typical: 0.01-0.05 (normal), 0.05-0.15 (heart failure)
    """
    T_cycle = 60.0 / HR
    T_sys = max(-0.0017 * HR + 0.413, 0.2)
    r_diss = wk.R1 * (T_sys / T_cycle)
    return max(min(r_diss, 0.20), 0.005)


# ============================================================
# WINDKESSEL -> pH-PINN MAPPING
# ============================================================

def windkessel_to_phpinn(wk, HR=75.0, Emax=2.5, Vd=10.0):
    T_cycle = 60.0 / HR
    Ea = wk.R_total / T_cycle
    tau_dia = wk.tau
    T_sys = max(-0.0017 * HR + 0.413, 0.2)
    tau_sys = T_sys / 3.0
    r_diss = estimate_dissipation(wk, HR)
    return PHPINNParams(Emax=Emax, Vd=Vd, Ea=Ea,
                        tau_sys=tau_sys, tau_dia=tau_dia,
                        HR=HR, r_diss=r_diss)


# ============================================================
# PV LOOP METRICS (with dissipation)
# ============================================================

def compute_pv_loop_metrics(phpinn, SV, EDV):
    """
    PV loop metrics with port-Hamiltonian energy balance.

    Energy balance: dH/dt = -(dH/dx)^T R(x) (dH/dx) + y^T u
    E_dissipated = r_diss * SV * mean_P_sys (per beat)
    """
    ESV = EDV - SV
    Ves = ESV
    Pes = phpinn.Emax * (Ves - phpinn.Vd)

    # Stroke work (Sunagawa analytical)
    SW = 0.5 * phpinn.Ea * SV**2

    # Potential energy
    PE = 0.5 * phpinn.Emax * (Ves - phpinn.Vd)**2

    # Dissipation energy
    r_diss = phpinn.r_diss
    T_sys = phpinn.tau_sys * 3.0
    mean_P_sys = (Pes + 0.5 * phpinn.Ea * SV) / 2.0
    E_diss = r_diss * SV * mean_P_sys

    PVA = SW + PE
    SW_net = SW - E_diss

    eff_gross = SW / PVA if PVA > 0 else 0
    eff_net = SW_net / PVA if PVA > 0 else 0
    energy_residual = -E_diss

    MVO2 = 0.0001 * PVA + 0.02 + 0.00005 * E_diss

    return {
        'SW_mmHg_mL': float(SW),
        'SW_joules': float(SW * 0.000133322),
        'PE_mmHg_mL': float(PE),
        'PVA_mmHg_mL': float(PVA),
        'PVA_joules': float(PVA * 0.000133322),
        'mechanical_efficiency_gross': float(eff_gross),
        'mechanical_efficiency_net': float(eff_net),
        'coupling_ratio_Ea_Emax': float(phpinn.coupling_ratio),
        'Pes_mmHg': float(Pes),
        'ESV_mL': float(ESV),
        'EDV_mL': float(EDV),
        'SV_mL': float(SV),
        'EF_pct': float(SV / EDV * 100) if EDV > 0 else 0,
        'MVO2_estimate': float(MVO2),
        'Ea_mmHg_per_mL': float(phpinn.Ea),
        'Emax_mmHg_per_mL': float(phpinn.Emax),
        'r_diss_mmHg_s_per_mL': float(r_diss),
        'E_dissipated_mmHg_mL': float(E_diss),
        'E_dissipated_joules': float(E_diss * 0.000133322),
        'energy_balance_residual': float(energy_residual),
        'SW_net_mmHg_mL': float(SW_net),
        'tau_dia_s': float(phpinn.tau_dia),
        'tau_sys_s': float(phpinn.tau_sys),
        'HR_bpm': float(phpinn.HR),
    }


# ============================================================
# PIPELINE
# ============================================================

def run_bridge_pipeline(cfd_data_path=None, use_synthetic=True):
    if use_synthetic or cfd_data_path is None:
        print("Using synthetic hemodynamic data...")
        T = 0.8
        t = np.linspace(0, T, 200)
        dt = t[1] - t[0]
        systole_mask = t < 0.35
        Q = np.where(systole_mask, 350 * np.sin(np.pi * t / 0.35)**2, 0.0)
        Q = Q * (70.0 / np.trapz(Q, t))
        P_ao = np.where(systole_mask,
            80 + 40 * np.sin(np.pi * t / 0.35),
            80 + 40 * np.exp(-(t - 0.35) / 0.4))
        P_lv = np.where(t < 0.4,
            10 + 110 * np.sin(np.pi * t / 0.4)**2,
            10 + 5 * np.exp(-(t - 0.4) / 0.15))
        V_lv = np.zeros_like(t)
        V_lv[0] = 120.0
        for i in range(1, len(t)):
            V_lv[i] = V_lv[i-1] - Q[i] * dt
        V_lv = np.clip(V_lv, 45, 130)
        cfd = CFDDerivedData(time=t, flow_rate=Q, pressure_aortic=P_ao,
                             pressure_lv=P_lv, volume_lv=V_lv)
    else:
        cfd = load_openfoam_data(cfd_data_path)

    sep = '=' * 60
    print(f"\n{sep}")
    print(f" Windkessel-pH-PINN Bridge Pipeline (with dissipation)")
    print(f"{sep}")

    print(f"\n--- CFD Hemodynamics ---")
    print(f"  HR: {cfd.HR:.0f} bpm")
    print(f"  SV: {cfd.SV:.1f} mL")
    print(f"  CO: {cfd.CO:.2f} L/min")
    print(f"  Mean AoP: {cfd.mean_aortic_pressure:.1f} mmHg")

    wk = estimate_windkessel_from_cfd(cfd)
    print(f"\n--- Windkessel Parameters ---")
    print(f"  R1 (Zc): {wk.R1:.4f}")
    print(f"  R2:      {wk.R2:.4f}")
    print(f"  C:       {wk.C:.2f}")
    print(f"  tau:     {wk.tau:.3f} s")

    phpinn = windkessel_to_phpinn(wk, HR=cfd.HR, Emax=2.5, Vd=10.0)
    print(f"\n--- pH-PINN Parameters ---")
    print(f"  Emax:    {phpinn.Emax:.2f} mmHg/mL")
    print(f"  Ea:      {phpinn.Ea:.4f} mmHg/mL")
    print(f"  r_diss:  {phpinn.r_diss:.4f} mmHg*s/mL")
    print(f"  Ea/Emax: {phpinn.coupling_ratio:.3f}")

    metrics = compute_pv_loop_metrics(phpinn, SV=cfd.SV, EDV=np.max(cfd.volume_lv))
    print(f"\n--- PV Loop Metrics (port-Hamiltonian) ---")
    print(f"  SW:       {metrics['SW_mmHg_mL']:.1f} mmHg*mL ({metrics['SW_joules']:.4f} J)")
    print(f"  PE:       {metrics['PE_mmHg_mL']:.1f} mmHg*mL")
    print(f"  PVA:      {metrics['PVA_mmHg_mL']:.1f} mmHg*mL")
    print(f"  E_diss:   {metrics['E_dissipated_mmHg_mL']:.1f} mmHg*mL")
    print(f"  SW_net:   {metrics['SW_net_mmHg_mL']:.1f} mmHg*mL")
    print(f"  Eff(gross): {metrics['mechanical_efficiency_gross']*100:.1f}%")
    print(f"  Eff(net):   {metrics['mechanical_efficiency_net']*100:.1f}%")
    print(f"  EF:       {metrics['EF_pct']:.1f}%")

    results = {
        'cfd_summary': {
            'HR_bpm': float(cfd.HR),
            'SV_mL': float(cfd.SV),
            'CO_Lmin': float(cfd.CO),
            'mean_AoP_mmHg': float(cfd.mean_aortic_pressure),
        },
        'windkessel': asdict(wk),
        'phpinn': asdict(phpinn),
        'pv_metrics': metrics,
    }
    return results


def load_openfoam_data(base_path):
    import glob
    flow_files = glob.glob(os.path.join(base_path, "postProcessing/flowRate/*/surfaceFieldValue.dat"))
    if not flow_files:
        flow_files = glob.glob(os.path.join(base_path, "postProcessing/flowRate_*/*/surfaceFieldValue.dat"))
    if flow_files:
        data = np.loadtxt(flow_files[0], comments='#')
        time, Q = data[:, 0], data[:, 1] * 1e6
    else:
        raise FileNotFoundError(f"No flow rate data in {base_path}")
    probe_files = glob.glob(os.path.join(base_path, "postProcessing/probes/*/p"))
    if probe_files:
        pdata = np.loadtxt(probe_files[0], comments='#')
        P_ao = pdata[:, 1] / 133.322
        P_lv = pdata[:, 2] / 133.322 if pdata.shape[1] > 2 else P_ao
    else:
        raise FileNotFoundError(f"No pressure data in {base_path}")
    vol_files = glob.glob(os.path.join(base_path, "postProcessing/volFieldValue/*/volFieldValue.dat"))
    if vol_files:
        vdata = np.loadtxt(vol_files[0], comments='#')
        V_lv = vdata[:, 1] * 1e6
    else:
        V_lv = 120 - np.cumsum(Q) * np.mean(np.diff(time)) * 0.001
    n = min(len(time), len(Q), len(P_ao))
    return CFDDerivedData(time=time[:n], flow_rate=Q[:n],
                          pressure_aortic=P_ao[:n], pressure_lv=P_lv[:n],
                          volume_lv=V_lv[:n])


if __name__ == "__main__":
    import sys
    cfd_path = sys.argv[1] if len(sys.argv) > 1 else None
    results = run_bridge_pipeline(cfd_path, use_synthetic=cfd_path is None)

    output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                               "windkessel_phpinn_results.json")

    def convert(obj):
        if isinstance(obj, (np.floating, np.integer)):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return obj

    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2, default=convert)
    print(f"\nResults saved: {output_path}")
