from fastapi.testclient import TestClient

from app.llm import FakeLLMProvider

PLAN_TOOL = (
    '{"action": "tool", "tool_name": "calculator", "tool_args": {"expression": "12 * (3 + 4)"}}'
)
PLAN_CLOCK = '{"action": "tool", "tool_name": "clock", "tool_args": {}}'


def test_list_tools(client: TestClient) -> None:
    response = client.get("/agent/tools")
    assert response.status_code == 200
    body = response.json()
    names = [tool["name"] for tool in body["tools"]]
    assert names == ["calculator", "clock"]
    assert all(tool["source"] == "mcp" for tool in body["tools"])
    assert all(tool["read_only"] is True for tool in body["tools"])
    assert all(tool["requires_approval"] is False for tool in body["tools"])


def test_trace_404_for_unknown_request(client: TestClient) -> None:
    response = client.get("/agent/trace/does-not-exist")
    assert response.status_code == 404
    assert "trace" in response.json()["detail"].lower()


def test_chat_calculator_path_writes_trace(client: TestClient, fake_llm: FakeLLMProvider) -> None:
    fake_llm.replies = [PLAN_TOOL, "The product is 84."]
    response = client.post(
        "/chat", json={"message": "what is 12 * (3 + 4)?", "use_documents": False}
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["mode"] == "chat"
    assert body["prompt_version"] == "agent-answer-v1"
    assert any("calculator" in step["label"] for step in body["workflow"])
    assert body["retrieval"] is None

    trace = client.get(f"/agent/trace/{body['request_id']}")
    assert trace.status_code == 200
    payload = trace.json()
    assert payload["request_id"] == body["request_id"]
    assert "call_tool" in payload["nodes_visited"]
    assert payload["tools"] == ["calculator"]
    assert payload["retrieved_chunks"] == 0
    # No document text, question, or planner JSON in the inspectable trace.
    dumped = trace.text.lower()
    assert "12 * (3 + 4)" not in dumped
    assert "handbook" not in dumped


def test_chat_clock_path_goes_through_mcp(client: TestClient, fake_llm: FakeLLMProvider) -> None:
    fake_llm.replies = [PLAN_CLOCK, "The local time is shown above."]
    response = client.post("/chat", json={"message": "what time is it?", "use_documents": False})
    assert response.status_code == 200, response.text
    body = response.json()
    assert any("clock" in step["label"] for step in body["workflow"])
    trace = client.get(f"/agent/trace/{body['request_id']}")
    assert trace.json()["tools"] == ["clock"]
