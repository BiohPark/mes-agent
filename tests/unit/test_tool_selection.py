"""요청당 도구 서브셋 선택 — tools 배열 128 한계 회귀 방지.

등록 도구가 128을 넘어도 select_tools()가 한도 이하로 추려야 한다(이 버그의 직접 회귀 테스트).
"""

from agent.tools import TOOLS, select_tools, LLM_MAX_TOOLS, _registry


def _names(schemas):
    return {s["function"]["name"] for s in schemas}


def test_selection_never_exceeds_limit():
    """기본 호출은 절대 128(LLM_MAX_TOOLS)을 넘지 않는다 — 핵심 회귀 테스트."""
    sel = select_tools()
    assert len(sel) <= LLM_MAX_TOOLS
    assert len(sel) <= 128


def test_registry_exceeds_limit_so_subsetting_is_active():
    """전제: 등록 도구가 한도보다 많아 서브셋이 실제로 동작하는 상황."""
    assert len(TOOLS) > LLM_MAX_TOOLS, "등록 도구가 한도 이하라면 이 테스트의 전제가 깨짐"
    assert len(select_tools()) < len(TOOLS)


def test_core_tools_always_present():
    names = _names(select_tools())
    for core in ("ask_user", "memory_remember", "workflow_init", "browser_open",
                 "read_excel", "capture_screen"):
        assert core in names, f"core 도구 {core}가 서브셋에서 빠짐"


def test_default_drops_cloud_office():
    """관련 키워드가 없으면 office_cloud(graph_*, GRAPH 토큰 필요)는 기본 드롭."""
    names = _names(select_tools("안녕 오늘 일정 정리해줘"))
    assert "graph_find_item" not in names


def test_relevance_includes_cloud_office():
    """클라우드/graph 키워드가 있으면 office_cloud 도구가 포함된다."""
    sel = select_tools("클라우드 graph M365 문서 편집해줘")
    names = _names(sel)
    assert "graph_excel_set_range" in names
    assert len(sel) <= 128


def test_limit_above_registry_returns_all():
    sel = select_tools(limit=len(_registry) + 10)
    assert len(sel) == len(TOOLS)


def test_no_duplicate_schemas_in_selection():
    sel = select_tools()
    names = [s["function"]["name"] for s in sel]
    assert len(names) == len(set(names))
