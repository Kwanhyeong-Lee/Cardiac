# TASK_PINN_GPU — RTX 3060에서 PINN 학습 (GPU 컴퓨터)

전제: `check_setup.py`에서 **pinn READY**, `gpu_smoke.py`가 **SETUP OK on cuda**.

## 먼저 알아둘 것

- **gpu_smoke가 이미 프로젝트 모델을 GPU에서 학습시켜 본다** — `pinn_hamiltonian_v5.PortHamiltonianPINN`(파라미터 57,798개)을
  그 파일의 `train_pH_PINN`으로, 환자 데이터 없이 합성 배치로 20에폭. 샌드박스 CPU에서 재구성 손실 5,635 → 2,779, 20에폭 6초.
- **알려진 코드 문제 1건 (셋업 문제 아님)** — `DrugPerturbationSimulator.simulate()`는 모델을 `torch.no_grad()` 안에서 부르는데,
  `forward()`가 해밀턴 방정식 때문에 ∂H/∂q를 autograd로 계산하므로 **CPU·GPU 어디서든 항상 실패한다**
  ("element 0 of tensors does not require grad"). 고치면 그다음엔 GPU에서 `dq`/`dp`가 CPU에 만들어지는 문제가 이어서 난다.
  수정안: `with torch.enable_grad():` + 결과 `.detach()`, 그리고 `torch.tensor(pert['dq'], device=q_base.device)`.
  논문 코드이므로 **승인 받은 뒤에** 고치고, 학습·저장된 결과(`phpinn_v5_*`)에는 영향이 없다는 것을 확인할 것.
- **Paper B의 결론은 동결** (HANDOVER §2: "바꾸려면 새 사전 등록으로"). GPU로 다시 돌려서 숫자가 달라져도 결론을 고치는 게 아니라,
  새 실험이면 먼저 사전 등록 문서를 쓰고 돌린다.
- **환자 데이터** — MIMIC·eICU·INSPIRE 파생 CSV는 저장소에 없다. 드라이브로 `$CARDIAC_DATA` 아래에만 두고(PhysioNet DUA),
  학습 산출물 중 환자 단위 파일(예측 CSV 등)은 절대 커밋하지 않는다. 집계 지표 JSON만.

## Claude Code 프롬프트 (GPU 컴퓨터, WSL, `cardiac` 로 venv 켠 뒤)

```
이 컴퓨터에서 PINN 학습이 GPU로 제대로 도는지 확인하고, 실제 실험을 돌릴 준비를 해 줘.
규칙: 환자 단위 데이터나 예측값 파일은 커밋하지 않는다. Paper B 의 동결된 결론은 바꾸지 않는다. 논문 코드 수정은 승인 후에만.

1. python tools/setup/gpu_smoke.py -> "SETUP OK on cuda" 인지. 세 단계의 수치(행렬곱 TFLOP/s, generic 손실, project 20에폭 시간)를 보여줘.
2. HANDOVER.md §2 를 읽고, 저장소 안의 heart_failure_clinical_records.csv (UCI 공개 데이터) 만으로 학습하는 Paper A 스크립트를 찾아서
   짧게(몇 에폭) CPU 와 CUDA 로 각각 돌려 시간을 비교해 줘. 스크립트가 GPU 를 안 쓰게 짜여 있으면, 무엇을 바꿔야 GPU 를 쓰는지만 제안하고 고치지는 마.
3. TASK_PINN_GPU.md 의 알려진 문제(DrugPerturbationSimulator.simulate)에 대해 수정 diff 를 제안해 줘. 적용은 내가 승인한 뒤에.
4. $CARDIAC_DATA 아래에 Paper B 용 추출 CSV 가 있는지만 확인(열어보지 말고 파일 이름과 크기만). 있으면 waveform_pinn/SUMMARY.md 를 읽고
   어떤 스크립트가 무엇을 읽는지 표로 정리해 줘. 돌리지는 말 것 — 무엇을 돌릴지는 내가 정한다.
5. 재현성 기록: torch / CUDA / 드라이버 버전, GPU 이름, 시드를 fusion_ready 가 아니라 저장소 루트의 RUN_ENV_GPU.md 에 적어 줘.
   GPU 커널은 비결정적일 수 있으니, 발표 수치와 비교할 실행에는 torch.use_deterministic_algorithms(True) 가 필요하다는 것도 같이.
```
