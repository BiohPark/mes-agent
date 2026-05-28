"""
Obsidian RAG 도구 — Vault 전체 검색 및 노트 읽기/쓰기
- 1순위: Obsidian Local REST API (OBSIDIAN_HOST + OBSIDIAN_API_KEY)
- fallback: OBSIDIAN_VAULT_PATH 직접 파일 접근 (검색·읽기만)
"""

import os
import re
import ssl
import json
import urllib.request
import urllib.parse
import urllib.error
from pathlib import Path


# ── 공통 유틸 ─────────────────────────────────────────────────

def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


def _ssl_ctx() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _api_base() -> str:
    return _env("OBSIDIAN_HOST").rstrip("/")


def _api_key() -> str:
    return _env("OBSIDIAN_API_KEY")


def _vault() -> Path | None:
    p = _env("OBSIDIAN_VAULT_PATH")
    return Path(p) if p else None


def _api_request(method: str, path: str, body: bytes = None,
                 content_type: str = "text/markdown; charset=utf-8") -> str | None:
    """REST API 호출. 성공 시 응답 body 문자열, 실패 시 None."""
    base, key = _api_base(), _api_key()
    if not base or not key:
        return None
    headers = {"Authorization": key}
    if body is not None:
        headers["Content-Type"] = content_type
    req = urllib.request.Request(
        base + path, data=body, method=method, headers=headers
    )
    try:
        with urllib.request.urlopen(req, context=_ssl_ctx(), timeout=8) as r:
            return r.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return ""
        return None
    except Exception:
        return None


def _vault_read(rel_path: str) -> str | None:
    """Vault 파일 직접 읽기 (fallback)."""
    vault = _vault()
    if not vault:
        return None
    p = vault / rel_path
    if p.exists():
        return p.read_text(encoding="utf-8", errors="ignore")
    return None


def _parse_frontmatter(content: str) -> dict:
    """YAML 프론트매터를 간단히 파싱한다."""
    if not content.startswith("---"):
        return {}
    end = content.find("\n---", 3)
    if end == -1:
        return {}
    fm = {}
    for line in content[3:end].splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip()
    return fm


def _extract_wikilinks(content: str) -> list[str]:
    """[[링크]], [[링크|별칭]], [[링크#섹션]] 에서 타깃 제목만 추출. 코드블록 제외."""
    body = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    body = re.sub(r"`[^`]+`", "", body)
    raw = re.findall(r"\[\[([^\]]+)\]\]", body)
    seen, result = set(), []
    for m in raw:
        title = m.split("|")[0].split("#")[0].strip()
        if title and title not in seen:
            seen.add(title)
            result.append(title)
    return result


def _resolve_wikilink(title: str) -> tuple[str | None, str | None]:
    """wikilink 제목 → (vault 상대 경로, 내용). 없으면 (None, None)."""
    # 1) REST API — 루트에 동일 이름 파일
    enc = urllib.parse.quote(f"{title}.md", safe="/")
    raw = _api_request("GET", f"/vault/{enc}")
    if raw:
        return (f"{title}.md", raw)

    # 2) REST API — 검색 후 stem 매칭
    sraw = _api_request("POST", f"/search/simple/?query={urllib.parse.quote(title)}")
    if sraw:
        try:
            results = json.loads(sraw)
            # stem 이름이 정확히 일치하는 것 우선
            for r in results[:10]:
                fname = r.get("filename", "")
                if Path(fname).stem.lower() == title.lower():
                    content = _api_request("GET", f"/vault/{urllib.parse.quote(fname, safe='/')}")
                    if content:
                        return (fname, content)
            # 없으면 첫 번째 결과
            if results:
                fname = results[0].get("filename", "")
                content = _api_request("GET", f"/vault/{urllib.parse.quote(fname, safe='/')}")
                if content:
                    return (fname, content)
        except Exception:
            pass

    # 3) 직접 파일 스캔 (fallback)
    vault = _vault()
    if not vault:
        return (None, None)
    for md in vault.rglob("*.md"):
        if md.stem.lower() == title.lower():
            rel = str(md.relative_to(vault)).replace("\\", "/")
            try:
                return (rel, md.read_text(encoding="utf-8", errors="ignore"))
            except Exception:
                return (rel, None)
    return (None, None)


# ── 툴 함수 ───────────────────────────────────────────────────

def obsidian_search(query: str, limit: int = 20) -> str:
    """Obsidian Vault 전체에서 키워드를 검색한다."""
    encoded = urllib.parse.quote(query)
    raw = _api_request("POST", f"/search/simple/?query={encoded}")

    if raw is not None:
        try:
            data = json.loads(raw) if raw else []
            items = []
            for r in data[:limit]:
                matches = r.get("matches", [])
                snippet = ""
                if matches:
                    c = matches[0].get("context", "")
                    snippet = c[:200] if isinstance(c, str) else ""
                items.append({
                    "path":    r.get("filename", ""),
                    "score":   round(float(r.get("score", 0)), 3),
                    "snippet": snippet,
                })
            return json.dumps(
                {"query": query, "count": len(data), "results": items},
                ensure_ascii=False
            )
        except Exception:
            pass  # REST 파싱 실패 시 fallback

    # Fallback: 파일 직접 스캔
    vault = _vault()
    if not vault or not vault.exists():
        return json.dumps({"error": "Obsidian 미설정 — OBSIDIAN_HOST 또는 OBSIDIAN_VAULT_PATH 필요"})

    q = query.lower()
    results = []
    for md in sorted(vault.rglob("*.md"), key=lambda f: f.stat().st_mtime, reverse=True):
        if len(results) >= limit:
            break
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
            if q in text.lower():
                idx = text.lower().find(q)
                snippet = text[max(0, idx - 50): idx + 150].strip()
                results.append({
                    "path":    str(md.relative_to(vault)).replace("\\", "/"),
                    "snippet": snippet,
                })
        except Exception:
            continue

    return json.dumps(
        {"query": query, "count": len(results), "results": results, "method": "file_scan"},
        ensure_ascii=False
    )


def obsidian_read_note(path: str) -> str:
    """Vault 경로로 노트 내용을 읽는다. 예: 'projects/Syncade.md'"""
    encoded = urllib.parse.quote(path, safe="/")
    raw = _api_request("GET", f"/vault/{encoded}")

    if raw is not None:
        if raw == "":
            return json.dumps({"error": f"노트를 찾을 수 없습니다: {path}"})
        return json.dumps({"path": path, "content": raw, "length": len(raw)}, ensure_ascii=False)

    # Fallback
    content = _vault_read(path)
    if content is None:
        return json.dumps({"error": "Obsidian 미설정 또는 파일 없음"})
    if content == "":
        return json.dumps({"error": f"노트를 찾을 수 없습니다: {path}"})
    return json.dumps({"path": path, "content": content, "length": len(content)}, ensure_ascii=False)


def obsidian_list_notes(folder: str = "", limit: int = 50) -> str:
    """Vault 폴더의 노트 목록을 반환한다. folder 생략 시 루트."""
    encoded = urllib.parse.quote(folder, safe="/")
    api_path = f"/vault/{encoded}/" if folder else "/vault/"
    raw = _api_request("GET", api_path)

    if raw is not None:
        try:
            data = json.loads(raw) if raw else {}
            files = data.get("files", [])
            notes = [f for f in files if not f.endswith("/")][:limit]
            dirs  = [f.rstrip("/") for f in files if f.endswith("/")]
            return json.dumps(
                {"folder": folder or "/", "notes": notes, "subfolders": dirs, "count": len(notes)},
                ensure_ascii=False
            )
        except Exception:
            pass

    # Fallback
    vault = _vault()
    if not vault:
        return json.dumps({"error": "Obsidian 미설정"})
    target = vault / folder if folder else vault
    if not target.exists():
        return json.dumps({"error": f"폴더 없음: {folder}"})

    notes = [str(p.relative_to(vault)).replace("\\", "/")
             for p in sorted(target.glob("*.md"))[:limit]]
    dirs  = [str(p.relative_to(vault)).replace("\\", "/")
             for p in sorted(target.iterdir()) if p.is_dir()]
    return json.dumps(
        {"folder": folder or "/", "notes": notes, "subfolders": dirs, "count": len(notes)},
        ensure_ascii=False
    )


def obsidian_write_note(path: str, content: str) -> str:
    """Vault에 노트를 생성하거나 덮어쓴다. 예: 'projects/Syncade.md'"""
    encoded = urllib.parse.quote(path, safe="/")
    raw = _api_request("PUT", f"/vault/{encoded}", body=content.encode("utf-8"))

    if raw is not None:
        return json.dumps({"path": path, "written": True, "size": len(content)}, ensure_ascii=False)

    # Fallback: 직접 파일 쓰기
    vault = _vault()
    if not vault:
        return json.dumps({"error": "Obsidian 미설정"})
    p = vault / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")
    return json.dumps({"path": path, "written": True, "size": len(content), "method": "file"}, ensure_ascii=False)


def obsidian_append_note(path: str, content: str) -> str:
    """기존 노트 끝에 내용을 추가한다. 노트가 없으면 새로 생성한다."""
    encoded = urllib.parse.quote(path, safe="/")
    raw = _api_request("POST", f"/vault/{encoded}", body=content.encode("utf-8"))

    if raw is not None:
        return json.dumps({"path": path, "appended": True, "added_size": len(content)}, ensure_ascii=False)

    # Fallback: 직접 파일 추가
    vault = _vault()
    if not vault:
        return json.dumps({"error": "Obsidian 미설정"})
    p = vault / path
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("a", encoding="utf-8") as f:
        f.write("\n" + content)
    return json.dumps({"path": path, "appended": True, "added_size": len(content), "method": "file"}, ensure_ascii=False)


def obsidian_get_tags(path: str) -> str:
    """노트의 프론트매터 태그와 인라인 태그(#tag)를 반환한다."""
    result = json.loads(obsidian_read_note(path))
    if "error" in result:
        return json.dumps(result)

    content = result["content"]
    fm = _parse_frontmatter(content)

    # 프론트매터 tags
    fm_tags_raw = fm.get("tags", "")
    if fm_tags_raw.startswith("["):
        fm_tags = [t.strip(" '\"[]") for t in fm_tags_raw.strip("[]").split(",")]
    else:
        fm_tags = [t.strip() for t in fm_tags_raw.split(",") if t.strip()]

    # 인라인 #태그 (코드블록 제외)
    body = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
    inline_tags = re.findall(r"(?<!\w)#([\w가-힣/-]+)", body)

    all_tags = sorted(set(fm_tags + inline_tags) - {""})
    return json.dumps(
        {"path": path, "frontmatter_tags": fm_tags, "inline_tags": inline_tags, "all_tags": all_tags},
        ensure_ascii=False
    )


def obsidian_follow_links(path: str, depth: int = 1, max_notes: int = 20) -> str:
    """노트의 [[wikilink]]를 따라 연결 노트를 BFS로 다중 뎁스 스캔한다."""
    root_result = json.loads(obsidian_read_note(path))
    if "error" in root_result:
        return json.dumps(root_result)

    visited: dict[str, dict] = {}
    unresolved: list[str] = []
    # (경로, 내용, 현재 깊이)
    queue: list[tuple[str, str, int]] = [(path, root_result["content"], 0)]

    while queue and len(visited) < max_notes:
        cur_path, cur_content, cur_depth = queue.pop(0)
        if cur_path in visited:
            continue

        links = _extract_wikilinks(cur_content)
        entry: dict = {
            "path":      cur_path,
            "depth":     cur_depth,
            "wikilinks": links,
            "content":   cur_content if cur_depth == 0 else cur_content[:2000],
        }
        if cur_depth > 0 and len(cur_content) > 2000:
            entry["content_truncated"] = True
        visited[cur_path] = entry

        if cur_depth < depth:
            for title in links:
                if len(visited) >= max_notes:
                    break
                if any(v["path"].endswith(f"/{title}.md") or v["path"] == f"{title}.md"
                       for v in visited.values()):
                    continue
                resolved_path, link_content = _resolve_wikilink(title)
                if resolved_path and link_content is not None and resolved_path not in visited:
                    queue.append((resolved_path, link_content, cur_depth + 1))
                elif resolved_path is None and title not in unresolved:
                    unresolved.append(title)

    return json.dumps(
        {
            "root":            path,
            "depth_scanned":   depth,
            "total":           len(visited),
            "unresolved_links": unresolved,
            "notes":           list(visited.values()),
        },
        ensure_ascii=False,
    )


# ── MANIFEST ──────────────────────────────────────────────────

MANIFEST = [
    {
        "name": "obsidian_search",
        "label": "Vault 전체 검색",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_search",
                "description": (
                    "Obsidian Vault 전체에서 키워드를 검색하고 관련 노트 목록을 반환합니다. "
                    "업무 도메인 지식, 과거 분석 결과, 시스템 명세를 찾을 때 사용합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "검색 키워드"},
                        "limit": {"type": "integer", "description": "최대 결과 수 (기본 20)"},
                    },
                    "required": ["query"],
                },
            }
        },
        "handler": lambda a: obsidian_search(a["query"], a.get("limit", 20))
    },
    {
        "name": "obsidian_read_note",
        "label": "노트 읽기",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_read_note",
                "description": (
                    "Vault 경로로 특정 노트의 전체 내용을 읽습니다. "
                    "예: 'projects/Syncade.md', 'agent/notes/분석.md'"
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "Vault 루트 기준 상대 경로 (.md 포함)"},
                    },
                    "required": ["path"],
                },
            }
        },
        "handler": lambda a: obsidian_read_note(a["path"])
    },
    {
        "name": "obsidian_list_notes",
        "label": "노트 목록 조회",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_list_notes",
                "description": (
                    "Vault 폴더의 노트 목록과 하위 폴더를 반환합니다. "
                    "folder 생략 시 루트 목록을 반환합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "folder": {"type": "string", "description": "폴더 경로 (예: 'projects', 'agent/notes')"},
                        "limit":  {"type": "integer", "description": "최대 노트 수 (기본 50)"},
                    },
                },
            }
        },
        "handler": lambda a: obsidian_list_notes(a.get("folder", ""), a.get("limit", 50))
    },
    {
        "name": "obsidian_write_note",
        "label": "노트 작성/덮어쓰기",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_write_note",
                "description": (
                    "Vault에 노트를 생성하거나 덮어씁니다. "
                    "분석 결과, 업무 정리, 지식 문서를 저장할 때 사용합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path":    {"type": "string", "description": "저장 경로 (예: 'projects/분석결과.md')"},
                        "content": {"type": "string", "description": "노트 내용 (마크다운)"},
                    },
                    "required": ["path", "content"],
                },
            }
        },
        "handler": lambda a: obsidian_write_note(a["path"], a["content"])
    },
    {
        "name": "obsidian_append_note",
        "label": "노트에 내용 추가",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_append_note",
                "description": (
                    "기존 노트 끝에 내용을 추가합니다. 일지, 로그, 회의록 등 누적 기록에 사용합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path":    {"type": "string", "description": "대상 노트 경로"},
                        "content": {"type": "string", "description": "추가할 내용"},
                    },
                    "required": ["path", "content"],
                },
            }
        },
        "handler": lambda a: obsidian_append_note(a["path"], a["content"])
    },
    {
        "name": "obsidian_get_tags",
        "label": "노트 태그 조회",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_get_tags",
                "description": (
                    "노트의 프론트매터 태그와 본문 인라인 태그(#tag)를 모두 반환합니다. "
                    "관련 노트를 태그로 분류할 때 사용합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "노트 경로"},
                    },
                    "required": ["path"],
                },
            }
        },
        "handler": lambda a: obsidian_get_tags(a["path"])
    },
    {
        "name": "obsidian_follow_links",
        "label": "[[링크]] 다중 뎁스 스캔",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_follow_links",
                "description": (
                    "노트의 [[wikilink]]를 따라 연결된 노트들을 BFS 방식으로 다중 뎁스 스캔합니다. "
                    "관련 노트 네트워크 파악, 도메인 지식 그래프 탐색, 주제 연결 분석에 사용합니다. "
                    "depth=1이면 직접 링크만, depth=2이면 링크의 링크까지 탐색합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path":      {"type": "string",  "description": "시작 노트 경로 (예: 'projects/Syncade.md')"},
                        "depth":     {"type": "integer", "description": "탐색 깊이 (기본 1, 권장 최대 3)"},
                        "max_notes": {"type": "integer", "description": "최대 스캔 노트 수 (기본 20)"},
                    },
                    "required": ["path"],
                },
            }
        },
        "handler": lambda a: obsidian_follow_links(a["path"], a.get("depth", 1), a.get("max_notes", 20))
    },
]
