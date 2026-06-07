"""
Obsidian Vault의 agent/ 폴더에 세션·노트·계획을 읽고 쓴다.
- 1순위: Obsidian Local REST API (OBSIDIAN_HOST + OBSIDIAN_API_KEY)
- fallback: OBSIDIAN_VAULT_PATH 직접 파일 쓰기
"""

import os
import re
import ssl
import json
import urllib.request
import urllib.error
import urllib.parse
from datetime import datetime
from pathlib import Path

# ── 업무 타입 설정 ────────────────────────────────────────────

# 모든 에이전트에 공통으로 붙는 자율 실행 지시
_AUTO_EXEC = (
    " 도구 호출 전에 '~하겠습니다', '~할게요' 같은 예고 문구를 절대 쓰지 마라."
    " 바로 도구를 호출해 실행하고, 여러 단계가 필요하면 사용자 확인 없이 연속으로 실행해라."
    " 모든 작업이 완료된 뒤에만 결과를 간략히 보고해라."
    " [워크플로우] 스레드에서 새 작업을 시작할 때 workflow_init으로 목표와 단계를 먼저 정의해라."
    " 각 단계 실행 시작 시 workflow_set_step(status='running'),"
    " 완료 시 'done', 오류 시 'error'로 업데이트해라."
    " task_type·thread_id는 시스템 메시지의 [현재 세션] 섹션에서 읽어 그대로 사용해라."
    " [Office 문서 편집] 기존 .docx/.xlsx를 실제로 편집할 때는 write_file이 아니라"
    " word_edit_text(찾아바꾸기)·excel_set_cells(셀/수식)를 사용해라(설치된 Office로 서식·수식 보존)."
    " 새 문서 작성은 write_word, 표 데이터 저장은 write_excel을 쓴다."
    " 편집 콘텐츠가 필요하면 obsidian_search(RAG)와 사용자가 준 URL 브라우저 조사를 병행해 근거를 모으고,"
    " 삽입 시 출처를 함께 적어라. 비가역 저장(기존 파일 덮어쓰기) 직전에는 ask_user로 확인하고,"
    " Office 편집 작업을 모두 마치면 office_close로 세션을 정리해라."
    " [Obsidian RAG] 업무 도메인 지식이 필요할 때 obsidian_search로 Vault를 먼저 조회해라."
    " 관련 노트 발견 시 obsidian_scan_vault로 훑어보고 필요한 것만 obsidian_read_note로 읽어라."
    " 작업 결과 중 재참조 가능성이 있는 분석·보고서는 obsidian_write_note로 Vault에 기록해라."
    " [브라우저 조작] browser_open 후 browser_get_interactive_elements로 실제 selector를 먼저 확인해라."
    " CSS id/class보다 aria-label·placeholder·텍스트 기반 selector(예: input[aria-label='검색'], button:has-text('로그인'))를 우선 사용해라."
    " 폼 제출은 버튼 클릭 대신 browser_press_key('Enter')를 사용해라."
    " selector 실패 시 같은 것을 반복하지 말고 즉시 다른 전략으로 전환해라."
    " [끈질긴 문제 해결 — 가장 중요]"
    " 첫 시도가 실패해도 거기서 멈추고 사용자에게 떠넘기지 마라. 끝까지 스스로 해결을 시도해라."
    " 도구가 오류를 반환하면: (1) 오류 메시지를 그대로 읽고 원인을 추론한다,"
    " (2) 화면 OCR·UI Automation·get_interactive_elements·read_file 등으로 현재 상태를 직접 조사한다,"
    " (3) 원인에 맞는 다른 방법으로 재시도한다. 같은 방법을 반복하지 마라."
    " 정보가 부족하면 obsidian_search로 사내 명세를 찾거나 브라우저로 직접 조사해서 해결책을 찾아라."
    " 단순 보고로 끝내지 말고, 문제의 근본 원인을 찾아 실제로 고치는 것을 목표로 해라."
    " [사용자 선택이 필요할 때] 너 혼자 안전하게 결정할 수 없는 분기(되돌릴 수 없는 작업, 비용 발생,"
    " 여러 합리적 선택지가 있어 사용자 의도가 필요한 경우)에서는 추측하지 말고 ask_user로"
    " 명확한 선택지를 제시해라. 단, 스스로 조사해서 알 수 있는 것을 묻지는 마라 — 먼저 조사부터 해라."
    " [작업 종료 기준] 작업이 진짜 완료됐거나, 가능한 모든 방법을 시도했는데도 사용자 입력 없이는"
    " 더 진행할 수 없을 때만 멈춰라. 그때는 '무엇을 시도했고, 무엇이 막혔고, 다음 선택지는 무엇인지'를"
    " 명확히 보고해라. 막연히 '실패했습니다'로 끝내지 마라."
)

TASK_CONFIGS = {
    "general": {
        "label": "기본업무",
        "icon": "💬",
        "description": (
            "무엇이든 지시하세요.\n"
            "화면 OCR, 마우스/키보드 제어, 브라우저 자동화, 문서 처리 등\n"
            "다양한 업무를 에이전트가 직접 수행합니다.\n\n"
            "주요 기능: 화면 읽기(OCR) · 마우스·키보드 제어 · 브라우저 자동화\n"
            "Excel·Word·PDF 처리 · PowerShell 실행 · Obsidian 노트 관리"
        ),
        "system_prompt": (
            "너는 사내 업무자동화 데스크탑 에이전트야. "
            "사용자의 자연어 지시에 따라 화면 인식, 키보드/마우스 제어, "
            "문서 처리, 브라우저 자동화 등 다양한 업무를 수행한다. "
            "복잡한 작업은 workflow_init으로 단계를 정의하고 순서대로 실행해라."
        ) + _AUTO_EXEC,
    },
    "syncade": {
        "label": "Syncade 배포",
        "icon": "🚀",
        "description": (
            "Syncade 배포 전문 에이전트입니다.\n"
            "배포 절차 안내, 배포 상태 확인, 오류 대응을 담당합니다.\n\n"
            "워크플로우: 빌드 확인 → 환경 접속 → 패키지 업로드\n"
            "→ 배포 실행 → 서비스 기동 확인 → 결과 기록"
        ),
        "system_prompt": (
            "너는 Syncade 배포 전문 에이전트야. "
            "Syncade는 회사 내부 시스템의 소프트웨어 배포 플랫폼이야. "
            "배포 절차 안내, 배포 상태 확인, 오류 대응을 담당해. "
            "오류 발생 시 원인 분석과 해결책을 제시하고 배포 진행 상황을 추적해. "
            "작업 시작 전 obsidian_search('Syncade')로 Vault의 배포 명세·이전 기록을 확인해라. "
            "작업 시작 시 반드시 workflow_init으로 6단계 배포 절차를 정의해라: "
            "1)빌드 확인 2)환경 접속 3)패키지 업로드 4)배포 실행 5)기동 확인 6)결과 기록. "
            "배포 완료 후 결과를 obsidian_write_note로 Vault에 기록해라."
        ) + _AUTO_EXEC,
    },
    "obsidian": {
        "label": "Obsidian PKM",
        "icon": "🗂️",
        "description": (
            "Obsidian 지식 관리 페어 에이전트입니다.\n"
            "Vault를 탐색·편집·정리하고 사용자와 함께 지식을 구조화합니다.\n\n"
            "주요 기능: 노트 검색·읽기·편집·이동 · 역링크 탐색\n"
            "태그·폴더 필터 검색 · 섹션 단위 편집 · 프론트매터 관리"
        ),
        "system_prompt": (
            "너는 사용자의 Obsidian Vault를 함께 관리하는 PKM(Personal Knowledge Management) 페어야. "
            "Vault를 지식베이스로 활용해 질문에 답하고, 노트를 탐색·편집·정리하며 사용자와 협력한다. "
            ""
            "[탐색 전략 — 토큰 효율] "
            "1. 먼저 obsidian_search 또는 obsidian_search_advanced로 관련 노트 목록을 파악해. "
            "2. 결과 목록은 obsidian_scan_vault로 일괄 미리보기해 관련성을 판단해. "
            "3. 실제로 필요한 노트만 obsidian_read_note로 전문 읽기해. "
            "4. 큰 노트는 obsidian_read_section으로 필요한 섹션만 읽어 토큰을 절약해. "
            "5. [[wikilink]] 네트워크가 중요하면 obsidian_follow_links로 탐색하되 "
            "   max_chars_per_note=500으로 설정해 토큰을 아껴. "
            "6. 이 노트를 참조하는 노트가 궁금하면 obsidian_get_backlinks를 써. "
            ""
            "[편집 전략] "
            "- 노트 일부 수정: obsidian_edit_note (정확한 텍스트 replace, 중복 시 오류). "
            "- 섹션 전체 교체: obsidian_replace_section (헤딩 지정). "
            "- 프론트매터 수정: obsidian_update_frontmatter (tags·status·aliases 등). "
            "- 전체 재작성: obsidian_write_note. "
            "- 이름/위치 변경: obsidian_move_note (update_links=true로 wikilink 자동 업데이트). "
            ""
            "Vault에 없는 정보면 솔직히 말하고, 새로 작성이 필요하면 사용자와 내용을 먼저 협의해. "
            "편집 전에 현재 내용을 읽어 맥락을 파악하고, 중요 변경 전에는 ask_user로 확인해. "
            "[노트 작성 기준] 새 노트 생성 시 'agent/guides/🤖 Agent 노트작성 가이드.md'를 참조해. "
            "frontmatter(tags/Categories/Indexes), 파일명 형식, 태그 규칙을 이 가이드에 따라 적용해라. "
            "[Templater] 업무·회의 노트는 obsidian_list_commands로 Templater 명령을 확인하고 "
            "obsidian_run_command로 실행해 템플릿 구조를 그대로 사용해라."
        ) + _AUTO_EXEC,
    },
    "unscript": {
        "label": "Unscript 테스트",
        "icon": "🤖",
        "description": (
            "Unscript 테스트 에이전트입니다.\n"
            "테스트 계획 수립, 케이스 작성, 실행 결과 분석을 도와드립니다.\n\n"
            "워크플로우: 화면 확인(OCR) → 케이스 설계\n"
            "→ 자동화 실행 → 결과 비교 → 버그 리포트"
        ),
        "system_prompt": (
            "너는 Unscript 테스트 에이전트야. "
            "업무 자동화 스크립트의 테스트 계획 수립, 테스트 케이스 작성, 실행 결과 분석을 담당해. "
            "테스트 시나리오를 체계적으로 관리하고 버그를 명확히 문서화해. "
            "화면 OCR(capture_screen_ocr)과 compare_screenshots로 UI 동작을 검증해. "
            "작업 시작 시 workflow_init으로 테스트 절차를 정의해라."
        ) + _AUTO_EXEC,
    },
    "knox": {
        "label": "Knox 자동 수집",
        "icon": "📥",
        "description": (
            "Knox 데이터 수집 에이전트입니다.\n"
            "Knox Chat, Knox Mail 등 사내 시스템에서 데이터를 수집하고 정리합니다.\n\n"
            "워크플로우: Knox 접속 확인 → 수집 대상 지정\n"
            "→ 데이터 수집 → 정리·중복 제거 → 결과 저장"
        ),
        "system_prompt": (
            "너는 Knox 데이터 수집 에이전트야. "
            "Knox Chat, Knox Mail 등 사내 시스템에서 필요한 데이터를 수집하고 정리하는 역할이야. "
            "수집 대상, 방법, 결과를 명확히 보고하고 수집 현황을 추적해. "
            "작업 시작 전 obsidian_search('Knox')로 Vault의 수집 명세·이전 결과를 참조해라. "
            "화면 캡처(capture_screen_ocr)와 브라우저 자동화를 활용해 데이터를 추출하고 정리해. "
            "작업 시작 시 workflow_init으로 수집 절차를 정의해라. "
            "수집 완료 후 정제된 데이터를 obsidian_write_note로 Vault에 저장해라."
        ) + _AUTO_EXEC,
    },
}

# ── 환경변수 로드 헬퍼 ────────────────────────────────────────

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


# ── 싱글턴 ───────────────────────────────────────────────────

_instance = None

def get_session_manager() -> "ObsidianSession":
    global _instance
    if _instance is None:
        _instance = ObsidianSession()
    return _instance


# ── 메인 클래스 ───────────────────────────────────────────────

class ObsidianSession:

    def __init__(self):
        vault_path = _env("OBSIDIAN_VAULT_PATH")
        self.agent_dir = Path(vault_path) / "agent" if vault_path else None
        self.api_base = _env("OBSIDIAN_HOST").rstrip("/")
        self.api_key  = _env("OBSIDIAN_API_KEY")
        self._ssl_ctx = ssl.create_default_context()
        self._ssl_ctx.check_hostname = False
        self._ssl_ctx.verify_mode = ssl.CERT_NONE
        self._ready = bool(vault_path)
        self._rest_ok: bool | None = None  # None=미확인, True=사용가능, False=불가

    # ── 초기화 ────────────────────────────────────────────────

    def setup_vault(self):
        """서버 시작 시 1회 호출 — 폴더 구조와 인덱스 파일을 생성한다."""
        if not self._ready:
            return

        files = {
            "agent/_index.md": self._tpl_index(),
            "agent/sessions/_index.md": self._tpl_sessions_index(),
            "agent/notes/_index.md": self._tpl_notes_index(),
            "agent/plans/backlog.md": self._tpl_backlog(),
        }
        for task_type, cfg in TASK_CONFIGS.items():
            desc = cfg.get("description", "")
            files[f"agent/threads/{task_type}/_index.md"] = (
                f"---\ntype: thread-index\ntask_type: {task_type}\n---\n\n"
                f"# {cfg['icon']} {cfg['label']} — 스레드 목록\n\n"
                f"{desc}\n\n"
                f"```dataview\nTABLE title, status, created\n"
                f"FROM \"agent/threads/{task_type}\"\n"
                f"WHERE thread_id\nSORT created DESC\n```\n"
            )
            files[f"agent/threads/_archive/{task_type}/_index.md"] = (
                f"---\ntype: thread-archive-index\ntask_type: {task_type}\n---\n\n"
                f"# {cfg['icon']} {cfg['label']} — 보관된 스레드\n\n"
                f"```dataview\nTABLE title, archived_at\n"
                f"FROM \"agent/threads/_archive/{task_type}\"\n"
                f"WHERE thread_id\nSORT archived_at DESC\n```\n"
            )
        for rel, content in files.items():
            try:
                # 이미 있으면 덮어쓰지 않는다
                existing = self._read(rel)
                if existing:
                    continue
            except Exception:
                pass
            try:
                self._write(rel, content)
            except Exception as e:
                print(f"[obsidian] 초기화 실패 {rel}: {e}")

        print("[obsidian] Vault 초기화 완료")

    # ── 세션 ──────────────────────────────────────────────────

    def new_session(self, task: str) -> str:
        """새 세션 노트를 생성하고 session_id를 반환한다."""
        if not self._ready:
            return ""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        time_str = now.strftime("%H:%M")
        session_id = self._next_session_id(date_str)
        slug = self._slug(task[:30])
        rel_path = f"agent/sessions/{date_str}-{session_id[-3:]}-{slug}.md"

        content = f"""---
session_id: {session_id}
date: {date_str}
time: {time_str}
type: session
status: in_progress
task: "{task[:80].replace('"', "'")}"
tools_used: []
duration_min: 0
tags: []
---

# 세션: {task[:60]}

## 요청
{task}

## 진행 내역

## 결과 요약

## 메모
"""
        try:
            self._write(rel_path, content)
        except Exception as e:
            print(f"[obsidian] 세션 생성 실패: {e}")
            return ""
        return session_id

    def log_tool(self, session_id: str, tool: str, result: str):
        """진행 내역에 툴 실행 결과를 추가한다."""
        if not self._ready or not session_id:
            return
        rel_path = self._session_path(session_id)
        if not rel_path:
            return
        try:
            content = self._read(rel_path)
            tool_label = f"- ✅ `{tool}`: {result[:120].strip()}\n"
            content = content.replace("## 진행 내역\n", f"## 진행 내역\n{tool_label}", 1)
            # frontmatter의 tools_used 업데이트
            content = re.sub(
                r"(tools_used: \[)(.*?)(\])",
                lambda m: m.group(1) + (m.group(2) + ", " if m.group(2) else "") + f'"{tool}"' + m.group(3),
                content,
            )
            self._write(rel_path, content)
        except Exception as e:
            print(f"[obsidian] 툴 로그 실패: {e}")

    def close_session(self, session_id: str, summary: str):
        """세션을 완료 상태로 닫고 결과 요약을 기록한다."""
        if not self._ready or not session_id:
            return
        rel_path = self._session_path(session_id)
        if not rel_path:
            return
        try:
            content = self._read(rel_path)
            content = content.replace("status: in_progress", "status: completed", 1)
            content = content.replace("## 결과 요약\n", f"## 결과 요약\n{summary[:500]}\n", 1)
            self._write(rel_path, content)
        except Exception as e:
            print(f"[obsidian] 세션 종료 실패: {e}")

    # ── 스레드 (업무별 대화 세션) ────────────────────────────────

    def new_thread(self, task_type: str, title: str = "") -> str:
        """새 업무 스레드를 생성하고 thread_id를 반환한다."""
        if not self._ready:
            return ""
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        thread_id = self._next_thread_id(task_type, date_str)
        config = TASK_CONFIGS.get(task_type, {})
        date_part = thread_id[:10]   # YYYY-MM-DD
        num_part  = thread_id[-3:]   # NNN
        display_title = title or f"{config.get('label', task_type)} {date_part} #{num_part}"
        system_prompt = config.get("system_prompt", "")
        initial_messages = [{"role": "system", "content": system_prompt}] if system_prompt else []
        meta = {
            "thread_id": thread_id,
            "task_type": task_type,
            "status": "in_progress",
            "created": now.isoformat(),
            "title": display_title,
        }
        content = self._build_thread_content(meta, initial_messages)
        rel_path = f"agent/threads/{task_type}/{thread_id}.md"
        try:
            self._write(rel_path, content)
        except Exception as e:
            print(f"[obsidian] 스레드 생성 실패: {e}")
            return ""
        return thread_id

    def get_thread_messages(self, task_type: str, thread_id: str) -> list:
        """LLM에 전달할 전체 messages 리스트를 반환한다 (system 포함)."""
        rel_path = f"agent/threads/{task_type}/{thread_id}.md"
        try:
            content = self._read(rel_path)
            return self._parse_thread_messages(content)
        except Exception as e:
            print(f"[obsidian] 스레드 메시지 로드 실패: {e}")
            config = TASK_CONFIGS.get(task_type, {})
            sp = config.get("system_prompt", "")
            return [{"role": "system", "content": sp}] if sp else []

    def save_thread_messages(self, task_type: str, thread_id: str, messages: list):
        """스레드의 전체 messages 리스트를 저장한다."""
        rel_path = f"agent/threads/{task_type}/{thread_id}.md"
        try:
            existing = self._read(rel_path)
            meta = self._parse_thread_meta(existing)
            content = self._build_thread_content(meta, messages)
            self._write(rel_path, content)
        except Exception as e:
            print(f"[obsidian] 스레드 저장 실패: {e}")

    def get_thread_display_messages(self, task_type: str, thread_id: str) -> list:
        """채팅창 표시용 메시지만 반환 (system/tool 제외)."""
        messages = self.get_thread_messages(task_type, thread_id)
        result = []
        for m in messages:
            role = m.get("role", "")
            content = m.get("content", "")
            if role == "user" and content:
                result.append({"role": "user", "content": content})
            elif role == "assistant" and content:
                result.append({"role": "assistant", "content": content})
        return result

    def list_threads(self, task_type: str) -> list:
        """특정 업무 타입의 스레드 목록을 반환한다."""
        rel_dir = f"agent/threads/{task_type}"
        try:
            files = self._list_dir(rel_dir)
            threads = []
            for f in sorted(
                [f for f in files if f.endswith(".md") and f != "_index.md"],
                reverse=True
            ):
                rel_path = f"{rel_dir}/{f}"
                try:
                    content = self._read(rel_path)
                    meta = self._parse_thread_meta(content)
                    msgs = self._parse_thread_messages(content)
                    msg_count = sum(1 for m in msgs if m.get("role") in ("user", "assistant"))
                    meta["message_count"] = msg_count
                    threads.append(meta)
                except Exception:
                    threads.append({"thread_id": f.replace(".md", ""), "status": "unknown",
                                    "title": f, "message_count": 0, "created": ""})
            return threads
        except Exception as e:
            print(f"[obsidian] 스레드 목록 조회 실패: {e}")
            return []

    def close_thread(self, task_type: str, thread_id: str):
        """스레드를 completed 상태로 변경한다."""
        rel_path = f"agent/threads/{task_type}/{thread_id}.md"
        try:
            content = self._read(rel_path)
            content = content.replace("status: in_progress", "status: completed", 1)
            self._write(rel_path, content)
        except Exception as e:
            print(f"[obsidian] 스레드 완료 처리 실패: {e}")

    def archive_thread(self, task_type: str, thread_id: str):
        """스레드를 _archive 폴더로 이동한다 (실제 삭제 아님)."""
        src_path = f"agent/threads/{task_type}/{thread_id}.md"
        dst_path = f"agent/threads/_archive/{task_type}/{thread_id}.md"
        try:
            content = self._read(src_path)
            if not content:
                print(f"[obsidian] 보관 실패: 파일 없음 {src_path}")
                return
            now = datetime.now().isoformat(timespec="seconds")
            # 복원 시 원래 상태로 돌아갈 수 있도록 보관 전 status 저장
            pre_match = re.search(r"^status: (\S+)$", content, re.MULTILINE)
            pre_status = pre_match.group(1) if pre_match else "in_progress"
            content = re.sub(r"(status: )\S+", r"\1archived", content, count=1)
            content = content.replace(
                "status: archived\n",
                f"status: archived\narchived_at: {now}\npre_archive_status: {pre_status}\n",
                1
            )
            self._write(dst_path, content)
            self._delete(src_path)
        except Exception as e:
            print(f"[obsidian] 스레드 보관 실패: {e}")

    def list_archived_threads(self, task_type: str) -> list:
        """보관된 스레드 목록을 반환한다."""
        rel_dir = f"agent/threads/_archive/{task_type}"
        try:
            files = self._list_dir(rel_dir)
            threads = []
            for f in sorted(
                [f for f in files if f.endswith(".md") and f != "_index.md"],
                reverse=True
            ):
                rel_path = f"{rel_dir}/{f}"
                try:
                    content = self._read(rel_path)
                    meta = self._parse_thread_meta(content)
                    m = re.search(r"^archived_at: (.+)$", content, re.MULTILINE)
                    meta["archived_at"] = m.group(1).strip() if m else ""
                    msgs = self._parse_thread_messages(content)
                    msg_count = sum(1 for msg in msgs if msg.get("role") in ("user", "assistant"))
                    meta["message_count"] = msg_count
                    threads.append(meta)
                except Exception:
                    threads.append({
                        "thread_id": f.replace(".md", ""), "status": "archived",
                        "title": f, "message_count": 0, "created": "", "archived_at": ""
                    })
            return threads
        except Exception as e:
            print(f"[obsidian] 보관 스레드 목록 조회 실패: {e}")
            return []

    def list_all_threads(self) -> dict:
        """모든 업무 타입의 활성·완료·보관 스레드를 묶어 반환한다."""
        result = {}
        for task_type in TASK_CONFIGS:
            active = self.list_threads(task_type)
            archived = self.list_archived_threads(task_type)
            for t in active:
                t["is_archived"] = False
            for t in archived:
                t["is_archived"] = True
            all_threads = active + archived
            if all_threads:
                result[task_type] = all_threads
        return result

    def delete_thread_permanent(self, task_type: str, thread_id: str, archived: bool = False) -> None:
        """스레드 .md 파일을 영구 삭제한다."""
        if archived:
            rel_path = f"agent/threads/_archive/{task_type}/{thread_id}.md"
        else:
            rel_path = f"agent/threads/{task_type}/{thread_id}.md"
        self._delete(rel_path)

    def restore_thread(self, task_type: str, thread_id: str) -> None:
        """완료된 스레드를 진행 중 상태로 복원한다."""
        rel_path = f"agent/threads/{task_type}/{thread_id}.md"
        try:
            content = self._read(rel_path)
            content = re.sub(r"(status: )\S+", r"\1in_progress", content, count=1)
            self._write(rel_path, content)
        except Exception as e:
            print(f"[obsidian] 스레드 복원 실패: {e}")

    def restore_archived_thread(self, task_type: str, thread_id: str) -> None:
        """보관된 스레드를 보관 전 상태(pre_archive_status)로 활성 폴더에 복원한다."""
        src_path = f"agent/threads/_archive/{task_type}/{thread_id}.md"
        dst_path = f"agent/threads/{task_type}/{thread_id}.md"
        try:
            content = self._read(src_path)
            if not content:
                print(f"[obsidian] 보관 복원 실패: 파일 없음 {src_path}")
                return
            # 저장해둔 보관 전 status로 복원 (없으면 in_progress로 fallback)
            pre_match = re.search(r"^pre_archive_status: (\S+)$", content, re.MULTILINE)
            restore_status = pre_match.group(1) if pre_match else "in_progress"
            content = re.sub(r"(status: )\S+", r"\1" + restore_status, content, count=1)
            content = re.sub(r"^archived_at: .+\n", "", content, flags=re.MULTILINE)
            content = re.sub(r"^pre_archive_status: .+\n", "", content, flags=re.MULTILINE)
            self._write(dst_path, content)
            self._delete(src_path)
        except Exception as e:
            print(f"[obsidian] 보관 스레드 복원 실패: {e}")

    def get_thread_display_messages_archived(self, task_type: str, thread_id: str) -> list:
        """보관된 스레드의 채팅창 표시용 메시지를 반환한다."""
        rel_path = f"agent/threads/_archive/{task_type}/{thread_id}.md"
        try:
            content = self._read(rel_path)
            messages = self._parse_thread_messages(content)
            result = []
            for msg in messages:
                role = msg.get("role", "")
                text = msg.get("content", "")
                if role == "user" and text:
                    result.append({"role": "user", "content": text})
                elif role == "assistant" and text:
                    result.append({"role": "assistant", "content": text})
            return result
        except Exception as e:
            print(f"[obsidian] 보관 스레드 메시지 로드 실패: {e}")
            return []

    # ── 스레드 내부 헬퍼 ─────────────────────────────────────

    def _build_thread_content(self, meta: dict, messages: list) -> str:
        task_type = meta.get("task_type", "")
        title = meta.get("title", task_type)
        lines = []
        for m in messages:
            role = m.get("role", "")
            if role == "system":
                continue
            elif role == "user" and m.get("content"):
                lines.append(f"**사용자**  \n{m['content']}\n")
            elif role == "assistant":
                text = m.get("content", "")
                if text:
                    lines.append(f"**에이전트**  \n{text}\n")
                elif m.get("tool_calls"):
                    names = ", ".join(tc["function"]["name"] for tc in m["tool_calls"])
                    lines.append(f"**에이전트** *(🔧 {names})*\n")
            elif role == "tool" and m.get("content"):
                preview = str(m["content"])[:100]
                lines.append(f"*✅ {preview}*\n")
        readable = "\n---\n\n".join(lines) if lines else "*(대화 없음)*"
        messages_json = json.dumps(messages, ensure_ascii=False, indent=2)
        return (
            f"---\n"
            f"thread_id: {meta['thread_id']}\n"
            f"task_type: {task_type}\n"
            f"status: {meta.get('status', 'in_progress')}\n"
            f"created: {meta.get('created', datetime.now().isoformat())}\n"
            f"title: \"{title}\"\n"
            f"---\n\n"
            f"# {title}\n\n"
            f"{readable}\n\n"
            f"---\n\n"
            f"```agent-messages\n{messages_json}\n```\n"
        )

    def _parse_thread_messages(self, content: str) -> list:
        match = re.search(r"```agent-messages\n(.*?)\n```", content, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        return []

    def _parse_thread_meta(self, content: str) -> dict:
        meta = {}
        for key in ("thread_id", "task_type", "status", "created"):
            m = re.search(rf"^{key}: (\S+)", content, re.MULTILINE)
            meta[key] = m.group(1) if m else ""
        m = re.search(r'^title: "(.*?)"', content, re.MULTILINE)
        meta["title"] = m.group(1) if m else ""
        return meta

    def _next_thread_id(self, task_type: str, date_str: str) -> str:
        try:
            files = self._list_dir(f"agent/threads/{task_type}")
            count = sum(1 for f in files if f.startswith(date_str) and f.endswith(".md"))
        except Exception:
            count = 0
        return f"{date_str}-{count + 1:03d}"

    # ── 개발 노트 ─────────────────────────────────────────────

    def add_note(self, title: str, content: str,
                 tags: list = None, related_session: str = "") -> str:
        """개발 노트를 생성하고 경로를 반환한다."""
        if not self._ready:
            return "Obsidian 미설정"
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        slug = self._slug(title[:40])
        rel_path = f"agent/notes/{date_str}-{slug}.md"
        tags_yaml = "\n".join(f"  - {t}" for t in (tags or []))
        note = f"""---
date: {date_str}
type: dev-note
related_session: "{related_session}"
tags:
{tags_yaml if tags_yaml else "  []"}
---

# {title}

{content}
"""
        try:
            self._write(rel_path, note)
            return f"노트 저장: {rel_path}"
        except Exception as e:
            return f"노트 저장 실패: {e}"

    # ── 계획/백로그 ───────────────────────────────────────────

    def add_plan_item(self, title: str, description: str = "") -> str:
        """backlog.md의 '## 예정' 섹션에 항목을 추가한다."""
        if not self._ready:
            return "Obsidian 미설정"
        rel_path = "agent/plans/backlog.md"
        try:
            content = self._read(rel_path) or self._tpl_backlog()
            item = f"- [ ] {title}" + (f" — {description}" if description else "") + "\n"
            content = content.replace("## 예정\n", f"## 예정\n{item}", 1)
            now = datetime.now().strftime("%Y-%m-%d")
            content = re.sub(r"updated: .*", f"updated: {now}", content)
            self._write(rel_path, content)
            return f"백로그에 추가: {title}"
        except Exception as e:
            return f"백로그 추가 실패: {e}"

    # ── 조회 ──────────────────────────────────────────────────

    def list_recent_sessions(self, limit: int = 5) -> str:
        """최근 세션 목록을 문자열로 반환한다."""
        if not self._ready:
            return "Obsidian 미설정"
        try:
            files = self._list_dir("agent/sessions")
            sessions = sorted(
                [f for f in files if f.endswith(".md") and not f.endswith("_index.md")],
                reverse=True
            )[:limit]
            if not sessions:
                return "저장된 세션이 없습니다."
            lines = []
            for f in sessions:
                rel = f"agent/sessions/{f}"
                try:
                    raw = self._read(rel)
                    task_m = re.search(r'task: "(.*?)"', raw)
                    status_m = re.search(r'status: (\w+)', raw)
                    task = task_m.group(1) if task_m else f
                    status = status_m.group(1) if status_m else "?"
                    lines.append(f"- [{f.replace('.md','')}] {task} ({status})")
                except Exception:
                    lines.append(f"- {f}")
            return "\n".join(lines)
        except Exception as e:
            return f"세션 조회 실패: {e}"

    def search_sessions(self, query: str) -> str:
        """세션 내용을 키워드로 검색한다."""
        if not self._ready:
            return "Obsidian 미설정"
        query_lower = query.lower()
        try:
            files = self._list_dir("agent/sessions")
            sessions = [f for f in files if f.endswith(".md") and not f.endswith("_index.md")]
            results = []
            for f in sorted(sessions, reverse=True):
                rel = f"agent/sessions/{f}"
                try:
                    raw = self._read(rel)
                    if query_lower in raw.lower():
                        task_m = re.search(r'task: "(.*?)"', raw)
                        task = task_m.group(1) if task_m else f
                        results.append(f"- [{f.replace('.md','')}] {task}")
                except Exception:
                    pass
            if not results:
                return f'"{query}" 검색 결과 없음'
            return f'"{query}" 검색 결과:\n' + "\n".join(results)
        except Exception as e:
            return f"검색 실패: {e}"

    # ── REST API / 파일 I/O ───────────────────────────────────

    def _write(self, vault_rel: str, content: str):
        if self.api_base and self.api_key and self._rest_ok is not False:
            url = self.api_base + "/vault/" + urllib.parse.quote(vault_rel, safe="/")
            data = content.encode("utf-8")
            req = urllib.request.Request(
                url, data=data, method="PUT",
                headers={"Authorization": self.api_key,
                         "Content-Type": "text/markdown; charset=utf-8"}
            )
            try:
                with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=5):
                    self._rest_ok = True
                    return
            except Exception as e:
                if self._rest_ok is None:
                    # 첫 실패에만 경고 1회 출력
                    print(f"[obsidian] REST API 연결 실패 — 파일 직접 쓰기로 전환합니다. ({e})")
                self._rest_ok = False

        # fallback: 직접 파일 쓰기
        if self.agent_dir:
            # vault_rel은 'agent/...' 형식이므로 agent_dir의 부모(vault root)에서 경로 구성
            path = self.agent_dir.parent / vault_rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def _read(self, vault_rel: str) -> str:
        if self.api_base and self.api_key and self._rest_ok is not False:
            url = self.api_base + "/vault/" + urllib.parse.quote(vault_rel, safe="/")
            req = urllib.request.Request(
                url, headers={"Authorization": self.api_key}
            )
            try:
                with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=5) as r:
                    self._rest_ok = True
                    return r.read().decode("utf-8")
            except urllib.error.HTTPError as e:
                if e.code == 404:
                    return ""
                raise
            except Exception:
                self._rest_ok = False

        if self.agent_dir:
            path = self.agent_dir.parent / vault_rel
            if path.exists():
                return path.read_text(encoding="utf-8")
        return ""

    def _delete(self, vault_rel: str):
        """파일을 삭제한다."""
        if self.api_base and self.api_key:
            url = self.api_base + "/vault/" + urllib.parse.quote(vault_rel, safe="/")
            req = urllib.request.Request(
                url, method="DELETE",
                headers={"Authorization": self.api_key}
            )
            try:
                with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=5):
                    return
            except Exception as e:
                print(f"[obsidian] REST 삭제 실패({vault_rel}), fallback: {e}")
        if self.agent_dir:
            path = self.agent_dir.parent / vault_rel
            if path.exists():
                path.unlink()

    def _list_dir(self, vault_rel_dir: str) -> list:
        if self.api_base and self.api_key:
            url = self.api_base + "/vault/" + urllib.parse.quote(vault_rel_dir, safe="/") + "/"
            req = urllib.request.Request(
                url, headers={"Authorization": self.api_key}
            )
            try:
                with urllib.request.urlopen(req, context=self._ssl_ctx, timeout=5) as r:
                    data = json.loads(r.read().decode("utf-8"))
                    return [f.rstrip("/") for f in data.get("files", [])]
            except Exception as e:
                print(f"[obsidian] 디렉터리 조회 실패: {e}")

        if self.agent_dir:
            path = self.agent_dir.parent / vault_rel_dir
            if path.exists():
                return [p.name for p in path.iterdir()]
        return []

    # ── 유틸 ──────────────────────────────────────────────────

    def _slug(self, text: str) -> str:
        text = re.sub(r"[^\w가-힣\s-]", "", text)
        text = re.sub(r"\s+", "-", text.strip())
        return text[:40].lower() or "session"

    def _next_session_id(self, date_str: str) -> str:
        try:
            files = self._list_dir("agent/sessions")
            count = sum(1 for f in files if f.startswith(date_str) and f.endswith(".md"))
        except Exception:
            count = 0
        return f"{date_str}-{count + 1:03d}"

    def _session_path(self, session_id: str) -> str:
        """session_id로 실제 파일 경로를 찾는다."""
        date_part = session_id[:10]  # YYYY-MM-DD
        num_part = session_id[-3:]   # NNN
        try:
            files = self._list_dir("agent/sessions")
            for f in files:
                if f.startswith(f"{date_part}-{num_part}-"):
                    return f"agent/sessions/{f}"
        except Exception:
            pass
        return ""

    # ── 템플릿 ────────────────────────────────────────────────

    def _tpl_index(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return f"""---
created: {today}
type: index
---

# MES Agent — 업무 기록

에이전트와의 업무 세션, 개발 노트, 계획을 관리하는 공간입니다.

## 폴더 구조

| 폴더 | 설명 |
|------|------|
| [[sessions/_index\\|sessions/]] | 에이전트 대화 세션 자동 로그 |
| [[notes/_index\\|notes/]] | 개발 노트, 인사이트 |
| [[plans/backlog\\|plans/]] | 할 일 목록 및 계획 |

## 사용 방법

- **세션 자동 저장**: 채팅창에서 대화하면 `sessions/`에 자동 기록됩니다.
- **개발 노트 추가**: 채팅에서 "개발 노트 추가해줘: [내용]"이라고 말하세요.
- **백로그 추가**: "백로그에 추가해줘: [할 일]"이라고 말하세요.
- **세션 검색**: "최근 세션 보여줘" 또는 "XXX 관련 세션 찾아줘"
"""

    def _tpl_sessions_index(self) -> str:
        return """---
type: index
---

# 세션 목록

```dataview
TABLE task, status, date, tools_used
FROM "agent/sessions"
WHERE type = "session"
SORT date DESC
LIMIT 20
```
"""

    def _tpl_notes_index(self) -> str:
        return """---
type: index
---

# 개발 노트

```dataview
TABLE date, tags, related_session
FROM "agent/notes"
WHERE type = "dev-note"
SORT date DESC
```
"""

    def _tpl_backlog(self) -> str:
        today = datetime.now().strftime("%Y-%m-%d")
        return f"""---
type: backlog
updated: {today}
---

# 개발 백로그

## 진행 중

## 예정

## 완료
"""


MANIFEST = [
    {
        "name": "add_dev_note",
        "label": "개발 노트 저장",
        "schema": {
            "type": "function",
            "function": {
                "name": "add_dev_note",
                "description": "Obsidian Vault에 개발 노트를 저장합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "content": {"type": "string"},
                        "tags": {"type": "array", "items": {"type": "string"}},
                        "related_session": {"type": "string"}
                    },
                    "required": ["title", "content"]
                }
            }
        },
        "handler": lambda a: get_session_manager().add_note(
            a["title"], a["content"], a.get("tags", []), a.get("related_session", "")
        )
    },
    {
        "name": "add_plan_item",
        "label": "백로그 항목 추가",
        "schema": {
            "type": "function",
            "function": {
                "name": "add_plan_item",
                "description": "Obsidian 백로그에 할 일 항목을 추가합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": ["title"]
                }
            }
        },
        "handler": lambda a: get_session_manager().add_plan_item(
            a["title"], a.get("description", "")
        )
    },
    {
        "name": "list_recent_sessions",
        "label": "최근 세션 조회",
        "schema": {
            "type": "function",
            "function": {
                "name": "list_recent_sessions",
                "description": "최근 업무 세션 목록을 반환합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer"}
                    }
                }
            }
        },
        "handler": lambda a: get_session_manager().list_recent_sessions(a.get("limit", 5))
    },
    {
        "name": "search_sessions",
        "label": "세션 검색",
        "schema": {
            "type": "function",
            "function": {
                "name": "search_sessions",
                "description": "Obsidian 세션 내용을 키워드로 검색합니다.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string"}},
                    "required": ["query"]
                }
            }
        },
        "handler": lambda a: get_session_manager().search_sessions(a["query"])
    },
]
