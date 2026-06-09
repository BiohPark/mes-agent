"""
멀티모달 비전 도구 — LLM 이미지 분석으로 화면 맥락 이해
활성화: .env 에 VISION_ENABLED=true 추가 + 멀티모달 지원 LLM 필요
"""

import json
import base64
import os
import io


def _check_vision() -> tuple[bool, str]:
    # 사내 멀티모달 LLM 확인됨 → 기본 켬. 비전 미지원 모델 사용 시 .env에서 false로 끌 수 있다.
    enabled = os.environ.get('VISION_ENABLED', 'true').lower() in ('1', 'true', 'yes')
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
        }]
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


# ── 메인 루프 이미지 주입 (capture_screen) ───────────────────────────
# analyze_* 가 "별도 LLM 호출 → 텍스트 요약"인 것과 달리, capture_screen 은
# 실제 스크린샷을 메인 에이전트 대화에 그대로 흘려보낸다. server.generate() 루프가
# 이 봉투를 감지해 user 멀티모달 메시지(image_url)로 주입하고, 메인 LLM이 화면을
# 직접 본다. tool_call 짝(I1)을 깨지 않으려 tool 메시지는 짧은 텍스트로 채우고
# 이미지는 별도 user 메시지로 넣는다.
_CAPTURE_NOTE = "화면을 캡처했습니다. 다음 user 메시지의 이미지를 직접 보고 작업 상황을 파악하세요."


def capture_screen(prompt: str = "", x: int = 0, y: int = 0, width: int = 0, height: int = 0) -> str:
    """화면을 캡처해 메인 LLM이 직접 보도록 이미지를 대화에 주입합니다.
    OCR/UI 트리로 파악 안 되는 화면을 실제 이미지로 확인하거나, 작업자와
    호흡하며 진행 상황을 능동적으로 이해해야 할 때 사용합니다.
    영역 인자(x,y,width,height)가 모두 0이면 전체 화면을 캡처합니다."""
    ok, msg = _check_vision()
    if not ok:
        return json.dumps({"error": msg})
    try:
        png = _screenshot(x, y, width, height)
        return json.dumps({
            "__capture__": True,
            "image_b64": base64.b64encode(png).decode(),
            "prompt": prompt or "",
            "note": _CAPTURE_NOTE,
        })
    except Exception as e:
        return json.dumps({"error": str(e)})


def parse_capture_envelope(result: str):
    """run_tool 결과가 capture_screen 봉투면 dict, 아니면 None을 반환한다(순수·테스트용)."""
    try:
        obj = json.loads(result)
    except (TypeError, ValueError):
        return None
    if isinstance(obj, dict) and obj.get("__capture__") and obj.get("image_b64"):
        return obj
    return None


MANIFEST = [
    {
        "name": "capture_screen",
        "label": "화면 캡처(메인 LLM 직접 확인)",
        "schema": {
            "type": "function",
            "function": {
                "name": "capture_screen",
                "description": (
                    "화면을 캡처해 너(메인 LLM)가 이미지를 직접 본다. "
                    "OCR/UI 트리로 안 되는 화면을 실제 이미지로 확인하거나, 작업 상황 파악·"
                    "작업자와 호흡이 필요할 때 사용한다. 캡처 후 다음 메시지에 이미지가 첨부된다. "
                    "영역 인자를 비우면 전체 화면을 캡처한다."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "prompt": {
                            "type": "string",
                            "description": "이미지에서 무엇을 확인할지(선택). 예: '진행 상태 표시줄이 끝났는지 확인'"
                        },
                        "x": {"type": "integer", "description": "영역 왼쪽 상단 X (전체 화면이면 생략)"},
                        "y": {"type": "integer", "description": "영역 왼쪽 상단 Y (전체 화면이면 생략)"},
                        "width": {"type": "integer", "description": "영역 너비 (전체 화면이면 생략)"},
                        "height": {"type": "integer", "description": "영역 높이 (전체 화면이면 생략)"}
                    },
                    "required": []
                }
            }
        },
        "handler": lambda a: capture_screen(
            a.get("prompt", ""), a.get("x", 0), a.get("y", 0), a.get("width", 0), a.get("height", 0)
        )
    },
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
