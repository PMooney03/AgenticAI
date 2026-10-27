import pytest

from app.prompts import PromptNotFoundError, PromptTemplate, get_prompt, list_prompts


def test_chat_system_prompt_is_registered_with_version() -> None:
    prompt = get_prompt("chat-system")
    assert prompt.version == "chat-system-v1"
    assert prompt.variables == frozenset()
    rendered = prompt.render()
    assert "do not invent" in rendered
    assert "Agentic Second Brain" in rendered


def test_versions_are_unique_and_follow_naming_convention() -> None:
    prompts = list_prompts()
    versions = [p.version for p in prompts]
    assert len(versions) == len(set(versions))
    for p in prompts:
        assert p.version.startswith(f"{p.name}-v"), p.version


def test_unknown_prompt_raises() -> None:
    with pytest.raises(PromptNotFoundError):
        get_prompt("does-not-exist")


def test_template_variables_and_render() -> None:
    template = PromptTemplate(
        name="demo", version="demo-v1", template="Context:\n{context}\n\nQuestion: {question}"
    )
    assert template.variables == {"context", "question"}
    assert template.render(context="A", question="B") == "Context:\nA\n\nQuestion: B"


def test_render_reports_missing_variables() -> None:
    template = PromptTemplate(name="demo", version="demo-v1", template="{a} {b}")
    with pytest.raises(KeyError, match="missing variables: \\['b'\\]"):
        template.render(a="x")
