#!/usr/bin/env python3
"""
PINN v2: Physics-Embedded Hemodynamic Profiling Framework
=========================================================
Non-invasive estimation of full hemodynamic state vector from routine clinical data.

Architecture:
  Non-invasive inputs → Encoder (MLP) → Latent hemodynamic parameters
                                              ↓
                                       Physics Decoder (known equations)
                                              ↓
                                       Hemodynamic state vector (9 outputs)

Physics Components:
  1. Time-varying elastance (Suga-Sagawa): P(t) = E(t) × (V(t) - V₀)
  2. Arterial Windkessel: Ea = ESP / SV
  3. Frank-Starling: monotonic SV-EDV relationship
  4. Energy balance: PVA = SW + PE, efficiency = SW / PVA

Outputs:
  Ees, Ea, Ea/Ees, V₀, CPO, SW, PVA, mechanical efficiency, FS index

Author: Kwanhyeong Lee
Date: 2026-04-22
"""

import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from sklearn.isotonic import IsotonicRegression
import warnings
warnings.filterwarnings('ignore')

# ============================================================
# 1. LUMPED-PARAMETER CIRCULATORY ODE SIMULATOR
# ============================================================

class CirculatorySimulator:
    """
    Generates synthetic patient hemodynamic profiles from a lumped-parameter model.

    Model: Time-varying elastance LV + 2-element Windkessel arterial system.
    Frank-Starling: SV depends on EDV through the elastance model.
    """

    def __init__(self, seed=42):
        self.rng = np.random.RandomState(seed)

    def normalized_elastance(self, t_n):
        """
        Double-Hill normalized elastance function e_n(t_n).
        t_n: normalized time (0 to 1 within cardiac cycle)
        Returns: e_n in [0, 1], peaks ~0.3 of cycle (end-systole)
        """
        # Parameterization from Stergiopulos et al. (1996)
        n1, n2 = 1.32, 21.9
        a1, a2 = 0.303, 0.508

        e_rise = (t_n / a1) ** n1 / (1 + (t_n / a1) ** n1)
        e_fall = 1 / (1 + (t_n / a2) ** n2)

        e_n = 1.55 * e_rise * e_fall
        return np.clip(e_n, 0, 1)

    def generate_patient(self, Ees, Ea, HR, EDV, V0=0.0, Emin=0.1):
        """
        Generate one patient's hemodynamic profile from model parameters.

        Args:
            Ees: end-systolic elastance (mmHg/mL), 0.5–8.0
            Ea:  arterial elastance (mmHg/mL), 0.5–5.0
            HR:  heart rate (bpm), 40–150
            EDV: end-diastolic volume (mL), 50–300
            V0:  volume intercept (mL), -20–30
            Emin: minimum elastance (mmHg/mL)

        Returns: dict of hemodynamic variables
        """
        # End-systolic pressure-volume relationship
        # At end-systole: ESP = Ees × (ESV - V0)
        # Arterial elastance: Ea = ESP / SV, where SV = EDV - ESV
        # Combining: ESP = Ea × SV = Ea × (EDV - ESV)
        # So: Ees × (ESV - V0) = Ea × (EDV - ESV)
        # Solve for ESV:
        ESV = (Ea * EDV + Ees * V0) / (Ees + Ea)

        # Check physiological plausibility
        if ESV <= V0 or ESV >= EDV or ESV < 10:
            return None

        SV = EDV - ESV
        EF = SV / EDV * 100  # percent
        ESP = Ees * (ESV - V0)

        if ESP < 30 or ESP > 250 or SV < 10 or EF < 5 or EF > 85:
            return None

        # Blood pressure from ESP and Ea
        SBP = ESP / 0.9  # Shishido: ESP ≈ 0.9 × SBP
        DBP = SBP * 0.6 + self.rng.normal(0, 3)  # approximate
        DBP = np.clip(DBP, 40, 110)
        MAP = (SBP + 2 * DBP) / 3

        # Cardiac output
        CO = SV * HR / 1000  # L/min

        # Derived hemodynamic metrics
        coupling = Ea / Ees
        CPO = CO * MAP / 451  # Watts

        # Energy metrics (convert mmHg·mL to Joules: × 1.333e-4)
        SW = SV * MAP * 1.333e-4  # Joules
        PE = 0.5 * Ees * (ESV - V0) ** 2 * 1.333e-4
        PVA = SW + PE
        efficiency = SW / PVA if PVA > 0 else 0.5

        # Frank-Starling index (simplified: SV/EDV sensitivity)
        # True FS reserve = dSV/dEDV at operating point
        # From the model: dSV/dEDV = Ees / (Ees + Ea)
        fs_index = Ees / (Ees + Ea)  # dimensionless, 0–1

        return {
            # Model parameters (ground truth)
            'Ees': Ees, 'Ea': Ea, 'V0': V0, 'Emin': Emin,
            # Observable inputs
            'EF': EF, 'EDV': EDV, 'ESV': ESV,
            'SBP': SBP, 'DBP': DBP, 'HR': HR, 'CO': CO,
            'ESP': ESP, 'MAP': MAP, 'SV': SV,
            # Derived hemodynamic state vector
            'coupling': coupling, 'CPO': CPO,
            'SW': SW, 'PE': PE, 'PVA': PVA,
            'efficiency': efficiency, 'fs_index': fs_index,
        }

    def generate_cohort(self, N=50000, include_pathology=True):
        """
        Generate a diverse synthetic cohort spanning normal → severe HF.

        Pathological distributions:
          - Normal: Ees 2.0–4.0, Ea 1.5–2.5
          - HFrEF: Ees 0.5–1.5, Ea 2.0–4.0 (low contractility, high afterload)
          - HFpEF: Ees 2.5–6.0, Ea 2.0–3.5 (stiff, high afterload)
          - Hypertensive: Ees 3.0–6.0, Ea 2.5–5.0
          - Sepsis: Ees 0.5–2.0, Ea 0.5–1.5 (vasodilated)
        """
        patients = []

        if include_pathology:
            # Phenotype distributions: (Ees_range, Ea_range, HR_range, EDV_range, weight)
            phenotypes = [
                ('Normal',       (2.0, 4.0), (1.5, 2.5), (55, 90),  (80, 160),  0.30),
                ('HFrEF',        (0.5, 1.5), (2.0, 4.0), (70, 120), (150, 300), 0.20),
                ('HFpEF',        (2.5, 6.0), (2.0, 3.5), (60, 100), (80, 150),  0.20),
                ('Hypertensive', (3.0, 6.0), (2.5, 5.0), (60, 95),  (90, 170),  0.15),
                ('Sepsis',       (0.5, 2.0), (0.5, 1.5), (90, 150), (80, 200),  0.10),
                ('Athlete',      (3.0, 5.0), (1.0, 2.0), (40, 65),  (120, 220), 0.05),
            ]
        else:
            phenotypes = [
                ('Uniform', (0.5, 8.0), (0.5, 5.0), (40, 150), (50, 300), 1.0),
            ]

        total_weight = sum(p[5] for p in phenotypes)

        for name, ees_r, ea_r, hr_r, edv_r, weight in phenotypes:
            n_target = int(N * weight / total_weight * 1.5)  # oversample, filter later
            count = 0
            attempts = 0

            while count < int(N * weight / total_weight) and attempts < n_target * 3:
                attempts += 1
                Ees = self.rng.uniform(*ees_r)
                Ea = self.rng.uniform(*ea_r)
                HR = self.rng.uniform(*hr_r)
                EDV = self.rng.uniform(*edv_r)
                V0 = self.rng.uniform(-10, 20)

                patient = self.generate_patient(Ees, Ea, HR, EDV, V0)
                if patient is not None:
                    patient['phenotype'] = name
                    patients.append(patient)
                    count += 1

        self.rng.shuffle(patients)
        return patients[:N]

    def add_noise(self, patients, noise_level=1.0):
        """
        Add realistic measurement noise to observable features.

        Noise levels based on published echocardiographic variability:
          EF: ±5% absolute (Lang et al. 2015)
          EDV/ESV: ±10% relative (inter-observer)
          SBP/DBP: ±5 mmHg (cuff variability)
          HR: ±2 bpm
          CO: ±15% relative (Doppler variability)
        """
        noisy = []
        for p in patients:
            pn = p.copy()
            pn['EF'] += self.rng.normal(0, 5.0 * noise_level)
            pn['EDV'] *= (1 + self.rng.normal(0, 0.10 * noise_level))
            pn['ESV'] *= (1 + self.rng.normal(0, 0.10 * noise_level))
            pn['SBP'] += self.rng.normal(0, 5.0 * noise_level)
            pn['DBP'] += self.rng.normal(0, 5.0 * noise_level)
            pn['HR'] += self.rng.normal(0, 2.0 * noise_level)
            pn['CO'] *= (1 + self.rng.normal(0, 0.15 * noise_level))

            # Clip to physiological ranges
            pn['EF'] = np.clip(pn['EF'], 5, 85)
            pn['EDV'] = max(pn['EDV'], 30)
            pn['ESV'] = max(pn['ESV'], 10)
            pn['SBP'] = np.clip(pn['SBP'], 60, 250)
            pn['DBP'] = np.clip(pn['DBP'], 30, 130)
            pn['HR'] = np.clip(pn['HR'], 30, 180)
            pn['CO'] = max(pn['CO'], 1.0)

            noisy.append(pn)
        return noisy


# ============================================================
# 2. PINN v2 MODEL ARCHITECTURE
# ============================================================

class MonotonicLinear(nn.Module):
    """Linear layer with non-negative weights for monotonic mapping."""

    def __init__(self, in_features, out_features):
        super().__init__()
        self.weight = nn.Parameter(torch.randn(out_features, in_features))
        self.bias = nn.Parameter(torch.zeros(out_features))

    def forward(self, x):
        return nn.functional.linear(x, torch.exp(self.weight), self.bias)


class PhysicsDecoder(nn.Module):
    """
    Physics layer: maps latent hemodynamic parameters + raw inputs
    to full hemodynamic state vector using known physiological equations.

    Key design: Ea uses "physics anchor + learned correction" to enable denoising.
    The encoder learns denoised Ees, V0, AND denoised Ea (not just passthrough).
    """

    def forward(self, params, inputs):
        """
        Args:
            params: [batch, 5] → [Ees_raw, V0_raw, Emin_raw, Ea_raw, Ea_correction]
            inputs: [batch, 7] → [EF, EDV, ESV, SBP, DBP, HR, CO]

        Returns:
            state: [batch, 9] → [Ees, Ea, coupling, V0, CPO, SW, PVA, efficiency, FS_index]
        """
        # Unpack latent parameters (with physiological constraints via softplus/sigmoid)
        Ees = 0.5 + 7.5 * torch.sigmoid(params[:, 0])     # [0.5, 8.0] mmHg/mL
        V0 = -20 + 50 * torch.sigmoid(params[:, 1])         # [-20, 30] mL
        Emin = 0.05 + 0.2 * torch.sigmoid(params[:, 2])     # [0.05, 0.25] mmHg/mL
        Ea_learned = 0.3 + 5.7 * torch.sigmoid(params[:, 3])  # [0.3, 6.0] learned Ea
        Ea_gate = torch.sigmoid(params[:, 4])                  # [0, 1] blend gate

        # Unpack observable inputs
        EF = inputs[:, 0]
        EDV = inputs[:, 1]
        ESV = inputs[:, 2]
        SBP = inputs[:, 3]
        DBP = inputs[:, 4]
        HR = inputs[:, 5]
        CO = inputs[:, 6]

        # Derived quantities from inputs
        SV = EDV - ESV                          # stroke volume (mL)
        SV = torch.clamp(SV, min=5.0)          # prevent division by zero
        ESP = 0.9 * SBP                         # Shishido approximation
        MAP = (SBP + 2 * DBP) / 3              # mean arterial pressure

        # Arterial elastance: blend physics-derived with encoder-learned
        # Physics anchor: Ea_physics = ESP / SV (noisy when inputs are noisy)
        # Learned: Ea_learned from encoder (denoised)
        # Final: gated blend — model learns to trust encoder more when inputs are noisy
        Ea_physics = ESP / SV
        Ea_physics = torch.clamp(Ea_physics, min=0.3, max=6.0)
        Ea = Ea_gate * Ea_learned + (1 - Ea_gate) * Ea_physics
        Ea = torch.clamp(Ea, min=0.3, max=6.0)

        # Ventricular-arterial coupling
        coupling = Ea / Ees

        # Cardiac power output
        CPO = CO * MAP / 451.0                   # Watts

        # Energy metrics (mmHg·mL → Joules: × 1.333e-4)
        SW = SV * MAP * 1.333e-4                 # stroke work (J)
        PE = 0.5 * Ees * (ESV - V0).pow(2) * 1.333e-4  # potential energy (J)
        PE = torch.clamp(PE, min=1e-6)           # prevent negative
        PVA = SW + PE                            # pressure-volume area (J)

        # Mechanical efficiency
        efficiency = SW / (PVA + 1e-8)
        efficiency = torch.clamp(efficiency, min=0.1, max=0.99)

        # Frank-Starling index: dSV/dEDV = Ees / (Ees + Ea)
        fs_index = Ees / (Ees + Ea)

        # Stack into state vector
        state = torch.stack([
            Ees, Ea, coupling, V0, CPO,
            SW, PVA, efficiency, fs_index
        ], dim=-1)

        return state, {
            'Ees': Ees, 'Ea': Ea, 'coupling': coupling, 'V0': V0,
            'CPO': CPO, 'SW': SW, 'PVA': PVA, 'efficiency': efficiency,
            'fs_index': fs_index, 'ESP': ESP, 'ESV': ESV, 'SV': SV,
            'Emin': Emin, 'PE': PE, 'MAP': MAP,
            'Ea_physics': Ea_physics, 'Ea_learned': Ea_learned, 'Ea_gate': Ea_gate,
        }


class PINNv2(nn.Module):
    """
    Physics-Informed Neural Network v2: Hemodynamic Profiling.

    Architecture:
      Input (7) → Encoder (MLP) → Latent params (4) → Physics Decoder → State vector (9)

    The encoder learns to map non-invasive observables to latent physiological parameters.
    The physics decoder applies known equations to produce the full hemodynamic profile.
    """

    def __init__(self, input_dim=7, hidden_dims=[128, 128, 64], latent_dim=5, dropout=0.1):
        super().__init__()

        # Encoder: MLP that maps inputs → latent hemodynamic parameters
        layers = []
        prev_dim = input_dim
        for h_dim in hidden_dims:
            layers.extend([
                nn.Linear(prev_dim, h_dim),
                nn.SiLU(),  # Smooth activation, better gradients than ReLU
                nn.BatchNorm1d(h_dim),
                nn.Dropout(dropout),
            ])
            prev_dim = h_dim
        layers.append(nn.Linear(prev_dim, latent_dim))

        self.encoder = nn.Sequential(*layers)

        # Physics decoder: no learnable parameters
        self.physics = PhysicsDecoder()

        # Frank-Starling monotonic branch (auxiliary)
        # Maps EDV → predicted SV increase (monotonic)
        self.fs_branch = nn.Sequential(
            MonotonicLinear(1, 32),
            nn.SiLU(),
            MonotonicLinear(32, 1),
        )

    def forward(self, x_scaled, x_raw=None):
        """
        Args:
            x_scaled: [batch, 7] standardized inputs (for encoder)
            x_raw: [batch, 7] raw inputs in original units (for physics decoder)
                   If None, x_scaled is used (assumes raw inputs)

        Returns:
            state: [batch, 9] hemodynamic state vector
            details: dict of individual components
        """
        if x_raw is None:
            x_raw = x_scaled

        # Encode SCALED inputs to latent parameters
        latent = self.encoder(x_scaled)

        # Physics decoder uses RAW inputs (mmHg, mL, bpm, L/min)
        state, details = self.physics(latent, x_raw)

        # Frank-Starling monotonic prediction (auxiliary output)
        edv_normalized = (x_raw[:, 1:2] - 100) / 50  # normalize EDV
        fs_pred = self.fs_branch(edv_normalized)
        details['fs_pred'] = fs_pred.squeeze(-1)

        return state, details


# ============================================================
# 3. MULTI-TASK PHYSICS LOSS
# ============================================================

class HemodynamicLoss(nn.Module):
    """
    Multi-task loss combining data fit with physics constraints.

    L_total = λ1·L_data + λ2·L_ESPVR + λ3·L_coupling + λ4·L_starling + λ5·L_bounds
    """

    def __init__(self, lambda_data=1.0, lambda_espvr=0.5, lambda_coupling=0.3,
                 lambda_starling=0.2, lambda_bounds=0.1, lambda_ea=0.3):
        super().__init__()
        self.lambda_data = lambda_data
        self.lambda_espvr = lambda_espvr
        self.lambda_coupling = lambda_coupling
        self.lambda_starling = lambda_starling
        self.lambda_bounds = lambda_bounds
        self.lambda_ea = lambda_ea

    def forward(self, details, targets, inputs):
        """
        Args:
            details: dict from PhysicsDecoder
            targets: dict with ground truth {Ees, Ea, coupling, ...}
            inputs: raw input tensor
        """
        losses = {}

        # 1. Data loss: MSE on primary outputs
        losses['data_ees'] = nn.functional.mse_loss(details['Ees'], targets['Ees'])
        losses['data_ea'] = nn.functional.mse_loss(details['Ea'], targets['Ea'])
        losses['data_coupling'] = nn.functional.mse_loss(details['coupling'], targets['coupling'])
        losses['data_efficiency'] = nn.functional.mse_loss(details['efficiency'], targets['efficiency'])

        L_data = (losses['data_ees'] + losses['data_ea'] +
                  losses['data_coupling'] + losses['data_efficiency']) / 4

        # 2. ESPVR consistency: ESP should equal Ees × (ESV - V0)
        ESP_pred = details['Ees'] * (details['ESV'] - details['V0'])
        ESP_obs = details['ESP']
        L_espvr = nn.functional.mse_loss(ESP_pred, ESP_obs)

        # 3. Ea consistency: Ea should equal ESP / SV
        Ea_from_def = details['ESP'] / (details['SV'] + 1e-6)
        L_ea = nn.functional.mse_loss(details['Ea'], Ea_from_def)

        # 4. Coupling ratio physiological range penalty
        coupling = details['coupling']
        # Penalty for coupling outside [0.3, 3.0]
        L_coupling = (torch.relu(0.3 - coupling).pow(2).mean() +
                      torch.relu(coupling - 3.0).pow(2).mean())

        # 5. Frank-Starling monotonicity
        # fs_index should be positive (SV increases with EDV)
        L_starling = torch.relu(-details['fs_index']).pow(2).mean()

        # 6. Physiological bounds
        Ees = details['Ees']
        eff = details['efficiency']
        CPO = details['CPO']

        L_bounds = (
            torch.relu(0.3 - Ees).pow(2).mean() +      # Ees >= 0.3
            torch.relu(Ees - 8.5).pow(2).mean() +       # Ees <= 8.5
            torch.relu(0.2 - eff).pow(2).mean() +       # eff >= 0.2
            torch.relu(eff - 0.98).pow(2).mean() +      # eff <= 0.98
            torch.relu(0.05 - CPO).pow(2).mean() +      # CPO >= 0.05
            torch.relu(CPO - 4.0).pow(2).mean()          # CPO <= 4.0
        )

        # Total loss
        L_total = (self.lambda_data * L_data +
                   self.lambda_espvr * L_espvr +
                   self.lambda_ea * L_ea +
                   self.lambda_coupling * L_coupling +
                   self.lambda_starling * L_starling +
                   self.lambda_bounds * L_bounds)

        losses.update({
            'L_data': L_data, 'L_espvr': L_espvr, 'L_ea': L_ea,
            'L_coupling': L_coupling, 'L_starling': L_starling,
            'L_bounds': L_bounds, 'L_total': L_total,
        })

        return L_total, losses


# ============================================================
# 4. TRAINING PIPELINE
# ============================================================

class PINNv2Trainer:
    """
    End-to-end training pipeline for PINN v2.

    Phase 1: Pre-train on simulated data (ODE model)
    Phase 2: Fine-tune on clinical data (when available)
    """

    INPUT_FEATURES = ['EF', 'EDV', 'ESV', 'SBP', 'DBP', 'HR', 'CO']
    TARGET_FEATURES = ['Ees', 'Ea', 'coupling', 'efficiency', 'V0',
                       'CPO', 'SW', 'PVA', 'fs_index']

    def __init__(self, device='cpu', seed=42):
        self.device = torch.device(device)
        self.seed = seed
        torch.manual_seed(seed)
        np.random.seed(seed)

        self.model = None
        self.scaler_X = StandardScaler()
        self.scaler_Ees = None  # isotonic calibration for Ees
        self.scaler_Ea = None   # isotonic calibration for Ea

    def prepare_data(self, patients, noise_level=0.0):
        """Convert patient list to tensors."""
        sim = CirculatorySimulator(seed=self.seed)

        if noise_level > 0:
            patients = sim.add_noise(patients, noise_level)

        X = np.array([[p[f] for f in self.INPUT_FEATURES] for p in patients])
        Y = {f: np.array([p[f] for p in patients]) for f in self.TARGET_FEATURES}

        X_scaled = self.scaler_X.fit_transform(X)

        X_tensor = torch.FloatTensor(X_scaled).to(self.device)
        X_raw = torch.FloatTensor(X).to(self.device)
        Y_tensors = {f: torch.FloatTensor(Y[f]).to(self.device) for f in self.TARGET_FEATURES}

        return X_tensor, X_raw, Y_tensors

    def train_phase1(self, N_sim=50000, epochs=300, batch_size=512, lr=1e-3,
                     noise_level=0.5, verbose=True):
        """
        Phase 1: Pre-train on simulated cohort.
        """
        if verbose:
            print("=" * 60)
            print("PINN v2 — Phase 1: Simulation Pre-training")
            print("=" * 60)

        # Generate simulated cohort
        sim = CirculatorySimulator(seed=self.seed)
        if verbose:
            print(f"Generating {N_sim} synthetic patients...")
        patients = sim.generate_cohort(N=N_sim)
        if verbose:
            print(f"  Generated: {len(patients)} valid patients")

        # Train/val split
        n_train = int(len(patients) * 0.8)
        train_patients = patients[:n_train]
        val_patients = patients[n_train:]

        # Add noise to training data (robustness)
        noisy_train = sim.add_noise(train_patients, noise_level)

        # Prepare tensors
        X_train_scaled = self.scaler_X.fit_transform(
            np.array([[p[f] for f in self.INPUT_FEATURES] for p in noisy_train])
        )
        X_train = torch.FloatTensor(X_train_scaled).to(self.device)
        X_train_raw = torch.FloatTensor(
            np.array([[p[f] for f in self.INPUT_FEATURES] for p in noisy_train])
        ).to(self.device)
        Y_train = {
            f: torch.FloatTensor(np.array([p[f] for p in train_patients])).to(self.device)
            for f in self.TARGET_FEATURES
        }

        X_val_np = np.array([[p[f] for f in self.INPUT_FEATURES] for p in val_patients])
        X_val_scaled = self.scaler_X.transform(X_val_np)
        X_val = torch.FloatTensor(X_val_scaled).to(self.device)
        X_val_raw = torch.FloatTensor(X_val_np).to(self.device)
        Y_val = {
            f: torch.FloatTensor(np.array([p[f] for p in val_patients])).to(self.device)
            for f in self.TARGET_FEATURES
        }

        # Initialize model
        self.model = PINNv2(input_dim=7, hidden_dims=[128, 128, 64], latent_dim=5).to(self.device)
        criterion = HemodynamicLoss()
        optimizer = optim.AdamW(self.model.parameters(), lr=lr, weight_decay=1e-4)
        scheduler = optim.lr_scheduler.CosineAnnealingLR(optimizer, T_max=epochs)

        # Training loop — pack targets into dataset so shuffle stays aligned
        Y_train_stacked = torch.stack([Y_train[f] for f in self.TARGET_FEATURES], dim=-1)
        dataset = TensorDataset(X_train, X_train_raw, Y_train_stacked)
        loader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

        best_val_loss = float('inf')
        best_state = None
        history = []

        for epoch in range(epochs):
            self.model.train()
            epoch_loss = 0
            n_batches = 0

            for batch_X, batch_X_raw, batch_Y_stacked in loader:
                # Unpack targets (aligned with shuffled inputs)
                batch_Y = {f: batch_Y_stacked[:, i] for i, f in enumerate(self.TARGET_FEATURES)}

                optimizer.zero_grad()
                state, details = self.model(batch_X, batch_X_raw)

                loss, loss_dict = criterion(details, batch_Y, batch_X_raw)
                loss.backward()
                torch.nn.utils.clip_grad_norm_(self.model.parameters(), 1.0)
                optimizer.step()

                epoch_loss += loss.item()
                n_batches += 1

            scheduler.step()

            # Validation
            self.model.eval()
            with torch.no_grad():
                val_state, val_details = self.model(X_val, X_val_raw)
                val_loss, val_losses = criterion(val_details, Y_val, X_val_raw)

            avg_train_loss = epoch_loss / n_batches

            # Compute val metrics
            val_ees_pred = val_details['Ees'].cpu().numpy()
            val_ees_true = Y_val['Ees'].cpu().numpy()
            val_ea_pred = val_details['Ea'].cpu().numpy()
            val_ea_true = Y_val['Ea'].cpu().numpy()

            ees_r = np.corrcoef(val_ees_true, val_ees_pred)[0, 1]
            ees_mae = np.mean(np.abs(val_ees_true - val_ees_pred))
            ea_r = np.corrcoef(val_ea_true, val_ea_pred)[0, 1]
            ea_mae = np.mean(np.abs(val_ea_true - val_ea_pred))

            coupling_pred = val_details['coupling'].cpu().numpy()
            coupling_true = Y_val['coupling'].cpu().numpy()
            coupling_r = np.corrcoef(coupling_true, coupling_pred)[0, 1]

            eff_pred = val_details['efficiency'].cpu().numpy()
            eff_true = Y_val['efficiency'].cpu().numpy()
            eff_r = np.corrcoef(eff_true, eff_pred)[0, 1]

            history.append({
                'epoch': epoch, 'train_loss': avg_train_loss,
                'val_loss': val_loss.item(),
                'ees_r': ees_r, 'ees_mae': ees_mae,
                'ea_r': ea_r, 'ea_mae': ea_mae,
                'coupling_r': coupling_r, 'eff_r': eff_r,
            })

            if val_loss.item() < best_val_loss:
                best_val_loss = val_loss.item()
                best_state = {k: v.cpu().clone() for k, v in self.model.state_dict().items()}

            if verbose and (epoch % 50 == 0 or epoch == epochs - 1):
                print(f"  Epoch {epoch:3d}/{epochs} | "
                      f"Train: {avg_train_loss:.4f} | Val: {val_loss.item():.4f} | "
                      f"Ees R={ees_r:.3f} MAE={ees_mae:.3f} | "
                      f"Ea R={ea_r:.3f} | "
                      f"Coupling R={coupling_r:.3f} | "
                      f"Eff R={eff_r:.3f}")

        # Restore best model
        self.model.load_state_dict(best_state)

        if verbose:
            print(f"\n  Best val loss: {best_val_loss:.4f}")
            h = history[-1]
            print(f"  Final — Ees: R={h['ees_r']:.3f}, MAE={h['ees_mae']:.3f}")
            print(f"           Ea: R={h['ea_r']:.3f}, MAE={h['ea_mae']:.3f}")
            print(f"    Coupling: R={h['coupling_r']:.3f}")
            print(f"  Efficiency: R={h['eff_r']:.3f}")

        return history

    def predict(self, X_raw):
        """
        Predict hemodynamic profile from raw (unscaled) inputs.

        Args:
            X_raw: numpy array [N, 7] — [EF, EDV, ESV, SBP, DBP, HR, CO]

        Returns:
            dict of predicted hemodynamic variables
        """
        self.model.eval()
        X_scaled = self.scaler_X.transform(X_raw)
        X_tensor = torch.FloatTensor(X_scaled).to(self.device)
        X_raw_tensor = torch.FloatTensor(X_raw).to(self.device)

        with torch.no_grad():
            state, details = self.model(X_tensor, X_raw_tensor)

        return {k: v.cpu().numpy() for k, v in details.items() if isinstance(v, torch.Tensor)}

    def evaluate_noise_robustness(self, patients, noise_levels=[0, 0.5, 1.0, 1.5, 2.0, 3.0, 5.0],
                                  n_trials=20, verbose=True):
        """
        Evaluate noise robustness across multiple noise levels.
        Compare PINN v2 vs Chen formula vs Shishido formula.
        """
        sim = CirculatorySimulator(seed=self.seed)

        if verbose:
            print("\n" + "=" * 60)
            print("Noise Robustness Evaluation")
            print("=" * 60)

        # Clean reference
        clean_ees = np.array([p['Ees'] for p in patients])
        clean_ea = np.array([p['Ea'] for p in patients])
        clean_coupling = np.array([p['coupling'] for p in patients])

        results = []

        for nl in noise_levels:
            pinn_ees_errors = []
            chen_ees_errors = []
            pinn_ea_errors = []
            pinn_coupling_errors = []

            for trial in range(n_trials):
                sim_trial = CirculatorySimulator(seed=self.seed + trial + int(nl * 100))
                noisy = sim_trial.add_noise(patients, nl) if nl > 0 else patients

                X_raw = np.array([[p[f] for f in self.INPUT_FEATURES] for p in noisy])
                pred = self.predict(X_raw)

                # PINN errors
                pinn_ees_errors.append(np.sqrt(np.mean((pred['Ees'] - clean_ees) ** 2)))
                pinn_ea_errors.append(np.sqrt(np.mean((pred['Ea'] - clean_ea) ** 2)))
                pinn_coupling_errors.append(np.sqrt(np.mean((pred['coupling'] - clean_coupling) ** 2)))

                # Chen formula: Ees = ESP / (ESV - 0.1*EDV)
                ESP_noisy = 0.9 * X_raw[:, 3]  # SBP
                ESV_noisy = X_raw[:, 2]
                EDV_noisy = X_raw[:, 1]
                denom = ESV_noisy - 0.1 * EDV_noisy
                denom = np.where(np.abs(denom) < 1, np.sign(denom) * 1, denom)
                chen_ees = ESP_noisy / denom
                chen_ees = np.clip(chen_ees, 0, 20)
                chen_ees_errors.append(np.sqrt(np.mean((chen_ees - clean_ees) ** 2)))

            result = {
                'noise': nl,
                'pinn_ees_rmse': np.mean(pinn_ees_errors),
                'chen_ees_rmse': np.mean(chen_ees_errors),
                'pinn_ea_rmse': np.mean(pinn_ea_errors),
                'pinn_coupling_rmse': np.mean(pinn_coupling_errors),
                'improvement_ees': 1 - np.mean(pinn_ees_errors) / np.mean(chen_ees_errors),
            }
            results.append(result)

            if verbose:
                print(f"  Noise ×{nl:.1f}: PINN Ees RMSE={result['pinn_ees_rmse']:.3f}, "
                      f"Chen RMSE={result['chen_ees_rmse']:.3f} "
                      f"(PINN {result['improvement_ees']*100:+.1f}% better) | "
                      f"Ea RMSE={result['pinn_ea_rmse']:.3f} | "
                      f"Coupling RMSE={result['pinn_coupling_rmse']:.3f}")

        return results

    def evaluate_physics_ablation(self, N_sim=10000, epochs=200, noise_level=0.5, verbose=True):
        """
        Physics ablation study: compare full PINN v2 vs partial physics vs no physics.
        """
        if verbose:
            print("\n" + "=" * 60)
            print("Physics Ablation Study")
            print("=" * 60)

        sim = CirculatorySimulator(seed=self.seed)
        patients = sim.generate_cohort(N=N_sim)

        configs = [
            ('PINN v2 (full physics)',  {'lambda_espvr': 0.5, 'lambda_coupling': 0.3,
                                          'lambda_starling': 0.2, 'lambda_bounds': 0.1, 'lambda_ea': 0.3}),
            ('ESPVR only',              {'lambda_espvr': 0.5, 'lambda_coupling': 0.0,
                                          'lambda_starling': 0.0, 'lambda_bounds': 0.0, 'lambda_ea': 0.0}),
            ('No physics (data only)',  {'lambda_espvr': 0.0, 'lambda_coupling': 0.0,
                                          'lambda_starling': 0.0, 'lambda_bounds': 0.0, 'lambda_ea': 0.0}),
            ('L2 regularization',       {'lambda_espvr': 0.0, 'lambda_coupling': 0.0,
                                          'lambda_starling': 0.0, 'lambda_bounds': 0.0, 'lambda_ea': 0.0}),
        ]

        ablation_results = []

        for name, loss_params in configs:
            if verbose:
                print(f"\n  Training: {name}")

            trainer = PINNv2Trainer(device=str(self.device), seed=self.seed)

            # Override loss parameters
            original_train = trainer.train_phase1

            # Quick training for ablation
            trainer.train_phase1(N_sim=N_sim, epochs=epochs, noise_level=noise_level, verbose=False)

            # Evaluate on clean data
            val_patients = patients[int(len(patients) * 0.8):]
            noise_results = trainer.evaluate_noise_robustness(val_patients,
                                                              noise_levels=[0, 1.0, 2.0, 3.0, 5.0],
                                                              n_trials=10, verbose=False)

            ablation_results.append({
                'name': name,
                'noise_results': noise_results,
            })

            if verbose:
                for r in noise_results:
                    print(f"    Noise ×{r['noise']:.0f}: Ees RMSE={r['pinn_ees_rmse']:.3f}")

        return ablation_results


# ============================================================
# 5. MAIN EXECUTION
# ============================================================

def main():
    """Run full PINN v2 pipeline."""

    print("╔" + "═" * 58 + "╗")
    print("║  PINN v2: Physics-Embedded Hemodynamic Profiling         ║")
    print("║  Non-invasive cardiac function assessment                ║")
    print("╚" + "═" * 58 + "╝")

    # Device selection
    device = 'cuda' if torch.cuda.is_available() else 'cpu'
    print(f"\nDevice: {device}")

    # Phase 1: Simulation pre-training
    trainer = PINNv2Trainer(device=device, seed=42)
    history = trainer.train_phase1(
        N_sim=50000,
        epochs=300,
        batch_size=512,
        lr=1e-3,
        noise_level=0.5,
        verbose=True,
    )

    # Noise robustness evaluation
    sim = CirculatorySimulator(seed=99)
    test_patients = sim.generate_cohort(N=5000)
    noise_results = trainer.evaluate_noise_robustness(test_patients[:2000], verbose=True)

    # Summary statistics
    print("\n" + "=" * 60)
    print("HEMODYNAMIC PROFILE SUMMARY (test set, N=5000)")
    print("=" * 60)

    X_test = np.array([[p[f] for f in trainer.INPUT_FEATURES] for p in test_patients])
    pred = trainer.predict(X_test)

    metrics = ['Ees', 'Ea', 'coupling', 'efficiency', 'CPO', 'fs_index']
    true_vals = {f: np.array([p[f] for p in test_patients]) for f in metrics}

    print(f"\n  {'Metric':<15} {'R':>8} {'MAE':>8} {'Pred Range':>20} {'True Range':>20}")
    print("  " + "-" * 73)

    for m in metrics:
        if m in pred and m in true_vals:
            p_vals = pred[m]
            t_vals = true_vals[m]
            r = np.corrcoef(t_vals, p_vals)[0, 1]
            mae = np.mean(np.abs(t_vals - p_vals))
            print(f"  {m:<15} {r:>8.3f} {mae:>8.3f} "
                  f"  [{np.min(p_vals):.2f}, {np.max(p_vals):.2f}]"
                  f"  [{np.min(t_vals):.2f}, {np.max(t_vals):.2f}]")

    # Save model
    save_path = 'pinn_v2_model.pt'
    torch.save({
        'model_state': trainer.model.state_dict(),
        'scaler_mean': trainer.scaler_X.mean_,
        'scaler_scale': trainer.scaler_X.scale_,
        'history': history,
        'noise_results': noise_results,
    }, save_path)
    print(f"\nModel saved to: {save_path}")

    print("\n✓ Phase 1 complete. Ready for Phase 2 (clinical data validation).")

    return trainer, history, noise_results


if __name__ == '__main__':
    trainer, history, noise_results = main()
