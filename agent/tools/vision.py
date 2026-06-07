"""
멀티모달 비전 도구 — LLM 이미지 분석으로 화면 맥락 이해
활성화: .env 에 VISION_ENABLED=true 추가 + 멀티모달 지원 LLM 필요
"""

import json
import base64
import os
import io


def _check_vision() -> tuple[bool, str]:
    enabled = os.environ.get('VISION_ENABLED', '').lower() in ('1', 'true', 'yes')
    if not enabled:
        return False, (
            "멀티모달 비전이 비활성화되어 있습니다. "
            ".env 파일에 VISION_ENABLED=true 를 추가하고, "
            "현재 사용 중인 LLM이 이미지 입력을 지원하는지 확인한 후 서버를 재시작하세요. "
            "지원 여부가 불확실하다면 먼저 사용자에게 확인하세요."
        )
    return True, ""


def _screenshot(x: int = 0, y: int = 0, w: int = 0, h: int = 0) -> bytes:
    import mss
    from PIL import Image
    with mss.mss() as sct:
        monitor = sct.monitors[0] if w == 0 or h == 0 else {"top": y, "left": x, "width": w, "height": h}
        sct_img = sct.grab(monitor)
        img = Image.frombytes('RGB', sct_img.size, sct_img.bgra, 'raw', 'BGRX')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return buf.getvalue()


def _call_llm(prompt: str, image_bytes: bytes) -> str:
    from agent.llm import get_client, get_model
    b64 = base64.b64encode(image_bytes).decode()
    client = get_client()
    resp = client.chat.completions.create(
        model=get_model(),
        messages=[{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"}}
            ]
        }],
        max_tokens=2048
    )
    return resp.choices[0].message.content or ""


def analyze_screen(prompt: str) -> str:
    """전체 화면을 캡처하여 멀티모달 LLM으로 분석합니다.
    화면의 레이아웃·UI 요소·표·차트 등 시각적 맥락을 이해하는 데 사용합니다.
    VISION_ENABLED=true 환경변수와 멀티모달 지원 LLM이 필요합니다."""
    ok, msg = _check_vision()
    if not ok:
        return json.dumps({"error": msg})
    try:
        result = _call_llm(prompt, _screenshot())
        return json.dumps({"analysis": result, "mode": "full_screen"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


def analyze_region(x: int, y: int, width: int, height: int, prompt: str) -> str:
    """화면의 특정 영역을 캡처하여 멀티모달 LLM으로 분석합니다.
    특정 창·패널·표 영역을 집중 분석할 때 사용합니다.
    VISION_ENABLED=true 환경변수와 멀티모달 지원 LLM이 필요합니다."""
    ok, msg = _check_vision()
    if not ok:
        return json.dumps({"error": msg})
    try:
        result = _call_llm(prompt, _screenshot(x, y, width, height))
        return json.dumps({"analysis": result, "region": f"({x},{y}) {width}x{height}"}, ensure_ascii=False)
    except Exception as e:
        return json.dumps({"error": str(e)})


MANIFEST = [
    {
        "name": "analyze_screen",
        "label": "화면 비전 분석",
        "schema": {
            "type": "function",
            "function": {
                "name": "analyze_screen",
                "description": (
                    "전체 화면을 캡처하여 멀티모달 LLM으로 분석합니다. "
                    "OCR로 해결 안 되는 복잡한 UI 레이아웃·차트·표의 시각적 맥락 이해에 사용합니다. "
                    "VISION_ENABLED=true 설정과 멀티모달 LLM 지원이 필요합니다. "
                    "사용 전 현재 LLM이 이미지 입력을 지원하는지 사용자에게 확인하세요."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "화면에서 확인하고 싶은 것을 자세히 설명하세요. 예: '현재 화면의 표에서 총합 행을 찾아주세요'"
                        }
                    },
                    "required": ["prompt"]
                }
            }
        },
        "handler": lambda a: analyze_screen(a["prompt"])
    },
    {
        "name": "analyze_region",
        "label": "영역 비전 분석",
        "schema": {
            "type": "function",
            "function": {
                "name": "analyze_region",
                "description": (
                    "화면의 특정 영역(x, y, width, height)을 캡처하여 멀티모달 LLM으로 분석합니다. "
                    "특정 창·패널에 집중 분석이 필요할 때 사용합니다. "
                    "VISION_ENABLED=true 설정과 멀티모달 LLM 지원이 필요합니다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "x": {"type": "integer", "description": "영역 왼쪽 상단 X 좌표"},
                        "y": {"type": "integer", "description": "영역 왼쪽 상단 Y 좌표"},
                        "width": {"type": "integer", "description": "영역 너비 (픽셀)"},
                        "height": {"type": "integer", "description": "영역 높이 (픽셀)"},
                        "prompt": {"type": "string", "description": "분석 요청 내용"}
                    },
                    "required": ["x", "y", "width", "height", "prompt"]
                }
            }
        },
        "handler": lambda a: analyze_region(a["x"], a["y"], a["width"], a["height"], a["prompt"])
    },
]
