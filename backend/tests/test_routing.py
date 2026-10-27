from app.agent.routing import (
    decide_plan,
    parse_plan,
    route_after_evaluate,
    route_after_plan,
)


def test_parse_plan_reads_json_and_fences() -> None:
    inner = '{"action": "tool", "tool_name": "calculator", "tool_args": {"expression": "2+2"}}'
    decision = parse_plan(f"```json\n{inner}\n```")
    assert decision.action == "tool"
    assert decision.tool_name == "calculator"
    assert decision.tool_args == {"expression": "2+2"}


def test_parse_plan_invalid_becomes_answer() -> None:
    assert parse_plan("not json").action == "answer"
    assert parse_plan("[]").action == "answer"
    assert parse_plan('{"action": "explode"}').action == "answer"


def test_decide_plan_falls_back_to_retrieve_when_documents_allowed() -> None:
    assert decide_plan("sure, I'll think", use_documents=True).action == "retrieve"
    assert decide_plan("sure, I'll think", use_documents=False).action == "answer"


def test_decide_plan_clamps_retrieve_without_documents() -> None:
    raw = '{"action": "retrieve", "tool_name": null, "tool_args": {}}'
    assert decide_plan(raw, use_documents=False).action == "answer"


def test_decide_plan_rejects_unknown_tool() -> None:
    raw = '{"action": "tool", "tool_name": "shell", "tool_args": {"cmd": "ls"}}'
    decision = decide_plan(raw, use_documents=False)
    assert decision.action == "answer"
    assert decision.tool_name is None


def test_route_after_plan_honours_step_budget() -> None:
    under_budget = {"next_action": "retrieve", "step_count": 1, "max_steps": 3}
    at_budget = {"next_action": "retrieve", "step_count": 3, "max_steps": 3}
    assert route_after_plan(under_budget) == "retrieve"
    assert route_after_plan(at_budget) == "answer"
    assert route_after_plan({"next_action": "answer", "step_count": 3, "max_steps": 3}) == "answer"
    assert route_after_plan({"next_action": "nope"}) == "answer"


def test_route_after_evaluate_loops_only_without_evidence() -> None:
    budget = {"step_count": 1, "max_steps": 3}
    with_chunks = {**budget, "chunks": [{"id": "1"}], "tool_results": []}
    with_tool = {**budget, "chunks": [], "tool_results": [{"name": "calculator"}]}
    retrieve_only = {**budget, "chunks": [], "tool_results": [], "attempted": ["retrieve"]}
    tool_only = {**budget, "chunks": [], "tool_results": [], "attempted": ["tool"]}
    both = {**budget, "chunks": [], "tool_results": [], "attempted": ["retrieve", "tool"]}
    exhausted = {"step_count": 3, "max_steps": 3, "attempted": ["retrieve"]}
    assert route_after_evaluate(with_chunks) == "answer"
    assert route_after_evaluate(with_tool) == "answer"
    assert route_after_evaluate(retrieve_only) == "plan"
    assert route_after_evaluate(tool_only) == "plan"
    assert route_after_evaluate(both) == "answer"
    assert route_after_evaluate(exhausted) == "answer"
