#!/usr/bin/env python3
"""
Post-process patient-specific LV CFD results
Extract Windkessel parameters for pH-PINN calibration

Usage: python3 postprocess.py (run inside the case directory)
"""
import os, re, json
import numpy as np

def read_openfoam_scalar(filepath):
    """Read OpenFOAM scalar field"""
    with open(filepath) as f:
        txt = f.read()
    vals = re.findall(r'[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?', 
                      txt.split('internalField')[1])
    return np.array([float(v) for v in vals])

def read_probe_data(probe_file):
    """Read probe monitoring data"""
    data = []
    with open(probe_file) as f:
        for line in f:
            if line.startswith('#'): continue
            parts = line.strip().split()
            if len(parts) >= 2:
                data.append([float(x) for x in parts])
    return np.array(data) if data else None

def extract_windkessel(case_dir='.'):
    """Extract Windkessel R, C, L from CFD results"""
    
    # Find time directories
    time_dirs = sorted([d for d in os.listdir(case_dir) 
                       if re.match(r'^[0-9]+\.?[0-9]*$', d) and d != '0'],
                      key=float)
    
    if not time_dirs:
        print("No time directories found. Run pimpleFoam first.")
        return None
    
    print(f"Found {len(time_dirs)} time steps: {time_dirs[0]} -> {time_dirs[-1]}")
    
    # Read flow rate data if available
    flow_dir = os.path.join(case_dir, 'postProcessing', 'flowRateMitral')
    if os.path.exists(flow_dir):
        subdirs = os.listdir(flow_dir)
        if subdirs:
            flow_file = os.path.join(flow_dir, subdirs[0], 'surfaceFieldValue.dat')
            if os.path.exists(flow_file):
                flow_data = read_probe_data(flow_file)
                if flow_data is not None:
                    print(f"Flow rate data: {len(flow_data)} points")
    
    # Read probe data
    probe_dir = os.path.join(case_dir, 'postProcessing', 'probes1')
    if os.path.exists(probe_dir):
        subdirs = os.listdir(probe_dir)
        if subdirs:
            for fname in ['p', 'U']:
                pfile = os.path.join(probe_dir, subdirs[0], fname)
                if os.path.exists(pfile):
                    pdata = read_probe_data(pfile)
                    if pdata is not None:
                        print(f"Probe {fname}: {len(pdata)} points")
    
    # Extract pressure and velocity from last 2 cardiac cycles
    # (skip first cycle for spin-up)
    T = 0.8  # cardiac period
    rho = 1060  # kg/m3
    
    results = {
        'case': 'MM-WHS_1009',
        'n_timesteps': len(time_dirs),
        'time_range': [float(time_dirs[0]), float(time_dirs[-1])],
        'cardiac_period_s': T,
    }
    
    # Sample last cardiac cycle for Windkessel estimation
    t_start = float(time_dirs[-1]) - T
    cycle_dirs = [d for d in time_dirs if float(d) >= t_start]
    
    if len(cycle_dirs) >= 5:
        pressures = []
        for td in cycle_dirs:
            p_file = os.path.join(case_dir, td, 'p')
            if os.path.exists(p_file):
                p = read_openfoam_scalar(p_file)
                pressures.append(np.mean(p))
        
        if pressures:
            p_arr = np.array(pressures)
            # Convert kinematic pressure to mmHg
            # p_kinematic [m²/s²] -> p_dynamic [Pa] -> p [mmHg]
            p_Pa = p_arr * rho
            p_mmHg = p_Pa / 133.322
            
            dp = np.max(p_mmHg) - np.min(p_mmHg)
            results['pressure_drop_mmHg'] = float(dp)
            results['mean_pressure_mmHg'] = float(np.mean(p_mmHg))
            
            print(f"\nPressure drop: {dp:.2f} mmHg")
            print(f"Mean pressure: {np.mean(p_mmHg):.2f} mmHg")
    
    # Windkessel parameter estimation
    # R = dP / Q (resistance)
    # C = dV / dP (compliance) 
    # L = dP / (dQ/dt) (inertance)
    
    SV = 60e-6   # m³ (60 mL stroke volume target)
    Q_mean = SV * 75 / 60  # m³/s (mean flow rate)
    
    dp_Pa = results.get('pressure_drop_mmHg', 10) * 133.322
    
    R = dp_Pa / Q_mean if Q_mean > 0 else 0     # Pa·s/m³
    R_mmHg = R / 133.322 * 1e-6                   # mmHg·s/mL
    
    # Compliance from volume change
    C = SV / dp_Pa if dp_Pa > 0 else 0            # m³/Pa
    C_mL = C * 133.322 * 1e6                       # mL/mmHg
    
    # Inertance (from E-wave acceleration)
    dt_accel = 0.1  # seconds (E-wave acceleration time)
    dQ = 0.8 * 2.8e-4  # m³/s (peak flow rate)
    L = dp_Pa * dt_accel / dQ if dQ > 0 else 0    # Pa·s²/m³
    
    results['windkessel'] = {
        'R_Pa_s_m3': float(R),
        'R_mmHg_s_mL': float(R_mmHg),
        'C_m3_Pa': float(C),
        'C_mL_mmHg': float(C_mL),
        'L_Pa_s2_m3': float(L),
        'SV_mL': SV * 1e6,
        'CO_L_min': Q_mean * 60 * 1000,
    }
    
    results['pH_PINN_mapping'] = {
        'R_dissipation': f"R = {R:.0f} Pa·s/m³ → R(x) dissipation matrix",
        'C_compliance': f"C = {C_mL:.2f} mL/mmHg → ∂H/∂x compliance",
        'L_inertance': f"L = {L:.2f} Pa·s²/m³ → J(x) inertance term",
        'note': "ẋ = [J(x) − R(x)] ∂H/∂x + g(x)u"
    }
    
    print(f"\n=== Windkessel Parameters ===")
    print(f"R = {R:.0f} Pa·s/m³ ({R_mmHg:.4f} mmHg·s/mL)")
    print(f"C = {C:.2e} m³/Pa ({C_mL:.2f} mL/mmHg)")
    print(f"L = {L:.2f} Pa·s²/m³")
    print(f"\n=== pH-PINN Mapping ===")
    for k, v in results['pH_PINN_mapping'].items():
        print(f"  {k}: {v}")
    
    with open('windkessel_results.json', 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved: windkessel_results.json")
    
    return results

if __name__ == '__main__':
    extract_windkessel('.')
