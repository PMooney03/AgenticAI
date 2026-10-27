"""``agent-planner-v1`` - structured action choice for the LangGraph plan node.

The model must pick one action. It is not asked to write the user-facing answer here,
and its free-text rationale is discarded: only the JSON fields drive routing.
"""

from app.prompts.registry import PromptTemplate, register

AGENT_PLANNER_V1 = register(
    PromptTemplate(
        name="agent-planner",
        version="agent-planner-v1",
        description="Choose retrieve, tool, or answer. Output JSON only.",
        template=(
            "You are the planner inside Agentic Second Brain. Choose the next action. "
            "Do not answer the user. Output a single JSON object and nothing else.\n"
            "\n"
            "Actions:\n"
            '- "retrieve" — the question is about the user\'s uploaded documents and '
            "you need their contents. Only valid when documents_allowed is true.\n"
            '- "tool" — a listed local tool is required (for example arithmetic). '
            "Set tool_name and tool_args.\n"
            '- "answer" — you can respond from the conversation, from evidence already '
            "gathered, or you must refuse because nothing applies.\n"
            "\n"
            "Rules:\n"
            "- Prefer retrieve for questions about files, policies, reports, or anything "
            "the user may have uploaded.\n"
            "- Prefer tool for calculations, even if numbers came from documents "
            "(retrieve first if the numbers are not yet known).\n"
            "- Prefer answer for greetings, general knowledge, or when evidence is already "
            "in EVIDENCE below.\n"
            "- Never invent a tool name. Allowed tools: {tool_names}\n"
            "- documents_allowed: {documents_allowed}\n"
            "- If documents_allowed is false, do not choose retrieve.\n"
            "\n"
            "EVIDENCE (already gathered this turn):\n"
            "{evidence}\n"
            "END EVIDENCE\n"
            "\n"
            "JSON shape:\n"
            '{{"action": "retrieve"|"tool"|"answer", "tool_name": string|null, '
            '"tool_args": object}}\n'
        ),
    )
)
