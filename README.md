# cardiac-phpinn-workbench

Port-Hamiltonian PINNs for cardiac physiology (Papers A/B), and a patient-specific LV geometry
pipeline from CT segmentation to printable solids, a lost-core silicone flow phantom and a CFD
domain (MM-WHS case 1009).

**Start with [HANDOVER.md](HANDOVER.md)** — it is the index: what is where, what is done, what is
open, and where the traps are.

| strand | entry point |
|---|---|
| Paper A — pH-PINN digital twin | `pinn_cardiac.py`, `PINN_Cardiac_Ees_Manuscript_CMBM_Final.docx`, `manuscript/` (public package: [pH-PINN-cardiac](https://github.com/Kwanhyeong-Lee/pH-PINN-cardiac)) |
| Paper B — value of architectural energy constraints | `waveform_pinn/PAPER_B_OUTLINE.md` → `RESULTS_v*.md` → `models.py` |
| Geometry → print / phantom / CFD | `fusion_ready/PIPELINE.md`, `fusion_ready/METHODS_DRAFT.md` |
| CFD cases (OpenFOAM) | `lv_cfd_patient/run_patient_cfd.sh` |

Data (MIMIC-IV, eICU, INSPIRE, VitalDB, MM-WHS) is **not** in this repository and must never be
added — see `HANDOVER.md` §3 and `.gitignore`. Heavy outputs (STL, GLB, OpenFOAM fields) are
regenerable and excluded; a few final ones are in the handover asset archive.

```
pip install -r requirements.txt          # + torch for your CUDA version
python fusion_ready/build_sdf_grid.py    # smoke test of the geometry stack
```
