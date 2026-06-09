"""장기기억 MemoryStore 단위 테스트 (파일 I/O, LLM 불필요)."""

from agent.memory import MemoryStore, Memory


def test_add_and_all_roundtrip(tmp_path):
    s = MemoryStore(tmp_path)
    assert s.all() == []
    m = s.add("사용자는 커밋 메시지를 한국어로 작성한다", category="preference", source="general")
    assert m is not None
    got = s.all()
    assert len(got) == 1
    assert got[0].text == "사용자는 커밋 메시지를 한국어로 작성한다"
    assert got[0].category == "preference"
    assert got[0].id == m.id


def test_persisted_across_instances(tmp_path):
    MemoryStore(tmp_path).add("회사 도메인은 sbiologics.com 이다")
    again = MemoryStore(tmp_path).all()
    assert len(again) == 1
    assert "sbiologics.com" in again[0].text


def test_dedup_skips_duplicate_and_substring(tmp_path):
    s = MemoryStore(tmp_path)
    assert s.add("파이썬 3.11 conda 환경을 쓴다") is not None
    assert s.add("파이썬 3.11 conda 환경을 쓴다") is None          # 완전 동일
    assert s.add("파이썬 3.11 conda 환경을 쓴다 (mes-agent)") is None  # 기존을 포함
    assert len(s.all()) == 1


def test_empty_text_not_added(tmp_path):
    s = MemoryStore(tmp_path)
    assert s.add("   ") is None
    assert s.all() == []


def test_search_scores_and_orders(tmp_path):
    s = MemoryStore(tmp_path)
    s.add("사용자는 한국어 답변을 선호한다")
    s.add("배포는 폐쇄망 PC로 git pull 한다")
    s.add("한국어 커밋 메시지를 쓴다")
    hits = s.search("한국어 커밋", k=5)
    assert hits, "검색 결과 없음"
    # '한국어 커밋'에 가장 많이 겹치는 항목이 먼저
    assert hits[0].text == "한국어 커밋 메시지를 쓴다"
    # 무관 쿼리는 빈 결과
    assert s.search("날씨 주식 강아지") == []


def test_search_respects_k(tmp_path):
    s = MemoryStore(tmp_path)
    for i in range(6):
        s.add(f"테스트 사실 항목 번호{i} 공통키워드")
    assert len(s.search("공통키워드", k=3)) == 3


def test_delete(tmp_path):
    s = MemoryStore(tmp_path)
    m = s.add("삭제될 기억")
    assert s.delete(m.id) is True
    assert s.all() == []
    assert s.delete("nonexistent") is False


def test_cap_keeps_recent(tmp_path, monkeypatch):
    import agent.memory as mem
    monkeypatch.setattr(mem, "_MAX_MEMORIES", 5)
    s = MemoryStore(tmp_path)
    for i in range(8):
        s.add(f"고유한 기억 항목 식별자{i}")
    allm = s.all()
    assert len(allm) == 5
    # 오래된 것부터 제거 → 마지막 것이 남음
    assert any("식별자7" in m.text for m in allm)
    assert not any("식별자0" in m.text for m in allm)
