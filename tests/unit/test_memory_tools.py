"""명시적 장기기억 도구 단위 테스트 — remember/forget/recall 라운드트립."""

import json

import pytest

from agent.memory import MemoryStore
from agent.tools import memory_tools


@pytest.fixture
def store(tmp_path, monkeypatch):
    """격리된 임시 vault를 memory_tools._store()가 쓰도록 환경변수 지정."""
    monkeypatch.setenv("OBSIDIAN_VAULT_PATH", str(tmp_path))
    return MemoryStore(tmp_path)


def test_remember_saves_memory(store):
    res = json.loads(memory_tools.memory_remember("사용자는 PPT를 16:9로 만든다", "preference"))
    assert res["ok"] and res["saved"]
    texts = [m.text for m in store.all()]
    assert any("16:9" in t for t in texts)


def test_remember_empty_is_rejected(store):
    res = json.loads(memory_tools.memory_remember("   "))
    assert res["ok"] is False


def test_remember_dedup(store):
    memory_tools.memory_remember("회사 도메인은 사내 전용이다", "fact")
    res = json.loads(memory_tools.memory_remember("회사 도메인은 사내 전용이다", "fact"))
    assert res["saved"] is False
    assert len(store.all()) == 1


def test_remember_invalid_category_falls_back_to_fact(store):
    res = json.loads(memory_tools.memory_remember("어떤 사실", "nonsense"))
    assert res["category"] == "fact"


def test_recall_finds_by_keyword(store):
    memory_tools.memory_remember("배포는 금요일 오후에 하지 않는다", "decision")
    res = json.loads(memory_tools.memory_recall("배포 금요일"))
    assert res["ok"]
    assert any("금요일" in m["text"] for m in res["memories"])


def test_forget_by_keyword_deletes(store):
    memory_tools.memory_remember("선호하는 에디터는 VS Code", "preference")
    res = json.loads(memory_tools.memory_forget("에디터 VS Code"))
    assert res["deleted"] is True
    assert store.all() == []


def test_forget_by_id_deletes(store):
    saved = json.loads(memory_tools.memory_remember("Obsidian Vault 경로는 .env에서 읽는다", "fact"))
    mem_id = saved["id"]
    res = json.loads(memory_tools.memory_forget(mem_id))
    assert res["deleted"] is True and res["id"] == mem_id
    assert store.all() == []


def test_forget_no_match(store):
    memory_tools.memory_remember("어떤 기억", "fact")
    res = json.loads(memory_tools.memory_forget("전혀무관한키워드xyz"))
    assert res["deleted"] is False
    assert len(store.all()) == 1
