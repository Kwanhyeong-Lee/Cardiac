# Fusion 360 MCP — 이 세션에 붙이는 법

## 확인된 사실 (2026-09-15, 앱 내장 브라우저로 직접 프로브)

| 항목 | 결과 | 의미 |
|---|---|---|
| `http://localhost:7654/` | 200, `{"error":"Not found"}` | 살아 있음, JSON API |
| `GET /health` | **401** Unauthorized | 실제 엔드포인트, 토큰 필요 |
| `POST /mcp` (JSON-RPC `initialize`) | **401** Unauthorized | MCP 엔드포인트가 맞음, 토큰 필요 |
| 그 외 경로 | 404 | — |
| `OPTIONS /` | 501 | Python stdlib `http.server` |
| `Server` 헤더 | `BaseHTTP/0.6 Python/3.14.0` | **Fusion 360 번들 파이썬** → 서버가 Fusion 프로세스 안에서 애드인으로 실행 중 |

결론: **Fusion 애드인이 7654에서 토큰 인증 streamable-HTTP MCP를 서비스**하고 있습니다.
Fusion이 꺼지거나 애드인이 멈추면 포트도 죽습니다.

## 왜 Claude가 아직 못 쓰는가

MCP 서버가 사용자 PC에서 돌아가는 것과, 그 서버가 **이 Cowork 세션의 도구로 등록**된 것은
별개입니다. 등록되면 `mcp__<이름>__*` 도구가 Claude 도구 목록에 나타납니다. 현재 그 목록에
Fusion 관련 도구는 없습니다(`fusion / autodesk / cad / sketch / extrude`로 전수 검색함).
Claude Code의 `.mcp.json` / `~/.claude.json`에 넣은 항목은 Cowork로 자동 전파되지 않습니다.

## 등록 절차

1. **Fusion 360이 켜져 있고 애드인이 실행 중**인지 확인 (7654가 살아 있으면 OK).
2. Claude 데스크톱 앱 → **설정 → Connectors(커넥터)** → **커스텀 MCP 서버 추가**.
3. URL: `http://localhost:7654/mcp`
   (연결 실패 시 `http://localhost:7654` 로 재시도)
4. 인증: 애드인이 요구하는 **Bearer 토큰**을 앱의 인증 헤더 칸에 입력.
   - 토큰 위치: 보통 애드인 시작 시 Fusion **Text Commands** 팔레트에 출력되거나,
     `%APPDATA%\Autodesk\Autodesk Fusion 360\API\AddIns\<애드인 폴더>\` 안의
     `config.json` / `.env` / `token.txt` 류 파일에 있음.
   - **토큰은 Claude에게 채팅으로 주지 말 것.** 앱 설정에만 넣으면 됨.
5. 저장 후 세션에서 "연결됐다"고 한 마디 → Claude가 도구 목록을 다시 검색해 확인.

## 등록이 실패하면

`initialize`가 완료되지 않으면 7654는 **애드인의 내부 HTTP 포트**이고, 실제 MCP는 별도의
**stdio 브리지 프로세스**(보통 `python .../mcp_server.py` 또는 `uvx ...`)일 가능성이 큽니다.
그 경우 등록해야 할 것은 URL이 아니라 그 실행 명령입니다 — 설치한 저장소 README의
"Claude Desktop 설정" 절에 명령이 적혀 있습니다. 저장소 이름을 알려주면 정확히 짚어 드립니다.

## 연결 뒤 Claude가 할 수 있는 것

애드인이 노출하는 도구에 따라 다르지만, 이 계열 MCP는 대개 `run_script`(Fusion 안에서
파이썬 실행), 스케치/돌출/불리언, 메쉬 임포트, STEP/STL 내보내기를 제공합니다. 그러면
`fusion_ready/`의 STL을 **제가 직접** 임포트·정리·BRep 변환까지 몰 수 있습니다.
