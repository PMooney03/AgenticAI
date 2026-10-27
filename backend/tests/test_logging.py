import json
import logging

from app.observability.logging import JsonFormatter, request_id_var


def _format(record_kwargs: dict, extra: dict | None = None) -> dict:
    logger = logging.getLogger("test.logger")
    record = logger.makeRecord(
        name="test.logger",
        level=logging.INFO,
        fn=__file__,
        lno=1,
        msg=record_kwargs.get("msg", "event_name"),
        args=(),
        exc_info=None,
        extra=extra,
    )
    return json.loads(JsonFormatter().format(record))


def test_json_formatter_includes_request_id_from_context() -> None:
    token = request_id_var.set("req-123")
    try:
        payload = _format({})
    finally:
        request_id_var.reset(token)
    assert payload["request_id"] == "req-123"
    assert payload["event"] == "event_name"
    assert payload["level"] == "INFO"


def test_json_formatter_merges_extra_fields() -> None:
    payload = _format({}, extra={"model": "m", "llm_latency_ms": 12})
    assert payload["model"] == "m"
    assert payload["llm_latency_ms"] == 12


def test_json_formatter_redacts_secret_like_keys() -> None:
    payload = _format({}, extra={"api_key": "sk-live-123", "token": "abc"})
    assert payload["api_key"] == "[REDACTED]"
    assert payload["token"] == "[REDACTED]"
    assert "sk-live-123" not in json.dumps(payload)
