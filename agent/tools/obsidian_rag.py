"""
Obsidian PKM 도구 — Vault 탐색·편집·정리
- 1순위: Obsidian Local REST API (OBSIDIAN_HOST + OBSIDIAN_API_KEY)
- fallback: OBSIDIAN_VAULT_PATH 직접 파일 접근
"""

import os
import re
import ssl
import json
import yaml
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


def obsidian_follow_links(
    path: str, depth: int = 1, max_notes: int = 20, max_chars_per_note: int = 2000
) -> str:
    """노트의 [[wikilink]]를 따라 연결 노트를 BFS로 다중 뎁스 스캔한다."""
    root_result = json.loads(obsidian_read_note(path))
    if "error" in root_result:
        return json.dumps(root_result)

    visited: dict[str, dict] = {}
    unresolved: list[str] = []
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
            "content":   cur_content if cur_depth == 0 else cur_content[:max_chars_per_note],
        }
        if cur_depth > 0 and len(cur_content) > max_chars_per_note:
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
            "root":             path,
            "depth_scanned":    depth,
            "total":            len(visited),
            "unresolved_links": unresolved,
            "notes":            list(visited.values()),
        },
        ensure_ascii=False,
    )


# ── 신규 툴 함수 (Phase 7) ────────────────────────────────────

def obsidian_preview_note(path: str, lines: int = 15) -> str:
    """노트의 첫 N줄과 메타데이터(크기·프론트매터)만 반환한다. 전문 읽기 전 필터링용."""
    encoded = urllib.parse.quote(path, safe="/")
    raw = _api_request("GET", f"/vault/{encoded}")

    if raw is not None:
        content = raw
        size_bytes = len(raw.encode("utf-8"))
    else:
        vault = _vault()
        if not vault:
            return json.dumps({"error": "Obsidian 미설정"})
        p = vault / path
        if not p.exists():
            return json.dumps({"error": f"노트를 찾을 수 없습니다: {path}"})
        size_bytes = p.stat().st_size
        content = p.read_text(encoding="utf-8", errors="ignore")

    if not content and raw == "":
        return json.dumps({"error": f"노트를 찾을 수 없습니다: {path}"})

    fm = _parse_frontmatter(content)
    all_lines = content.splitlines()
    preview = "\n".join(all_lines[:lines])

    return json.dumps({
        "path":        path,
        "size_kb":     round(size_bytes / 1024, 1),
        "total_lines": len(all_lines),
        "frontmatter": fm,
        "preview":     preview,
    }, ensure_ascii=False)


def obsidian_scan_vault(
    paths: list = None, folder: str = None, limit: int = 20
) -> str:
    """여러 노트를 한 번에 preview해 크기·태그·첫 줄을 반환한다. 관련성 판단용 배치 스캔."""
    if paths is None:
        folder_result = json.loads(obsidian_list_notes(folder or "", limit))
        if "error" in folder_result:
            return json.dumps(folder_result)
        paths = folder_result.get("notes", [])[:limit]

    notes = []
    for p in paths[:limit]:
        preview = json.loads(obsidian_preview_note(p, lines=10))
        notes.append(preview)

    return json.dumps({"count": len(notes), "notes": notes}, ensure_ascii=False)


def obsidian_get_backlinks(path: str) -> str:
    """이 노트를 [[링크]]하는 다른 노트 목록을 반환한다."""
    stem = Path(path).stem

    # REST API 검색 시도
    query = f"[[{stem}]]"
    raw = _api_request("POST", f"/search/simple/?query={urllib.parse.quote(query)}")
    if raw is not None:
        try:
            data = json.loads(raw) if raw else []
            backlinks = [r.get("filename", "") for r in data
                         if r.get("filename", "") != path and r.get("filename", "")]
            return json.dumps({"path": path, "backlinks": backlinks, "count": len(backlinks)},
                              ensure_ascii=False)
        except Exception:
            pass

    # Fallback: Vault 직접 스캔
    vault = _vault()
    if not vault:
        return json.dumps({"error": "Obsidian 미설정"})

    pattern = re.compile(r"\[\[" + re.escape(stem) + r"[\]|#]", re.IGNORECASE)
    backlinks = []
    for md in vault.rglob("*.md"):
        rel = str(md.relative_to(vault)).replace("\\", "/")
        if rel == path:
            continue
        try:
            text = md.read_text(encoding="utf-8", errors="ignore")
            if pattern.search(text):
                backlinks.append(rel)
        except Exception:
            continue

    return json.dumps({"path": path, "backlinks": backlinks, "count": len(backlinks)},
                      ensure_ascii=False)


def obsidian_read_section(path: str, heading: str) -> str:
    """노트에서 특정 헤딩 섹션의 내용만 읽는다. 토큰 절약용 부분 읽기."""
    result = json.loads(obsidian_read_note(path))
    if "error" in result:
        return json.dumps(result)

    lines = result["content"].splitlines()
    pattern = re.compile(r"^(#{1,6})\s+" + re.escape(heading) + r"\s*$", re.IGNORECASE)

    start_idx = None
    heading_level = 0
    for i, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            start_idx = i
            heading_level = len(m.group(1))
            break

    if start_idx is None:
        return json.dumps({"error": f"헤딩 '{heading}'을 찾을 수 없습니다: {path}"})

    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        m = re.match(r"^(#{1,6})\s+", lines[i])
        if m and len(m.group(1)) <= heading_level:
            end_idx = i
            break

    section = "\n".join(lines[start_idx:end_idx])
    return json.dumps({
        "path":    path,
        "heading": heading,
        "content": section,
        "lines":   end_idx - start_idx,
    }, ensure_ascii=False)


def obsidian_search_advanced(
    query: str = "", tags: list = None, folder: str = None,
    limit: int = 20, sort: str = "modified"
) -> str:
    """태그·폴더 필터와 정렬을 지원하는 고급 검색."""
    vault = _vault()
    candidates = None

    if query:
        raw = _api_request("POST", f"/search/simple/?query={urllib.parse.quote(query)}")
        if raw is not None:
            try:
                data = json.loads(raw) if raw else []
                candidates = [r.get("filename", "") for r in data if r.get("filename", "")]
            except Exception:
                pass

    if candidates is None:
        if not vault:
            return json.dumps({"error": "Obsidian 미설정"})
        all_files = list(vault.rglob("*.md"))
        if folder:
            target = vault / folder
            all_files = [f for f in all_files if str(f.resolve()).startswith(str(target.resolve()))]
        candidates = [str(f.relative_to(vault)).replace("\\", "/") for f in all_files]

    if folder:
        prefix = folder.rstrip("/") + "/"
        candidates = [c for c in candidates if c.startswith(prefix) or c == folder.lstrip("/")]

    results = []
    for c in candidates:
        if not c:
            continue
        if tags:
            note_result = json.loads(obsidian_read_note(c))
            if "error" in note_result:
                continue
            content = note_result.get("content", "")
            fm = _parse_frontmatter(content)
            fm_tags_raw = fm.get("tags", "")
            if fm_tags_raw.startswith("["):
                fm_tags = [t.strip(" '\"[]") for t in fm_tags_raw.strip("[]").split(",")]
            else:
                fm_tags = [t.strip() for t in fm_tags_raw.split(",") if t.strip()]
            body = re.sub(r"```.*?```", "", content, flags=re.DOTALL)
            inline_tags = re.findall(r"(?<!\w)#([\w가-힣/-]+)", body)
            all_note_tags = set(fm_tags + inline_tags)
            if not any(t in all_note_tags for t in tags):
                continue
        results.append(c)

    if sort == "modified" and vault:
        def _mtime(p: str) -> float:
            try:
                return (vault / p).stat().st_mtime
            except Exception:
                return 0.0
        results.sort(key=_mtime, reverse=True)

    results = results[:limit]
    return json.dumps({
        "query":   query,
        "tags":    tags or [],
        "folder":  folder or "/",
        "count":   len(results),
        "results": results,
    }, ensure_ascii=False)


def obsidian_edit_note(path: str, old_text: str, new_text: str) -> str:
    """노트 내 특정 텍스트를 정확히 교체한다. old_text가 여러 곳이면 오류 반환(안전장치)."""
    result = json.loads(obsidian_read_note(path))
    if "error" in result:
        return json.dumps(result)

    content = result["content"]
    count = content.count(old_text)
    if count == 0:
        return json.dumps({"error": f"텍스트를 찾을 수 없습니다: {repr(old_text[:80])}"})
    if count > 1:
        return json.dumps({"error": f"텍스트가 {count}곳에서 발견되어 모호합니다. 더 구체적인 텍스트를 사용하세요."})

    new_content = content.replace(old_text, new_text, 1)
    write_result = json.loads(obsidian_write_note(path, new_content))
    write_result["edited"] = True
    return json.dumps(write_result, ensure_ascii=False)


def obsidian_replace_section(path: str, heading: str, new_content: str) -> str:
    """헤딩 섹션 전체 내용을 교체한다. 헤딩 줄 자체는 보존된다."""
    result = json.loads(obsidian_read_note(path))
    if "error" in result:
        return json.dumps(result)

    lines = result["content"].splitlines()
    pattern = re.compile(r"^(#{1,6})\s+" + re.escape(heading) + r"\s*$", re.IGNORECASE)

    start_idx = None
    heading_level = 0
    heading_line = ""
    for i, line in enumerate(lines):
        m = pattern.match(line)
        if m:
            start_idx = i
            heading_level = len(m.group(1))
            heading_line = line
            break

    if start_idx is None:
        return json.dumps({"error": f"헤딩 '{heading}'을 찾을 수 없습니다: {path}"})

    end_idx = len(lines)
    for i in range(start_idx + 1, len(lines)):
        m = re.match(r"^(#{1,6})\s+", lines[i])
        if m and len(m.group(1)) <= heading_level:
            end_idx = i
            break

    new_lines = lines[:start_idx] + [heading_line] + new_content.splitlines() + lines[end_idx:]
    write_result = json.loads(obsidian_write_note(path, "\n".join(new_lines)))
    write_result["replaced_section"] = heading
    return json.dumps(write_result, ensure_ascii=False)


def obsidian_update_frontmatter(path: str, updates: dict) -> str:
    """프론트매터 필드를 추가하거나 업데이트한다. 없으면 새로 생성한다."""
    result = json.loads(obsidian_read_note(path))
    if "error" in result:
        return json.dumps(result)

    content = result["content"]

    if content.startswith("---"):
        end = content.find("\n---", 3)
        if end != -1:
            fm_str = content[4:end]
            body = content[end + 4:]
            try:
                fm = yaml.safe_load(fm_str) or {}
            except Exception:
                fm = {}
        else:
            fm = {}
            body = content
    else:
        fm = {}
        body = ("\n" + content) if content else ""

    fm.update(updates)
    fm_yaml = yaml.dump(fm, allow_unicode=True, default_flow_style=False).strip()
    new_content = f"---\n{fm_yaml}\n---{body}"

    write_result = json.loads(obsidian_write_note(path, new_content))
    write_result["updated_fields"] = list(updates.keys())
    return json.dumps(write_result, ensure_ascii=False)


def obsidian_move_note(
    from_path: str, to_path: str, update_links: bool = True
) -> str:
    """노트를 이동/이름 변경하고 [[wikilink]]를 자동 업데이트한다."""
    result = json.loads(obsidian_read_note(from_path))
    if "error" in result:
        return json.dumps(result)

    content = result["content"]
    write_result = json.loads(obsidian_write_note(to_path, content))
    if not write_result.get("written"):
        return json.dumps({"error": f"새 경로에 쓰기 실패: {to_path}"})

    # 원본 삭제
    vault = _vault()
    if vault:
        old_file = vault / from_path
        if old_file.exists():
            old_file.unlink()

    links_updated = 0
    old_stem = Path(from_path).stem
    new_stem = Path(to_path).stem

    if update_links and vault and old_stem != new_stem:
        pattern = re.compile(r"\[\[" + re.escape(old_stem) + r"([\]|#])", re.IGNORECASE)

        def _replacer(m):
            return f"[[{new_stem}{m.group(1)}"

        for md in vault.rglob("*.md"):
            rel = str(md.relative_to(vault)).replace("\\", "/")
            if rel == to_path:
                continue
            try:
                text = md.read_text(encoding="utf-8", errors="ignore")
                new_text, n = pattern.subn(_replacer, text)
                if n > 0:
                    md.write_text(new_text, encoding="utf-8")
                    links_updated += n
            except Exception:
                continue

    return json.dumps({
        "moved":         True,
        "from_path":     from_path,
        "to_path":       to_path,
        "links_updated": links_updated,
    }, ensure_ascii=False)


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
                    "depth=1이면 직접 링크만, depth=2이면 링크의 링크까지 탐색합니다. "
                    "max_chars_per_note로 비루트 노트의 반환 글자 수를 제한해 토큰을 절약합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path":               {"type": "string",  "description": "시작 노트 경로 (예: 'projects/Syncade.md')"},
                        "depth":              {"type": "integer", "description": "탐색 깊이 (기본 1, 권장 최대 3)"},
                        "max_notes":          {"type": "integer", "description": "최대 스캔 노트 수 (기본 20)"},
                        "max_chars_per_note": {"type": "integer", "description": "비루트 노트 당 최대 글자 수 (기본 2000, 토큰 절약 시 500)"},
                    },
                    "required": ["path"],
                },
            }
        },
        "handler": lambda a: obsidian_follow_links(
            a["path"], a.get("depth", 1), a.get("max_notes", 20), a.get("max_chars_per_note", 2000)
        )
    },
    # ── Phase 7 신규 툴 ──────────────────────────────────────
    {
        "name": "obsidian_preview_note",
        "label": "노트 미리보기 (얕은 읽기)",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_preview_note",
                "description": (
                    "노트의 첫 N줄과 파일 크기·프론트매터만 반환합니다. "
                    "전문을 읽기 전에 관련성을 판단하거나 큰 노트를 얕게 훑을 때 사용하세요. "
                    "전문이 필요하면 obsidian_read_note를 사용하세요."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path":  {"type": "string",  "description": "노트 경로"},
                        "lines": {"type": "integer", "description": "반환할 줄 수 (기본 15)"},
                    },
                    "required": ["path"],
                },
            }
        },
        "handler": lambda a: obsidian_preview_note(a["path"], a.get("lines", 15))
    },
    {
        "name": "obsidian_scan_vault",
        "label": "Vault 배치 미리보기",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_scan_vault",
                "description": (
                    "여러 노트를 한 번에 얕게 스캔해 크기·태그·첫 줄을 반환합니다. "
                    "폴더 전체나 검색 결과 목록을 빠르게 훑어 관련 노트를 추릴 때 사용합니다. "
                    "paths(경로 목록) 또는 folder(폴더명) 중 하나를 지정하세요."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "paths":  {"type": "array",   "items": {"type": "string"}, "description": "미리볼 노트 경로 목록"},
                        "folder": {"type": "string",  "description": "스캔할 폴더 경로"},
                        "limit":  {"type": "integer", "description": "최대 스캔 수 (기본 20)"},
                    },
                },
            }
        },
        "handler": lambda a: obsidian_scan_vault(a.get("paths"), a.get("folder"), a.get("limit", 20))
    },
    {
        "name": "obsidian_get_backlinks",
        "label": "역링크 조회",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_get_backlinks",
                "description": (
                    "이 노트를 [[링크]]하는 다른 노트 목록을 반환합니다. "
                    "어떤 노트들이 이 주제를 참조하는지 파악할 때 사용합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "대상 노트 경로"},
                    },
                    "required": ["path"],
                },
            }
        },
        "handler": lambda a: obsidian_get_backlinks(a["path"])
    },
    {
        "name": "obsidian_read_section",
        "label": "헤딩 섹션 읽기",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_read_section",
                "description": (
                    "노트에서 특정 헤딩 섹션의 내용만 읽습니다. "
                    "큰 노트에서 필요한 부분만 가져올 때 토큰을 크게 절약합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path":    {"type": "string", "description": "노트 경로"},
                        "heading": {"type": "string", "description": "헤딩 텍스트 (# 기호 제외, 예: '설치 방법')"},
                    },
                    "required": ["path", "heading"],
                },
            }
        },
        "handler": lambda a: obsidian_read_section(a["path"], a["heading"])
    },
    {
        "name": "obsidian_search_advanced",
        "label": "고급 검색 (태그·폴더 필터)",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_search_advanced",
                "description": (
                    "태그 필터·폴더 범위·정렬을 지원하는 고급 검색입니다. "
                    "특정 태그가 붙은 노트나 특정 폴더 내 노트를 찾을 때 사용합니다. "
                    "query 생략 시 조건에 맞는 모든 노트를 반환합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query":  {"type": "string",  "description": "검색 키워드 (생략 가능)"},
                        "tags":   {"type": "array",   "items": {"type": "string"}, "description": "필터할 태그 목록"},
                        "folder": {"type": "string",  "description": "검색 범위 폴더"},
                        "limit":  {"type": "integer", "description": "최대 결과 수 (기본 20)"},
                        "sort":   {"type": "string",  "description": "'modified'(최근 수정순, 기본) 또는 'name'"},
                    },
                },
            }
        },
        "handler": lambda a: obsidian_search_advanced(
            a.get("query", ""), a.get("tags"), a.get("folder"), a.get("limit", 20), a.get("sort", "modified")
        )
    },
    {
        "name": "obsidian_edit_note",
        "label": "노트 텍스트 교체",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_edit_note",
                "description": (
                    "노트 내 특정 텍스트를 정확히 교체합니다. "
                    "old_text가 노트에 없거나 여러 곳에 있으면 오류를 반환합니다(안전장치). "
                    "전체 덮어쓰기(obsidian_write_note) 대신 부분 수정이 필요할 때 사용하세요."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path":     {"type": "string", "description": "편집할 노트 경로"},
                        "old_text": {"type": "string", "description": "교체할 원본 텍스트 (정확히 일치, 1번만 나타나야 함)"},
                        "new_text": {"type": "string", "description": "새로 넣을 텍스트"},
                    },
                    "required": ["path", "old_text", "new_text"],
                },
            }
        },
        "handler": lambda a: obsidian_edit_note(a["path"], a["old_text"], a["new_text"])
    },
    {
        "name": "obsidian_replace_section",
        "label": "헤딩 섹션 교체",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_replace_section",
                "description": (
                    "노트의 특정 헤딩 섹션 내용 전체를 교체합니다. 헤딩 줄 자체는 보존됩니다. "
                    "섹션 단위로 내용을 업데이트할 때 obsidian_edit_note보다 안전합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path":        {"type": "string", "description": "노트 경로"},
                        "heading":     {"type": "string", "description": "교체할 섹션의 헤딩 텍스트 (# 제외)"},
                        "new_content": {"type": "string", "description": "새 섹션 내용 (마크다운)"},
                    },
                    "required": ["path", "heading", "new_content"],
                },
            }
        },
        "handler": lambda a: obsidian_replace_section(a["path"], a["heading"], a["new_content"])
    },
    {
        "name": "obsidian_update_frontmatter",
        "label": "프론트매터 업데이트",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_update_frontmatter",
                "description": (
                    "노트의 YAML 프론트매터 필드를 추가하거나 업데이트합니다. "
                    "프론트매터가 없으면 새로 생성합니다. 본문 내용은 보존됩니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path":    {"type": "string", "description": "노트 경로"},
                        "updates": {
                            "type": "object",
                            "description": "업데이트할 필드 딕셔너리 (예: {\"tags\": [\"pkm\"], \"status\": \"draft\"})",
                        },
                    },
                    "required": ["path", "updates"],
                },
            }
        },
        "handler": lambda a: obsidian_update_frontmatter(a["path"], a["updates"])
    },
    {
        "name": "obsidian_move_note",
        "label": "노트 이동/이름 변경",
        "schema": {
            "type": "function",
            "function": {
                "name": "obsidian_move_note",
                "description": (
                    "노트를 이동하거나 이름을 변경합니다. "
                    "update_links=true이면 Vault 내 [[wikilink]]를 새 이름으로 자동 업데이트합니다. "
                    "폴더만 바뀌고 파일 이름이 같으면 링크 업데이트가 불필요합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "from_path":    {"type": "string",  "description": "원본 경로"},
                        "to_path":      {"type": "string",  "description": "대상 경로"},
                        "update_links": {"type": "boolean", "description": "[[wikilink]] 자동 업데이트 여부 (기본 true)"},
                    },
                    "required": ["from_path", "to_path"],
                },
            }
        },
        "handler": lambda a: obsidian_move_note(a["from_path"], a["to_path"], a.get("update_links", True))
    },
]
