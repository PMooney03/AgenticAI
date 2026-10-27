import pytest

from app.agent.tools.calculator import CalculatorError, calculate
from app.agent.tools.policy import execute_tool, list_tools
from app.mcp.client import InProcessMCPClient
from app.mcp.server import build_mcp_server


def test_calculator_arithmetic() -> None:
    assert calculate("12 * (3 + 4)") == "84"
    assert calculate("2 + 2") == "4"
    assert calculate("-3.5 + 1") == "-2.5"
    assert calculate("10 // 3") == "3"


def test_calculator_rejects_unsafe_expressions() -> None:
    with pytest.raises(CalculatorError):
        calculate("__import__('os').system('id')")
    with pytest.raises(CalculatorError):
        calculate("abs(1)")
    with pytest.raises(CalculatorError):
        calculate("")
    with pytest.raises(CalculatorError):
        calculate("1" + "+1" * 80)
    with pytest.raises(CalculatorError):
        calculate("1 / 0")
    with pytest.raises(CalculatorError):
        calculate("10 ** 99")


def test_allowlist_exposes_read_only_and_write_tools() -> None:
    by_name = {spec.name: spec for spec in list_tools()}
    assert set(by_name) == {"calculator", "clock", "save_note"}
    assert by_name["calculator"].read_only is True
    assert by_name["calculator"].requires_approval is False
    assert by_name["save_note"].read_only is False
    assert by_name["save_note"].requires_approval is True
    assert all(spec.source == "mcp" for spec in by_name.values())


async def test_execute_tool_goes_through_mcp_and_rejects_unknown() -> None:
    client = InProcessMCPClient(build_mcp_server())
    assert await execute_tool("calculator", {"expression": "2+2"}, client=client) == "4"
    with pytest.raises(ValueError, match="allowlist"):
        await execute_tool("shell", {"cmd": "ls"}, client=client)
    with pytest.raises(ValueError, match="expression"):
        await execute_tool("calculator", {}, client=client)
