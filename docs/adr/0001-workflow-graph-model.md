# ADR-0001: 워크플로우 모델 — 선형 리스트에서 분기 그래프로

> 상태: **채택됨 · 구현 완료(2026-06)** | 작성일: 2026-06-07
> 구현: `agent/workflow/model.py`(`WorkflowDefinition`·`WorkflowNode`·`WorkflowConnection`·`WorkflowRunState`·`migrate_linear_to_graph`), `storage.py`(포맷 감지·YAML frontmatter 마이그레이션), `agent/tools/workflow.py`(connection 툴 포함 8종).

---

## 맥락

현재 `Workflow.steps: list[WorkflowStep]`는 순서 있는 선형 체크리스트다. 브리프 P1이 요구하는 조건 분기, P1-b의 사람·에이전트 단일 진실 소스, C3의 정의/상태 분리를 모두 충족하려면 데이터 모델 진화가 필요하다.

**핵심 질문 두 가지:**
1. 그래프 구조를 어떻게 표현할 것인가? (노드+엣지 vs 중첩 트리)
2. 워크플로우 정의(불변)와 실행 상태(가변)를 분리할 것인가?

---

## 대안 A — n8n식 노드/커넥션 분리 (권고안)

### 구조

```python
@dataclass
class WorkflowNode:
    id: str
    title: str
    type: NodeType           # "auto" | "semi_auto" | "manual" | "condition"
    retry: int = 0           # 재시도 횟수 (C2)
    on_error: str = "stop"   # "stop" | "continue" | node_id

@dataclass
class WorkflowConnection:
    from_node: str           # node id
    from_output: int = 0     # 0=기본, 1=조건분기 true, 2=false 등
    to_node: str

@dataclass
class WorkflowDefinition:
    """불변 정의 — Vault에 저장, 사람이 편집 가능."""
    id: str                  # 기존 thread_id
    task_type: str
    title: str
    nodes: list[WorkflowNode]
    connections: list[WorkflowConnection]

@dataclass
class WorkflowRunState:
    """가변 실행 상태 — 런타임 분리, 메모리 또는 별도 파일."""
    definition_id: str
    node_states: dict[str, NodeState]  # node_id → {status, notes, started_at}
```

### JSON 직렬화 예시 (사람이 읽는 정의 파일)

```json
{
  "id": "2026-06-07-001",
  "task_type": "syncade",
  "title": "Syncade 배포",
  "nodes": [
    {"id": "n1", "title": "빌드 확인", "type": "auto"},
    {"id": "n2", "title": "배포 실행 성공?", "type": "condition"},
    {"id": "n3", "title": "서비스 확인", "type": "auto"},
    {"id": "n4", "title": "롤백", "type": "semi_auto"}
  ],
  "connections": [
    {"from_node": "n1", "from_output": 0, "to_node": "n2"},
    {"from_node": "n2", "from_output": 1, "to_node": "n3"},
    {"from_node": "n2", "from_output": 2, "to_node": "n4"}
  ]
}
```

### 하위 호환·마이그레이션

기존 선형 `steps` 배열 → 자동 변환 함수:
```python
def migrate_linear_to_graph(wf: Workflow) -> WorkflowDefinition:
    nodes = [WorkflowNode(id=s.id, title=s.title, type=s.type) for s in wf.steps]
    connections = [
        WorkflowConnection(from_node=nodes[i].id, to_node=nodes[i+1].id)
        for i in range(len(nodes) - 1)
    ]
    return WorkflowDefinition(...)
```

기존 `steps` JSON이 저장된 파일을 load할 때 형태 감지 후 자동 마이그레이션.

### 툴 인터페이스 변화

| 툴 | 변화 |
|----|------|
| `workflow_init` | `steps` → `nodes` + `connections` 파라미터 추가 (steps도 계속 받아 마이그레이션) |
| `workflow_set_step` | 이름 유지, RunState 업데이트 대상으로 변경 |
| `workflow_add_step` | `add_node` + `add_connection`으로 분리 또는 헬퍼로 래핑 |
| `workflow_remove_step` | node 제거 + 관련 connection 정리 추가 |
| `workflow_reorder` | 선형에만 의미 있으므로 deprecated 예정 (연결 재정의로 대체) |
| `workflow_update_step` | 변화 없음 |

### 트레이드오프

| 장점 | 단점 |
|------|------|
| 조건 분기 표현 가능 | 기존 코드 변경 범위 큼 |
| 정의/상태 명확 분리 | connections 개념 학습 비용 |
| 위상 정렬로 실행 순서 결정 | RunState 저장소 설계 추가 필요 |
| 사람이 JSON 읽기 적당히 가능 | 복잡 그래프는 여전히 JSON이 불편 |

---

## 대안 B — 중첩 트리(nested children) 모델

### 구조

```python
@dataclass
class WorkflowStep:
    id: str
    title: str
    type: str
    status: str           # 정의와 상태 혼재 유지
    condition: str = ""   # "success" | "failure" | ""
    children: list        # list[WorkflowStep]
```

### 트레이드오프

| 장점 | 단점 |
|------|------|
| 기존 구조에서 변화 최소 | 정의/상태 분리 안 됨 (C3 미달) |
| 단순 분기(if/else)는 표현 가능 | 다이아몬드 그래프(합류 노드) 불가 |
| children으로 직관적 이해 | 깊이 중첩 시 JSON 읽기 불편 |
| 마이그레이션 간단 | 위상 정렬 엔진 필요 동일 |

**결론: 단기 구현 비용은 낮으나 C3 미달, 합류 노드 불가라는 구조적 한계로 장기 부채 누적.**

---

## 결정

**대안 A (노드/커넥션 분리) 채택 — 단계적 적용.**

이유:
1. C3(정의/상태 분리)를 구조적으로 강제 — 사람의 Obsidian 편집이 실행 상태를 깨지 않음
2. 조건 분기와 합류 노드 모두 표현 가능
3. 기존 선형 모델을 자동 마이그레이션으로 하위 호환 유지

**단계적 적용 계획:**
1. `WorkflowDefinition` + `WorkflowRunState` 데이터클래스 도입 (기존 `Workflow` 유지, 병행)
2. `storage.py`에 새 포맷 감지·마이그레이션 로직 추가
3. 툴 6종 시그니처를 backwards-compatible 확장
4. 실행 루프(`server.py`)에서 RunState 분리 사용
5. 기존 포맷 완전 제거는 모든 스레드 마이그레이션 확인 후

---

## 결정하지 않은 것 (다음 스파이크로)

- **RunState 저장소:** 메모리(휘발) vs 별도 JSON 파일 vs Vault 노트. 재시작 후 재개 요구 여부에 따라 결정.
- **조건 분기 평가:** LLM이 from_output을 결정하는가 vs 단계 결과 값 기반 룰 평가. 현재 구조에선 LLM 결정으로 시작 후 룰 기반으로 진화 예정.
- **Obsidian Canvas 활용:** 그래프를 Canvas(.canvas JSON)로 저장해 사람이 시각적으로 편집하는 경로. 별도 스파이크 필요.
