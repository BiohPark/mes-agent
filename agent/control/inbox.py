"""백로그 O — 명령함 순수 로직 (I/O 없음 → 테스트 용이).

inbox.md의 `- [ ] 명령` 체크박스를 멱등 마커로 사용한다: 처리하면 `- [x]`로
뒤집어 동기화 재읽기·서버 재시작에도 재실행을 막는다. status.md는 최신 항목을
헤더 바로 아래로 누적(newest-first)한다.
"""

import re

# inbox 미체크 명령 패턴: "- [ ] 명령"
_PENDING_RE = re.compile(r"^\s*-\s*\[ \]\s*(.+?)\s*$", re.MULTILINE)

STATUS_HEADER = "# 🛰️ 에이전트 상태"

INBOX_TEMPLATE = (
    "---\ntype: agent-control-inbox\n---\n\n"
    "# 🛰️ 에이전트 명령함\n\n"
    "`- [ ] 명령` 형식으로 지시하면 에이전트가 실행하고 `status.md`에 결과를 적습니다.\n"
    "처리된 명령은 `- [x]`로 바뀝니다.\n\n"
    "- [ ] 예시: 화면 OCR 해줘\n"
)

_STATUS_SCAFFOLD = "---\ntype: agent-control-status\n---\n\n" + STATUS_HEADER + "\n\n"


def extract_pending(text: str) -> list[str]:
    """`- [ ] 명령` 미체크 라인의 명령 텍스트를 순서대로 반환한다."""
    if not text:
        return []
    return [m.strip() for m in _PENDING_RE.findall(text)]


def mark_processed(text: str, command: str) -> str:
    """`- [ ] {command}` 첫 매칭을 `- [x] {command}`로 치환한다(멱등)."""
    pattern = re.compile(
        r"^(\s*-\s*)\[ \](\s*)" + re.escape(command) + r"\s*$",
        re.MULTILINE,
    )
    return pattern.sub(lambda m: f"{m.group(1)}[x]{m.group(2)}{command}", text, count=1)


def format_status_entry(command: str, result: str, status: str, ts: str) -> str:
    """status.md에 누적할 항목 1개를 포맷한다."""
    body = (result or "").strip() or "(출력 없음)"
    return (
        f"## [{ts}] {command}\n"
        f"- 상태: {status}\n"
        f"- 결과: {body}\n\n"
    )


def prepend_status(existing: str, entry: str) -> str:
    """최신 항목을 헤더 바로 아래에 삽입한다(newest-first). 헤더 없으면 골격 생성."""
    if not existing or STATUS_HEADER not in existing:
        return _STATUS_SCAFFOLD + entry
    head, _, tail = existing.partition(STATUS_HEADER)
    # 헤더 직후 빈 줄을 보존하며 새 항목을 앞에 끼운다
    tail = tail.lstrip("\n")
    return f"{head}{STATUS_HEADER}\n\n{entry}{tail}"
