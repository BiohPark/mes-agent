"""M4 컨텍스트 초과(400) 감지 순수 로직 단위 테스트.

모델 무관(원칙 #0): 다양한 프로바이더 문구·예외 형태를 견고하게 감지하는지 확인한다.
"""

from agent.core.overflow import is_context_overflow, is_bad_request, is_recoverable


class _Err(Exception):
    """status_code/code/body 속성을 흉내내는 테스트 예외."""
    def __init__(self, msg="", status_code=None, code=None, body=None):
        super().__init__(msg)
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code
        if body is not None:
            self.body = body


class BadRequestError(Exception):
    """openai.BadRequestError 클래스명 매칭 검증용(상태코드 없음)."""


def test_detects_openai_context_length_exceeded():
    e = _Err("This model's maximum context length is 8192 tokens. context_length_exceeded", status_code=400)
    assert is_context_overflow(e)
    assert is_recoverable(e)


def test_detects_various_provider_phrases():
    for msg in [
        "maximum context length exceeded",
        "The input is too long for the model",
        "Please reduce the length of the messages",
        "prompt is too long",
        "too many tokens in the request",
        "exceeds the maximum allowed",
    ]:
        assert is_context_overflow(_Err(msg)), msg


def test_detects_code_in_body():
    e = _Err("Bad request", status_code=400, body={"error": {"code": "context_length_exceeded"}})
    assert is_context_overflow(e)


def test_non_context_message_not_overflow():
    e = _Err("invalid api key", status_code=401)
    assert not is_context_overflow(e)


def test_bad_request_by_status_code():
    assert is_bad_request(_Err("malformed", status_code=400))
    assert not is_bad_request(_Err("unauthorized", status_code=401))


def test_bad_request_by_class_name():
    assert is_bad_request(BadRequestError("tools array too long"))


def test_recoverable_includes_plain_400_even_if_phrase_unknown():
    # 문구는 인식 못 해도 400 이면 마지막 수단으로 줄여볼 가치가 있음(원칙 #0)
    e = _Err("some unrecognized 400 reason", status_code=400)
    assert not is_context_overflow(e)
    assert is_recoverable(e)


def test_non_recoverable_for_500_and_network():
    assert not is_recoverable(_Err("internal server error", status_code=500))
    assert not is_recoverable(_Err("connection reset"))
