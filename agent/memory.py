"""대화 간 장기기억 (Long-Term Memory).

스레드를 넘는 영속 기억 저장소. 과거 대화에서 추출한 핵심 사실·선호·결정을
Obsidian Vault 노트(`<vault>/agent/memory/long_term.md`)에 저장하고, 새 대화 시작 시
키워드 검색으로 관련 기억을 꺼내 system 프롬프트에 주입한다.

순수 파일 I/O(stdlib)라 의존성·LLM 없이 단위 테스트 가능. 사용자는 노트를 직접 열어
보고 편집할 수 있다.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

_MAX_MEMORIES = 200
_REL_PATH = ("agent", "memory", "long_term.md")
_FRONTMATTER = "---\ntype: agent-memory\n---\n\n# 에이전트 장기 기억\n\n"
# - [YYYY-MM-DD] (category) 텍스트 <!-- id:xxxx src:yyyy -->
_LINE_RE = re.compile(
    r"^- \[(?P<created>[^\]]*)\] \((?P<category>[^)]*)\) (?P<text>.*?)\s*<!-- id:(?P<id>\S+) src:(?P<src>\S*) -->\s*$"
)
_TOKEN_RE = re.compile(r"[0-9A-Za-z가-힣]+")


@dataclass
class Memory:
    id: str
    text: str
    category: str = "fact"
    created: str = ""
    source: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id, "text": self.text, "category": self.category,
            "created": self.created, "source": self.source,
        }

    def to_line(self) -> str:
        return (f"- [{self.created}] ({self.category}) {self.text} "
                f"<!-- id:{self.id} src:{self.source} -->")


def _normalize(text: str) -> str:
    return " ".join(text.lower().split())


def _tokens(text: str) -> set[str]:
    return {t for t in _TOKEN_RE.findall(text.lower()) if len(t) > 1}


class MemoryStore:
    def __init__(self, base_dir: str | Path):
        self.path = Path(base_dir).joinpath(*_REL_PATH)

    # ── 영속 ──────────────────────────────────────────────────
    def all(self) -> list[Memory]:
        if not self.path.exists():
            return []
        out: list[Memory] = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            m = _LINE_RE.match(line.strip())
            if m:
                out.append(Memory(
                    id=m.group("id"), text=m.group("text").strip(),
                    category=m.group("category"), created=m.group("created"),
                    source=m.group("src"),
                ))
        return out

    def _save(self, mems: list[Memory]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        body = "\n".join(m.to_line() for m in mems)
        self.path.write_text(_FRONTMATTER + body + ("\n" if body else ""), encoding="utf-8")

    # ── 변경 ──────────────────────────────────────────────────
    def add(self, text: str, category: str = "fact", source: str = "") -> Memory | None:
        text = (text or "").strip()
        if not text:
            return None
        mems = self.all()
        norm = _normalize(text)
        # dedup: 정규화 텍스트가 기존과 동일하거나 서로 포함하면 skip
        for existing in mems:
            en = _normalize(existing.text)
            if norm == en or norm in en or en in norm:
                return None
        mem = Memory(
            id=uuid.uuid4().hex[:8], text=text, category=category or "fact",
            created=datetime.now().strftime("%Y-%m-%d"), source=source,
        )
        mems.append(mem)
        if len(mems) > _MAX_MEMORIES:
            mems = mems[-_MAX_MEMORIES:]
        self._save(mems)
        return mem

    def delete(self, mem_id: str) -> bool:
        mems = self.all()
        kept = [m for m in mems if m.id != mem_id]
        if len(kept) == len(mems):
            return False
        self._save(kept)
        return True

    # ── 검색 ──────────────────────────────────────────────────
    def search(self, query: str, k: int = 5) -> list[Memory]:
        q = _tokens(query or "")
        if not q:
            return []
        scored: list[tuple[int, Memory]] = []
        for mem in self.all():
            score = len(q & _tokens(mem.text))
            if score > 0:
                scored.append((score, mem))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [m for _, m in scored[:k]]
