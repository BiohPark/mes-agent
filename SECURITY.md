# 보안 정책 (Security Policy)

## 지원 버전 (Supported Versions)

현재 `master` 브랜치만 보안 패치를 지원합니다.

| 버전 | 지원 여부 |
|------|----------|
| master | ✅ 지원 |
| 이전 태그 | ❌ 미지원 |

---

## 취약점 보고 (Reporting a Vulnerability)

MES Agent는 **사내 폐쇄망 환경**에서 운영되는 내부 도구입니다.
보안 취약점을 발견하면 **공개 이슈를 올리지 말고** 아래 경로로 보고해 주세요.

### 보고 경로

1. **이메일**: [qldh1669@gmail.com](mailto:qldh1669@gmail.com)
2. **GitHub 보안 탭**: [Security Advisories](../../security/advisories/new) (비공개 보고)

보고 시 포함할 정보:
- 취약점 설명 (어떤 구성 요소, 어떤 조건)
- 재현 방법 (단계별)
- 잠재적 영향 범위

### 응답 정책

- 접수 확인: 2 영업일 이내
- 초기 평가: 5 영업일 이내
- 패치 목표: 심각도에 따라 1~4주

---

## 보안 설계 원칙

이 프로젝트는 아래 보안 계층을 구현하고 있습니다.

| 계층 | 구현 | 파일 |
|------|------|------|
| 인증 게이트 | `X-Auth-Token` 헤더 + 랜덤 토큰 (Electron이 생성) | `agent/server.py`, `electron/main.js` |
| Origin 차단 | 원격 HTTP(S) Origin 요청 403 반환 | `agent/server.py` |
| 안전 게이트 | 모든 도구 실행 전 `classify_risk()` 위험도 분류 강제 | `agent/tools/_safety.py` |
| 파괴적 명령 차단 | 재귀삭제·포맷·레지스트리·종료 명령 감지 후 차단 | `agent/tools/_safety.py` |
| 시스템 경로 보호 | `C:\Windows`, `C:\Program Files` 등 쓰기 차단 | `agent/tools/_safety.py` |
| 자동 백업 | 파일 덮어쓰기 전 `.bak` 자동 생성 | `agent/tools/document.py` |

> 상세 보안 설계: `docs/adr/0002-L1-loop-contract.md` §5 (G3 안전 게이트)
