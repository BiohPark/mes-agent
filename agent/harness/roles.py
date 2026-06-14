"""하네스 역할 정의 — Executor · Reviewer.

계약: docs/contracts/harness-poc-v1.md
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class HarnessRole:
    """하네스 역할 정의 (불변)."""

    name: str
    system_suffix: str
    allowed_modules: frozenset[str] | None  # None = 모든 도구 허용


EXECUTOR = HarnessRole(
    name="executor",
    system_suffix=(
        "당신은 실행자입니다. "
        "주어진 목표를 도구를 사용해 완수하세요. "
        "작업이 완전히 완료되면 결과를 간결하게 요약하세요."
    ),
    allowed_modules=None,
)

REVIEWER = HarnessRole(
    name="reviewer",
    system_suffix=(
        "당신은 검증자입니다. "
        "읽기 전용 도구(OCR·파일 읽기·시스템 조회)로 실행자의 작업 결과를 확인하고, "
        "정확히 완수됐으면 {\"passed\": true}를, "
        "문제가 있으면 {\"passed\": false, \"feedback\": \"구체적인 수정 지침\"}을 "
        "JSON으로만 반환하세요. 다른 텍스트는 일절 출력하지 마세요."
    ),
    allowed_modules=frozenset({
        "ocr",
        "screen",
        "process",
        "document",
        "obsidian_rag",
    }),
)

HARNESS_ROLES: dict[str, HarnessRole] = {
    EXECUTOR.name: EXECUTOR,
    REVIEWER.name: REVIEWER,
}


def get_role(name: str) -> HarnessRole:
    """역할 이름으로 HarnessRole 조회. 없으면 KeyError."""
    return HARNESS_ROLES[name]
