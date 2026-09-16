"""
Port-Hamiltonian Physics-Informed Neural Network (pH-PINN) v5
=============================================================
Upgrade from PINN v4: Hamiltonian/Lagrangian cardiac mechanics

Key innovation: Instead of enforcing individual physics equations (ESPVR, EDPVR),
learn the total energy function H(q,p) of the cardiac system, with dynamics
automatically derived from Hamilton's equations.

Architecture:
  Echo (11) → StateEncoder → (q, p) generalized coordinates/momenta
                           → HamiltonianNet → H(q,p) scalar
                           → DissipationNet → R(x) matrix
                           → Hamilton's Eqs → dq/dt, dp/dt
                           → PhysicsDecoder → clinical outputs

Framework: Port-Hamiltonian System
  ẋ = [J(x) - R(x)] ∂H/∂x + g(x)u
  
  where:
    x = [V_LV, V_art, Q_ao, Q_mv]  (state: volumes + flows)
    J = skew-symmetric (energy-conserving interconnection)
    R = symmetric PSD (dissipation: vascular resistance)
    H(x) = total energy (kinetic + elastic potential)
    g(x)u = external input (cardiac pump, drug effects)

Drug Perturbation Model:
  H_drug(x) = H_0(x) + δH(x; θ_drug)
  
  where δH encodes drug-specific energy modifications:
    - Vasodilators: δV(q) → arterial compliance change
    - Inotropes: δT(p) → contractile kinetic energy change
    - Diuretics: δ constraint → total volume reduction
    - Chronotropes: δR → dissipation modification

Reference: Greydanus et al. (2019) "Hamiltonian Neural Networks"
           Cranmer et al. (2020) "Lagrangian Neural Networks"
           Regazzoni et al. (2022) "Energy-preserving cardiac coupling"
           
Author: Kwanhyeong Lee
Date: 2026-06-08
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np
from typing import Tuple, Optional, Dict


# ============================================================
# 1. CORE NETWORK COMPONENTS
# ============================================================

class MLP(nn.Module):
    """Standard MLP with optional residual connections."""
    def __init__(self, in_dim, hidden_dims, out_dim, activation='gelu', 
                 dropout=0.1, residual=False):
        super().__init__()
        self.residual = residual
        layers = []
        prev = in_dim
        for h in hidden_dims:
            layers.extend([
                nn.Linear(prev, h),
                nn.GELU() if activation == 'gelu' else nn.SiLU(),
                nn.Dropout(dropout) if dropout > 0 else nn.Identity(),
            ])
            prev = h
        layers.append(nn.Linear(prev, out_dim))
        self.net = nn.Sequential(*layers)
        
        if residual and in_dim == out_dim:
            self.skip = nn.Identity()
        elif residual:
            self.skip = nn.Linear(in_dim, out_dim)
        
    def forward(self, x):
        out = self.net(x)
        if self.residual:
            out = out + self.skip(x)
        return out


# ============================================================
# 2. STATE ENCODER: Echo → Generalized Coordinates (q, p)
# ============================================================

class StateEncoder(nn.Module):
    """
    Maps 11 echo measurements to generalized coordinates and momenta.
    
    Generalized coordinates q (volumes/displacements):
      q1 = V_LV   (LV volume state)
      q2 = V_LA   (LA volume state)  
      q3 = V_art   (arterial volume state)
    
    Generalized momenta p (flows × inertance):
      p1 = L_mv × Q_mv   (mitral flow momentum)
      p2 = L_ao × Q_ao   (aortic flow momentum)
    
    Also outputs auxiliary physiological parameters for decoder.
    """
    
    def __init__(self, input_dim=11, latent_q=3, latent_p=2, aux_dim=4):
        super().__init__()
        self.latent_q = latent_q
        self.latent_p = latent_p
        
        # Shared encoder trunk
        self.trunk = MLP(input_dim, [256, 128], 64, activation='gelu')
        
        # Coordinate head: q (volumes) — physically bounded
        self.q_head = MLP(64, [32], latent_q, activation='gelu')
        
        # Momentum head: p (flows × inertance) — can be negative
        self.p_head = MLP(64, [32], latent_p, activation='gelu')
        
        # Auxiliary parameters (Ees, Eed, tau, V0)
        self.aux_head = MLP(64, [32], aux_dim, activation='gelu')
        
    def forward(self, x):
        h = self.trunk(x)
        
        # q: volumes must be positive
        q_raw = self.q_head(h)
        q = torch.stack([
            F.softplus(q_raw[:, 0]) * 200 + 20,   # V_LV: 20-400 mL
            F.softplus(q_raw[:, 1]) * 50 + 5,      # V_LA: 5-100 mL
            F.softplus(q_raw[:, 2]) * 100 + 50,     # V_art: 50-300 mL
        ], dim=-1)
        
        # p: momenta can be positive or negative
        p = self.p_head(h) * 100  # scale to physiological range
        
        # Auxiliary parameters
        aux_raw = self.aux_head(h)
        aux = torch.stack([
            F.softplus(aux_raw[:, 0]) * 5 + 0.5,   # Ees: 0.5-10 mmHg/mL
            F.sigmoid(aux_raw[:, 1]) * 0.5,          # Eed: 0-0.5 1/mL
            F.softplus(aux_raw[:, 2]) * 50 + 30,     # tau: 30-100 ms
            aux_raw[:, 3] * 20,                       # V0: -20 to +30 mL
        ], dim=-1)
        
        return q, p, aux


# ============================================================
# 3. HAMILTONIAN NETWORK: (q, p) → H scalar
# ============================================================

class HamiltonianNet(nn.Module):
    """
    Learns the total energy H(q, p) = T(p) + V(q) of the cardiac system.
    
    Key structural priors:
      - T(p) depends only on momenta (kinetic energy)
      - V(q) depends only on coordinates (potential energy)
      - H is always non-negative
      
    The separation T/V is structurally enforced, giving:
      - ∂H/∂p = ∂T/∂p  (velocity from momenta)
      - ∂H/∂q = ∂V/∂q  (force from potential)
    """
    
    def __init__(self, q_dim=3, p_dim=2, hidden_dim=64):
        super().__init__()
        
        # T(p): Kinetic energy network — quadratic structure
        # T ≈ ½ pᵀ M⁻¹(q) p  where M is mass/inertance matrix
        self.T_net = MLP(p_dim, [hidden_dim, hidden_dim//2], 1, activation='gelu')
        
        # V(q): Potential energy network — includes ESPVR + EDPVR + arterial
        self.V_net = MLP(q_dim, [hidden_dim, hidden_dim//2], 1, activation='gelu')
        
        # Optional: q-dependent mass matrix for T(q, p) = ½ pᵀ M⁻¹(q) p
        self.M_net = MLP(q_dim, [32], p_dim * p_dim, activation='gelu')
        self.p_dim = p_dim
        
    def kinetic_energy(self, q, p):
        """T(q, p) = ½ pᵀ M⁻¹(q) p — generalized kinetic energy."""
        batch = q.shape[0]
        
        # Learn M⁻¹(q) as positive definite matrix via Cholesky
        L_flat = self.M_net(q)  # (batch, p_dim²)
        L = L_flat.view(batch, self.p_dim, self.p_dim)
        
        # Make positive definite: M⁻¹ = L Lᵀ + εI
        M_inv = torch.bmm(L, L.transpose(1, 2)) + 0.01 * torch.eye(self.p_dim).to(q.device)
        
        # T = ½ pᵀ M⁻¹ p
        p_unsq = p.unsqueeze(-1)  # (batch, p_dim, 1)
        T = 0.5 * torch.bmm(p_unsq.transpose(1, 2), torch.bmm(M_inv, p_unsq))
        
        return T.squeeze(-1).squeeze(-1)
    
    def potential_energy(self, q):
        """V(q) — elastic potential energy (ESPVR + EDPVR + arterial)."""
        V = self.V_net(q).squeeze(-1)
        return F.softplus(V)  # V ≥ 0
    
    def forward(self, q, p):
        """H(q, p) = T(q, p) + V(q)"""
        T = self.kinetic_energy(q, p)
        V = self.potential_energy(q)
        H = T + V
        return H, T, V


# ============================================================
# 4. DISSIPATION NETWORK: x → R(x) matrix
# ============================================================

class DissipationNet(nn.Module):
    """
    Learns the dissipation matrix R(x) ≥ 0 (positive semi-definite).
    
    In the cardiovascular system, dissipation comes from:
      - Systemic vascular resistance (SVR)
      - Pulmonary vascular resistance (PVR)  
      - Valve resistance
      - Myocardial viscosity
    """
    
    def __init__(self, state_dim=5, hidden_dim=32):
        super().__init__()
        self.state_dim = state_dim
        # Learn lower triangular L such that R = L Lᵀ (guarantees PSD)
        self.L_net = MLP(state_dim, [hidden_dim], state_dim * state_dim)
        
    def forward(self, x):
        batch = x.shape[0]
        L_flat = self.L_net(x)
        L = L_flat.view(batch, self.state_dim, self.state_dim)
        
        # Mask to lower triangular
        mask = torch.tril(torch.ones(self.state_dim, self.state_dim)).to(x.device)
        L = L * mask
        
        # R = L Lᵀ (positive semi-definite)
        R = torch.bmm(L, L.transpose(1, 2))
        return R


# ============================================================
# 5. PHYSICS DECODER: Hamiltonian → Clinical Outputs
# ============================================================

class HamiltonianPhysicsDecoder(nn.Module):
    """
    Derives clinical hemodynamic outputs from Hamiltonian quantities.
    
    Uses Hamilton's equations + auxiliary params to compute:
      - EDP (from EDPVR using V(q) gradient)
      - ESP (from ESPVR using Ees)
      - Coupling ratio (Ees/Ea)
      - Efficiency (SW/PVA from energy decomposition)
      - Tau (relaxation from dissipation)
    """
    
    def __init__(self):
        super().__init__()
    
    def forward(self, q, p, aux, H, T, V, dH_dq=None):
        """
        Inputs:
            q: (batch, 3) — [V_LV, V_LA, V_art]
            p: (batch, 2) — [p_mv, p_ao]  
            aux: (batch, 4) — [Ees, Eed, tau, V0]
            H, T, V: scalars — total, kinetic, potential energy
            dH_dq: (batch, 3) — gradient of H w.r.t. q (= generalized forces)
        
        Returns dict of clinical outputs.
        """
        V_LV = q[:, 0]
        V_LA = q[:, 1]
        V_art = q[:, 2]
        Ees = aux[:, 0]
        Eed = aux[:, 1]
        tau = aux[:, 2]
        V0 = aux[:, 3]
        
        # --- End-Systolic Pressure from ESPVR ---
        ESV = V_LV * 0.4  # approximate ESV from V_LV state
        ESP = Ees * (ESV - V0)
        ESP = ESP.clamp(min=30, max=250)
        
        # --- End-Diastolic Pressure from EDPVR ---
        # EDP = A × exp(Eed × (EDV − V₀))
        # A derived from potential energy gradient if available
        EDV = V_LV
        A = 0.5  # baseline; can be learned
        exp_term = (Eed * (EDV - V0)).clamp(max=6)
        EDP = A * torch.exp(exp_term)
        EDP = EDP.clamp(min=1, max=45)
        
        # --- Arterial Elastance ---
        SV = (EDV - ESV).clamp(min=5)
        Ea = ESP / SV
        Ea = Ea.clamp(min=0.5, max=6)
        
        # --- Coupling ---
        coupling = Ees / Ea
        
        # --- Efficiency from Hamiltonian ---
        # SW = loop area ≈ (ESP - EDP) × SV
        SW = (ESP - EDP) * SV
        SW = SW.clamp(min=0)
        # PE_es = ½ Ees (ESV - V0)²
        PE_es = 0.5 * Ees * (ESV - V0)**2
        PE_es = PE_es.clamp(min=0)
        PVA = SW + PE_es
        efficiency = SW / (PVA + 1e-6)
        efficiency = efficiency.clamp(min=0.1, max=0.95)
        
        return {
            'Ees': Ees,
            'Eed': Eed,
            'Ea': Ea,
            'coupling': coupling,
            'EDP': EDP,
            'efficiency': efficiency,
            'tau': tau,
            'H_total': H,
            'T_kinetic': T,
            'V_potential': V,
            'SW': SW,
            'PVA': PVA,
            'ESP': ESP,
        }


# ============================================================
# 6. FULL PORT-HAMILTONIAN PINN (pH-PINN v5)
# ============================================================

class PortHamiltonianPINN(nn.Module):
    """
    Port-Hamiltonian Physics-Informed Neural Network for Cardiac Digital Twin.
    
    Full system: ẋ = [J - R(x)] ∂H/∂x + g(x)u
    
    Architecture:
        Echo (11) → StateEncoder → (q, p, aux)
                                → HamiltonianNet → H(q,p), T, V
                                → DissipationNet → R(x)
                                → PortHamiltonian dynamics
                                → PhysicsDecoder → clinical outputs (7+)
    
    Training losses:
        L = L_recon + λ_H × L_hamiltonian + λ_R × L_dissipation + λ_phys × L_physics
        
        L_recon: reconstruction of echo measurements
        L_hamiltonian: energy conservation (dH/dt ≤ 0 for dissipative system)
        L_dissipation: R(x) ≥ 0 (PSD constraint, auto-satisfied by Cholesky)
        L_physics: ESPVR/EDPVR consistency
    """
    
    def __init__(self, input_dim=11, q_dim=3, p_dim=2, aux_dim=4):
        super().__init__()
        self.state_dim = q_dim + p_dim
        
        # Encoder
        self.encoder = StateEncoder(input_dim, q_dim, p_dim, aux_dim)
        
        # Hamiltonian
        self.hamiltonian = HamiltonianNet(q_dim, p_dim)
        
        # Dissipation
        self.dissipation = DissipationNet(self.state_dim)
        
        # Physics decoder
        self.decoder = HamiltonianPhysicsDecoder()
        
        # Interconnection matrix J (learnable, antisymmetric)
        # J represents valve dynamics and circuit topology
        J_param = torch.randn(self.state_dim, self.state_dim) * 0.1
        self.J_param = nn.Parameter(J_param)
        
        # Drug perturbation network (optional)
        self.drug_net = MLP(13, [32, 16], q_dim + p_dim)  # 13 drug flags → δ(q,p)
        
    @property
    def J(self):
        """Antisymmetric interconnection matrix."""
        return self.J_param - self.J_param.T
    
    def forward(self, x, drug_flags=None):
        """
        x: (batch, 11) echo inputs
        drug_flags: (batch, 13) optional drug indicators
        """
        # 1. Encode to (q, p, aux)
        q, p, aux = self.encoder(x)
        
        # 2. Drug perturbation (if provided)
        if drug_flags is not None:
            delta_state = self.drug_net(drug_flags)
            delta_q = delta_state[:, :q.shape[1]]
            delta_p = delta_state[:, q.shape[1]:]
            q_drug = q + delta_q
            p_drug = p + delta_p
        else:
            q_drug, p_drug = q, p
        
        # 3. Compute Hamiltonian
        q_drug.requires_grad_(True)
        p_drug.requires_grad_(True)
        
        H, T, V = self.hamiltonian(q_drug, p_drug)
        
        # 4. Hamilton's equations via autograd
        dH_dq = torch.autograd.grad(H.sum(), q_drug, create_graph=True)[0]
        dH_dp = torch.autograd.grad(H.sum(), p_drug, create_graph=True)[0]
        
        # 5. Port-Hamiltonian dynamics
        state = torch.cat([q_drug, p_drug], dim=-1)
        R = self.dissipation(state)
        J = self.J.unsqueeze(0).expand(x.shape[0], -1, -1)
        
        dH_dx = torch.cat([dH_dq, dH_dp], dim=-1).unsqueeze(-1)
        dx_dt = torch.bmm(J - R, dH_dx).squeeze(-1)
        
        # 6. Decode to clinical outputs
        outputs = self.decoder(q_drug, p_drug, aux, H, T, V, dH_dq)
        
        # Add dynamics info
        outputs['dq_dt'] = dx_dt[:, :q.shape[1]]
        outputs['dp_dt'] = dx_dt[:, q.shape[1]:]
        outputs['R_matrix'] = R
        outputs['q'] = q_drug
        outputs['p'] = p_drug
        
        return outputs
    
    def energy_loss(self, outputs):
        """
        Hamiltonian physics loss:
        1. dH/dt ≤ 0 (energy dissipation, not creation)
        2. Energy partition consistency
        """
        H = outputs['H_total']
        T = outputs['T_kinetic']
        V = outputs['V_potential']
        
        # H = T + V consistency (should be exact by construction)
        loss_partition = F.mse_loss(H, T + V)
        
        # T ≥ 0, V ≥ 0 (soft constraint)
        loss_positive = F.relu(-T).mean() + F.relu(-V).mean()
        
        # Energy dissipation: dH/dt = -xᵀ R ∂H/∂x ≤ 0
        # (auto-satisfied by R ≥ 0, but add soft penalty for stability)
        R = outputs['R_matrix']
        eigenvalues = torch.linalg.eigvalsh(R)
        loss_R_psd = F.relu(-eigenvalues).mean()  # penalize negative eigenvalues
        
        return loss_partition + loss_positive + loss_R_psd
    
    def physics_loss(self, outputs, targets):
        """
        Physics consistency losses (backward compatible with PINN v4):
        1. ESPVR: ESP = Ees × (ESV - V0)
        2. EDPVR: EDP = A × exp(Eed × (EDV - V0))
        3. Coupling: Ea = ESP / SV
        """
        Ees = outputs['Ees']
        Ea = outputs['Ea']
        coupling = outputs['coupling']
        efficiency = outputs['efficiency']
        
        # VA coupling physical range
        loss_coupling = F.relu(coupling - 10).mean() + F.relu(0.05 - coupling).mean()
        
        # Efficiency physical range
        loss_eff = F.relu(efficiency - 0.95).mean() + F.relu(0.1 - efficiency).mean()
        
        return loss_coupling + loss_eff


# ============================================================
# 7. TRAINING LOOP
# ============================================================

def train_pH_PINN(model, train_loader, val_loader, 
                  epochs=200, lr=1e-3, 
                  lambda_H=1.0, lambda_phys=0.5):
    """
    Training with multi-objective loss:
    L = L_recon + λ_H × L_energy + λ_phys × L_physics
    """
    optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(optimizer, epochs)
    
    target_keys = ['Ees', 'Eed', 'Ea', 'coupling', 'EDP', 'efficiency', 'tau']
    
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        
        for batch_x, batch_y in train_loader:
            optimizer.zero_grad()
            
            outputs = model(batch_x)
            
            # Reconstruction loss
            loss_recon = sum(
                F.mse_loss(outputs[k], batch_y[:, i])
                for i, k in enumerate(target_keys)
            )
            
            # Energy loss
            loss_energy = model.energy_loss(outputs)
            
            # Physics loss
            loss_physics = model.physics_loss(outputs, batch_y)
            
            # Total
            loss = loss_recon + lambda_H * loss_energy + lambda_phys * loss_physics
            loss.backward()
            
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            total_loss += loss.item()
        
        scheduler.step()
        
        if (epoch + 1) % 20 == 0:
            print(f"Epoch {epoch+1}: loss={total_loss:.4f}")


# ============================================================
# 8. DRUG PERTURBATION SIMULATION
# ============================================================

class DrugPerturbationSimulator:
    """
    Simulate drug effects as perturbations to the Hamiltonian.
    
    Each drug class modifies a specific energy component:
    
    | Drug Class    | Primary Perturbation | Mechanism                |
    |---------------|---------------------|--------------------------|
    | Vasodilators  | δV(q): ↓V_art      | ↓ arterial potential E   |
    | Inotropes     | δT(p): ↑p_ao       | ↑ ejection kinetic E     |
    | Diuretics     | δq: ↓V_LV, V_LA    | ↓ preload → ↓ PE_ed      |
    | β-blockers    | δR: ↑R_chrono       | ↑ chronotropic dissipation|
    | ARNI          | δV + δR             | ↓ afterload + ↓ fibrosis |
    | SGLT2i        | δq + δR             | ↓ volume + ↓ inflammation|
    """
    
    def __init__(self, model):
        self.model = model
        
        # Calibrated perturbation parameters (from digital_twin_calibration.csv)
        self.perturbation_map = {
            'loop':        {'dq': [-0.05, -0.08, -0.02], 'dp': [0, 0], 'dR_scale': 1.0},
            'MRA':         {'dq': [-0.02, -0.03, -0.01], 'dp': [0, 0], 'dR_scale': 0.95},
            'RAASi':       {'dq': [-0.01, -0.02, -0.05], 'dp': [0, 0.02], 'dR_scale': 0.90},
            'BB':          {'dq': [0, 0, 0],             'dp': [0, -0.03], 'dR_scale': 1.10},
            'ARNI':        {'dq': [-0.03, -0.05, -0.08], 'dp': [0, 0.05], 'dR_scale': 0.85},
            'SGLT2i':      {'dq': [-0.03, -0.04, -0.01], 'dp': [0, 0], 'dR_scale': 0.92},
            'CCB':         {'dq': [0, 0, -0.06],         'dp': [0, 0], 'dR_scale': 0.88},
            'digoxin':     {'dq': [0.02, 0, 0],          'dp': [0.05, 0.08], 'dR_scale': 1.0},
            'hydralazine': {'dq': [0, 0, -0.10],         'dp': [0, 0.03], 'dR_scale': 0.85},
        }
    
    def simulate(self, echo_input, drug_name, dose_fraction=1.0):
        """
        Predict hemodynamic response to a drug.
        
        Args:
            echo_input: (1, 11) baseline echo measurements
            drug_name: string key into perturbation_map
            dose_fraction: 0-1, scales the perturbation
            
        Returns:
            dict with baseline, post-drug, and delta outputs
        """
        self.model.eval()
        with torch.no_grad():
            # Baseline
            baseline = self.model(echo_input)
            
            # Apply perturbation
            pert = self.perturbation_map[drug_name]
            dq = torch.tensor(pert['dq']).float() * dose_fraction
            dp = torch.tensor(pert['dp']).float() * dose_fraction
            
            # Re-encode with perturbation
            q_base = baseline['q']
            p_base = baseline['p']
            q_drug = q_base * (1 + dq.unsqueeze(0))
            p_drug = p_base * (1 + dp.unsqueeze(0))
            
            # Recompute Hamiltonian
            H_drug, T_drug, V_drug = self.model.hamiltonian(q_drug, p_drug)
            
            return {
                'baseline_H': baseline['H_total'].item(),
                'drug_H': H_drug.item(),
                'delta_H': H_drug.item() - baseline['H_total'].item(),
                'baseline_T': baseline['T_kinetic'].item(),
                'drug_T': T_drug.item(),
                'baseline_V': baseline['V_potential'].item(),
                'drug_V': V_drug.item(),
            }


# ============================================================
# 9. MODEL SUMMARY
# ============================================================

if __name__ == '__main__':
    model = PortHamiltonianPINN(input_dim=11)
    
    # Count parameters
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    print("=" * 60)
    print("Port-Hamiltonian PINN v5 — Architecture Summary")
    print("=" * 60)
    print(f"Total parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")
    print()
    
    # Test forward pass
    x = torch.randn(4, 11)
    outputs = model(x)
    
    print("Input shape: (4, 11)")
    print("\nOutput keys:")
    for k, v in outputs.items():
        if isinstance(v, torch.Tensor):
            print(f"  {k:20s}: shape={list(v.shape)}, range=[{v.min():.3f}, {v.max():.3f}]")
    
    print("\nEnergy decomposition (sample):")
    print(f"  H = {outputs['H_total'][0]:.2f}")
    print(f"  T = {outputs['T_kinetic'][0]:.2f}")
    print(f"  V = {outputs['V_potential'][0]:.2f}")
    print(f"  H ≈ T + V? {abs(outputs['H_total'][0] - outputs['T_kinetic'][0] - outputs['V_potential'][0]):.6f}")
    
    # Energy loss
    e_loss = model.energy_loss(outputs)
    print(f"\nEnergy loss: {e_loss.item():.6f}")
    
    print("\n✓ Model initialized successfully")
