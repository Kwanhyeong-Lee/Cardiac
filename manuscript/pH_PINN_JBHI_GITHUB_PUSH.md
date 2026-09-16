# GitHub 업로드 가이드 — 재현성 패키지 (Private)

로컬 git 저장소는 **이미 초기화 + 커밋 완료**:
- 위치(Windows): `...\260421 (심장) - main\pH-PINN-cardiac`
- 위치(WSL): `/mnt/c/Users/alex0/OneDrive/PINN/260421 (심장) - main/pH-PINN-cardiac`
- 브랜치 `main`, 파일 42개, 커밋 1개 — 남은 건 GitHub 원격 생성 + push (계정 인증 필요)

> WSL에서는 `C:\...` 백슬래시 경로가 안 먹힙니다. `/mnt/c/...` 를 쓰거나,
> PowerShell에서 해당 폴더로 이동한 뒤 `wsl`을 실행하면 그 폴더에서 바로 시작됩니다.

---

## 0) 먼저 저장소 확인 (WSL, 폴더 안에서)
```bash
git log --oneline -1
# -> 6018418 Initial commit: pH-PINN ...  가 보이면 정상
```

## 방법 A — GitHub CLI (권장). gh 미설치 시 설치부터:
```bash
sudo apt update && sudo apt install gh -y          # (또는: sudo snap install gh)
gh auth login          # GitHub.com -> HTTPS -> "Login with a web browser" -> 코드 입력
gh repo create pH-PINN-cardiac --private --source=. --remote=origin --push \
  --description "Port-Hamiltonian PINN cardiac digital twin - reproducibility package (IEEE JBHI)"
```
`gh`가 본인 계정 아래에 자동 생성 + push. 사용자명 입력 불필요.

## 방법 B — 순수 git (gh 없이, 토큰 필요)
```bash
# 1) github.com -> New repository -> 이름 pH-PINN-cardiac -> Private -> README 추가 안 함 -> Create
# 2) 토큰: github.com -> Settings -> Developer settings -> Personal access tokens (repo 권한)
git remote add origin https://github.com/<본인-깃허브-아이디>/pH-PINN-cardiac.git
git push -u origin main
#    Username = 깃허브 아이디,  Password = 토큰(계정 비밀번호 아님)
```

---

## 게재 확정 시 — Public 전환 + URL 삽입
```bash
gh repo edit --visibility public       # 또는 repo Settings에서 변경
```
그 후 원고 Data and Code Availability 문구에 실제 URL 삽입
(현재: "... will be deposited in a public repository (GitHub/Zenodo) upon acceptance" — 이 시나리오와 일치).

## 참고
- 심사 중에는 Private 유지가 저자 익명성에 안전. 에디터 요청 시에만 링크 공유.
- 폴더가 OneDrive 안에 있어 git은 정상 동작하나, `.git` 동기화가 신경 쓰이면 OneDrive 밖으로 옮긴 뒤 push해도 됨.
- 확인 명령: `git log --oneline`, `git status`, `git remote -v`
