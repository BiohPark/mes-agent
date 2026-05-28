"""
사용자 상호작용 도구 — 중요 작업 전 확인 요청
"""

import json
import uuid


def ask_user(question: str, options: list | None = None) -> str:
    """중요한 작업 실행 전 사용자에게 확인을 요청한다."""
    confirm_id = uuid.uuid4().hex[:8]
    if options is None:
        options = ["계속 진행", "중단", "방법 변경 제안", "의견 전달"]
    return json.dumps({
        "__confirm__": True,
        "confirm_id": confirm_id,
        "question": question,
        "options": options,
    }, ensure_ascii=False)


MANIFEST = [
    {
        "name": "ask_user",
        "label": "사용자 확인 요청",
        "schema": {
            "type": "function",
            "function": {
                "name": "ask_user",
                "description": (
                    "중요한 작업 실행 전 사용자에게 확인을 요청합니다. "
                    "파일 삭제·덮어쓰기, 데이터 수정, 시스템 설정 변경 등 "
                    "되돌리기 어려운 작업 전에 반드시 호출하세요. "
                    "사용자는 계속 진행 / 중단 / 방법 변경 제안 / 의견 전달 중 선택합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "question": {
                            "type": "string",
                            "description": (
                                "사용자에게 보여줄 확인 질문. "
                                "예: 'report.xlsx를 덮어쓰려고 합니다. 계속하시겠습니까?'"
                            ),
                        },
                        "options": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "선택지 목록. 생략 시 기본 4가지 옵션 사용.",
                        },
                    },
                    "required": ["question"],
                },
            },
        },
        "handler": lambda a: ask_user(a["question"], a.get("options")),
    },
]
