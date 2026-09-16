"""
Lumped Parameter Extraction from CFD Results
=============================================
Extracts 0D Windkessel parameters from 3D CFD simulation:
  - R (Resistance) = ΔP / Q
  - C (Compliance) = ΔV / ΔP  
  - L (Inertance) = ΔP / (dQ/dt)

These map directly to pH-PINN parameters for validation.
"""
import numpy as np
import json

def extract_windkessel(time, pressure, flow, volume=None):
    """Extract 0D Windkessel parameters from CFD time series.
    
    Args:
        time: Time array (s)
        pressure: Spatially-averaged pressure (Pa)
        flow: Volume flow rate at inlet/outlet (m³/s)
        volume: LV cavity volume over time (m³), optional
    
    Returns:
        dict with R, C, L parameters + pH-PINN mapping
    """
    dt = np.diff(time)
    
    # Resistance: R = mean(|ΔP|) / mean(|Q|)
    # Use peak systolic values for characteristic resistance
    Q_abs = np.abs(flow)
    P_abs = np.abs(pressure)
    R = np.mean(P_abs[Q_abs > 0.1*np.max(Q_abs)]) / np.mean(Q_abs[Q_abs > 0.1*np.max(Q_abs)])
    
    # Compliance: C = ΔV / ΔP (if volume available)
    if volume is not None:
        dV = np.max(volume) - np.min(volume)
        dP = np.max(pressure) - np.min(pressure)
        C = dV / dP if dP > 0 else 0
    else:
        # Estimate from flow integral
        dV = np.trapz(flow, time)
        dP = np.max(pressure) - np.min(pressure)
        C = abs(dV) / dP if dP > 0 else 0
    
    # Inertance: L = ΔP / (dQ/dt)
    dQdt = np.gradient(flow, time)
    # Use early systolic acceleration phase
    accel_phase = (dQdt > 0.1 * np.max(dQdt))
    if np.any(accel_phase):
        L = np.mean(P_abs[accel_phase]) / np.mean(np.abs(dQdt[accel_phase]))
    else:
        L = 0
    
    # Map to pH-PINN parameters
    # pH-PINN: dx/dt = [J(x) - R(x)] * dH/dx + g(x)*u
    # R matrix diagonal elements ↔ vascular resistance
    # H = T + V, where V includes compliance (elastic potential)
    
    results = {
        "windkessel_0D": {
            "R_Pa_s_m3": float(R),
            "R_mmHg_s_mL": float(R * 1e-6 / 133.322),
            "C_m3_Pa": float(C),
            "C_mL_mmHg": float(C * 1e6 * 133.322),
            "L_Pa_s2_m3": float(L),
        },
        "phpinn_mapping": {
            "R_matrix_diagonal": "SVR ∝ R_windkessel (vascular resistance)",
            "H_potential_V": "Compliance C ↔ elastic potential energy dV/dP",
            "J_matrix_offskew": "Inertance L ↔ kinetic energy coupling",
            "note": "Compare with pH-PINN v5 trained values from MIMIC-IV"
        }
    }
    return results

if __name__ == "__main__":
    # Demo with synthetic data
    T_cycle = 0.8
    t = np.linspace(0, T_cycle, 500)
    
    # Synthetic pressure waveform
    P = 80*133.322 + 40*133.322 * np.sin(2*np.pi*t/T_cycle)  # Pa
    
    # Synthetic flow
    Q = 70e-6/T_cycle * np.sin(2*np.pi*t/T_cycle)  # m³/s
    
    results = extract_windkessel(t, P, Q)
    print(json.dumps(results, indent=2))
    print("\n✓ Lumped parameter extraction ready for CFD post-processing")
