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


def test_allowlist_exposes_calculator_and_clock() -> None:
    names = [spec.name for spec in list_tools()]
    assert names == ["calculator", "clock"]
    for spec in list_tools():
        assert spec.read_only is True
        assert spec.requires_approval is False
        assert spec.source == "mcp"


async def test_execute_tool_goes_through_mcp_and_rejects_unknown() -> None:
    client = InProcessMCPClient(build_mcp_server())
    assert await execute_tool("calculator", {"expression": "2+2"}, client=client) == "4"
    with pytest.raises(ValueError, match="allowlist"):
        await execute_tool("shell", {"cmd": "ls"}, client=client)
    with pytest.raises(ValueError, match="expression"):
        await execute_tool("calculator", {}, client=client)
