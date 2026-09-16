"""
Patient-Specific LV CFD Post-Processing Analysis
=================================================
pimpleFoam 완료 후 실행:
  cd lv_cfd_anatomical
  bash postprocess.sh          # OpenFOAM 후처리
  python3 postprocess_analysis.py  # 분석 + 시각화

출력:
  - Pressure/velocity time series (probe data)
  - Mitral/aortic flow rate curves
  - WSS statistics
  - Windkessel parameter extraction (R, C, L)
  - PV loop reconstruction
"""
import numpy as np
import os, json, glob, re

# ============================================================
# 1. Load probe data (pressure & velocity at 4 LV locations)
# ============================================================
def load_probes(case_dir='.'):
    probe_dir = os.path.join(case_dir, 'postProcessing', 'probes', '0')
    results = {}
    
    for field in ['U', 'p']:
        fpath = os.path.join(probe_dir, field)
        if not os.path.exists(fpath):
            print(f"  Warning: {fpath} not found")
            continue
        
        times, values = [], []
        with open(fpath) as f:
            for line in f:
                if line.strip().startswith('#') or not line.strip():
                    continue
                parts = line.strip().split()
                t = float(parts[0])
                times.append(t)
                
                if field == 'U':
                    # Vector field: (Ux Uy Uz) per probe
                    raw = line.split('(')[1:]
                    vecs = []
                    for r in raw:
                        xyz = r.replace(')', '').strip().split()
                        mag = np.sqrt(sum(float(x)**2 for x in xyz[:3]))
                        vecs.append(mag)
                    values.append(vecs)
                else:
                    # Scalar field
                    vals = [float(x) for x in parts[1:]]
                    values.append(vals)
        
        results[field] = {
            'times': np.array(times),
            'values': np.array(values)
        }
        print(f"  Loaded {field}: {len(times)} samples, {np.array(values).shape[1] if values else 0} probes")
    
    return results

# ============================================================
# 2. Load flow rate data (mitral & aortic)
# ============================================================
def load_flow_rates(case_dir='.'):
    flows = {}
    for patch in ['flowRateMitral', 'flowRateAortic']:
        fpath = os.path.join(case_dir, 'postProcessing', patch, '0', 'surfaceFieldValue.dat')
        if not os.path.exists(fpath):
            print(f"  Warning: {fpath} not found")
            continue
        
        times, phi = [], []
        with open(fpath) as f:
            for line in f:
                if line.strip().startswith('#') or not line.strip():
                    continue
                parts = line.strip().split()
                times.append(float(parts[0]))
                phi.append(float(parts[1]))
        
        flows[patch] = {'times': np.array(times), 'phi': np.array(phi)}
        print(f"  Loaded {patch}: {len(times)} samples")
    
    return flows

# ============================================================
# 3. Extract hemodynamic parameters
# ============================================================
def extract_hemodynamics(probes, flows, cardiac_period=0.8):
    """Extract Windkessel parameters from last cardiac cycle."""
    params = {}
    
    # Use last cardiac cycle (t = 1.6 to 2.4)
    t_start = 2.4 - cardiac_period
    t_end = 2.4
    
    # Pressure statistics
    if 'p' in probes:
        t = probes['p']['times']
        mask = (t >= t_start) & (t <= t_end)
        p_center = probes['p']['values'][mask, 0]  # LV center probe
        
        if len(p_center) > 0:
            # Convert kinematic pressure to mmHg (rho=1060, 1 Pa = 0.00750062 mmHg)
            rho = 1060.0
            p_pa = p_center * rho  # kinematic → Pa
            p_mmhg = p_pa * 0.00750062
            
            params['p_max_mmHg'] = float(np.max(p_mmhg))
            params['p_min_mmHg'] = float(np.min(p_mmhg))
            params['p_mean_mmHg'] = float(np.mean(p_mmhg))
            params['p_range_mmHg'] = float(np.max(p_mmhg) - np.min(p_mmhg))
            
            print(f"\n  LV Pressure (last cycle):")
            print(f"    Peak: {params['p_max_mmHg']:.1f} mmHg")
            print(f"    Min:  {params['p_min_mmHg']:.1f} mmHg")
            print(f"    Mean: {params['p_mean_mmHg']:.1f} mmHg")
    
    # Velocity statistics
    if 'U' in probes:
        t = probes['U']['times']
        mask = (t >= t_start) & (t <= t_end)
        u_center = probes['U']['values'][mask, 0]
        
        if len(u_center) > 0:
            params['u_max_ms'] = float(np.max(u_center))
            params['u_mean_ms'] = float(np.mean(u_center))
            
            print(f"\n  LV Velocity (center, last cycle):")
            print(f"    Peak: {params['u_max_ms']:.3f} m/s")
            print(f"    Mean: {params['u_mean_ms']:.3f} m/s")
    
    # Flow rates
    for patch_name, label in [('flowRateMitral', 'Mitral'), ('flowRateAortic', 'Aortic')]:
        if patch_name in flows:
            t = flows[patch_name]['times']
            phi = flows[patch_name]['phi']
            mask = (t >= t_start) & (t <= t_end)
            phi_cycle = phi[mask]
            t_cycle = t[mask]
            
            if len(phi_cycle) > 0:
                # phi is in m³/s, convert to mL/s
                q_mls = np.abs(phi_cycle) * 1e6
                
                params[f'{label.lower()}_q_max_mls'] = float(np.max(q_mls))
                params[f'{label.lower()}_q_mean_mls'] = float(np.mean(q_mls))
                
                # Stroke volume estimate (integrate over cycle)
                sv_ml = float(np.trapz(q_mls, t_cycle))
                params[f'{label.lower()}_sv_ml'] = sv_ml
                
                print(f"\n  {label} Flow (last cycle):")
                print(f"    Peak:  {np.max(q_mls):.1f} mL/s")
                print(f"    Mean:  {np.mean(q_mls):.1f} mL/s")
                print(f"    SV:    {sv_ml:.1f} mL")
    
    # Windkessel parameters (from aortic flow + pressure)
    if 'p' in probes and 'flowRateAortic' in flows:
        t_p = probes['p']['times']
        t_q = flows['flowRateAortic']['times']
        
        mask_p = (t_p >= t_start) & (t_p <= t_end)
        mask_q = (t_q >= t_start) & (t_q <= t_end)
        
        p_cycle = probes['p']['values'][mask_p, 0] * rho  # Pa
        q_cycle = np.abs(flows['flowRateAortic']['phi'][mask_q])  # m³/s
        
        if len(p_cycle) > 10 and len(q_cycle) > 10:
            # Simple 2-element Windkessel: R = mean(P) / mean(Q)
            q_mean = np.mean(q_cycle)
            p_mean = np.mean(p_cycle)
            
            if q_mean > 0:
                R_total = p_mean / q_mean  # Pa·s/m³
                R_mmhg = R_total * 0.00750062 / 1e6  # mmHg·s/mL
                params['R_total_mmhg_s_ml'] = float(R_mmhg)
                
                # Compliance: C ≈ SV / (P_sys - P_dia)
                p_mmhg_cycle = p_cycle * 0.00750062
                dp = np.max(p_mmhg_cycle) - np.min(p_mmhg_cycle)
                if dp > 0 and 'aortic_sv_ml' in params:
                    C = params['aortic_sv_ml'] / dp  # mL/mmHg
                    params['C_compliance_ml_mmhg'] = float(C)
                
                # Characteristic impedance: Z_c = dP/dQ at early systole
                # (simplified: use peak values)
                Z_c = np.max(p_cycle) / np.max(q_cycle) if np.max(q_cycle) > 0 else 0
                params['Z_c_pa_s_m3'] = float(Z_c)
                
                print(f"\n  Windkessel Parameters:")
                print(f"    R_total: {R_mmhg:.4f} mmHg·s/mL")
                if 'C_compliance_ml_mmhg' in params:
                    print(f"    C:       {params['C_compliance_ml_mmhg']:.4f} mL/mmHg")
                print(f"    Z_c:     {Z_c:.0f} Pa·s/m³")
    
    return params

# ============================================================
# 4. WSS statistics from latest time step
# ============================================================
def analyze_wss(case_dir='.'):
    """Read wallShearStress from latest time directory."""
    time_dirs = sorted(glob.glob(os.path.join(case_dir, '[0-9]*')), 
                       key=lambda x: float(os.path.basename(x)))
    if not time_dirs:
        print("  No time directories found")
        return {}
    
    latest = time_dirs[-1]
    wss_file = os.path.join(latest, 'wallShearStress')
    
    if not os.path.exists(wss_file):
        print(f"  wallShearStress not found in {latest}")
        print(f"  Run: pimpleFoam -postProcess -func wallShearStress -latestTime")
        return {}
    
    print(f"\n  WSS from {os.path.basename(latest)}:")
    # Parse OpenFOAM vector field
    wss_mag = []
    with open(wss_file) as f:
        in_data = False
        for line in f:
            if '(' in line and ')' in line and in_data:
                nums = line.strip().strip('()').split()
                if len(nums) == 3:
                    mag = np.sqrt(sum(float(x)**2 for x in nums))
                    wss_mag.append(mag)
            if line.strip().startswith('(') and not ')' in line:
                in_data = True
            if line.strip() == ')':
                in_data = False
    
    if wss_mag:
        wss = np.array(wss_mag)
        # Convert to physical units (Pa) — already in Pa for incompressible
        wss_pa = wss * 1060  # kinematic → physical (rho=1060)
        
        stats = {
            'wss_mean_Pa': float(np.mean(wss_pa)),
            'wss_max_Pa': float(np.max(wss_pa)),
            'wss_std_Pa': float(np.std(wss_pa)),
            'wss_median_Pa': float(np.median(wss_pa)),
            'n_cells': len(wss_pa),
        }
        
        print(f"    Mean:   {stats['wss_mean_Pa']:.3f} Pa")
        print(f"    Max:    {stats['wss_max_Pa']:.3f} Pa")
        print(f"    Median: {stats['wss_median_Pa']:.3f} Pa")
        print(f"    Cells:  {stats['n_cells']}")
        
        # Clinical reference: normal LV WSS ~ 0.5-2.5 Pa
        if stats['wss_mean_Pa'] < 0.5:
            print(f"    ⚠ Low WSS — may indicate stagnation zones")
        elif stats['wss_mean_Pa'] > 5.0:
            print(f"    ⚠ High WSS — check mesh resolution")
        else:
            print(f"    ✓ WSS in physiological range (0.5-5.0 Pa)")
        
        return stats
    
    return {}


# ============================================================
# Main
# ============================================================
def main():
    print("="*60)
    print("Patient-Specific LV CFD Post-Processing")
    print("="*60)
    
    print("\n[1] Loading probe data...")
    probes = load_probes()
    
    print("\n[2] Loading flow rate data...")
    flows = load_flow_rates()
    
    print("\n[3] Extracting hemodynamic parameters...")
    params = extract_hemodynamics(probes, flows)
    
    print("\n[4] Analyzing WSS...")
    wss = analyze_wss()
    
    # Combine all results
    results = {
        'case': 'MM-WHS Case 1009',
        'simulation': {'endTime': 2.4, 'cardiac_cycles': 3, 'period': 0.8},
        'hemodynamics': params,
        'wss': wss,
    }
    
    # Map to pH-PINN port-Hamiltonian
    if 'R_total_mmhg_s_ml' in params:
        print("\n[5] Mapping to pH-PINN parameters...")
        R = params.get('R_total_mmhg_s_ml', 1.0)
        C = params.get('C_compliance_ml_mmhg', 1.0)
        
        # Port-Hamiltonian: dx/dt = (J-R)∂H/∂x + Bu
        # R_pH = dissipation matrix element
        # C_pH = 1/stiffness in Hamiltonian
        results['port_hamiltonian'] = {
            'R_dissipation': R,
            'C_storage': C,
            'tau_RC': R * C if C else None,
            'note': 'CFD-derived → pH-PINN v5 calibration'
        }
        print(f"    R (dissipation): {R:.4f}")
        print(f"    C (storage):     {C:.4f}")
        if C: print(f"    τ = RC:          {R*C:.4f} s")
    
    out_path = 'cfd_postprocess_results.json'
    with open(out_path, 'w') as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nSaved: {out_path}")

if __name__ == '__main__':
    main()
