"""
think_tool — explicit reflection
==================================
A no-op tool: it doesn't search, write files, or call any API. Its only
purpose is to give the model a place to write out reasoning as a discrete,
visible step rather than burying it in prose inside a regular message.

This is the same pattern used in Anthropic's and LangChain's open-source
deep-research reference agents: forcing a `think` call after each research
round measurably reduces premature stopping and unsupported leaps, because
the model has to explicitly state "what do I know / what's missing / do I
need another round" before it's allowed to move on.

The return value is intentionally just an acknowledgement — the value of
this tool is entirely in the *input* the model is prompted to produce, which
the UI renders as a distinct "🤔 Reflection" step.
"""

from __future__ import annotations


def think_tool(reflection: str) -> str:
    """Record a structured reflection. Call this after each research round
    (search + optional fetch_full_content) and before deciding to research
    further or write your findings.

    Your reflection should cover:
    - What did I just learn?
    - What's still missing or unconfirmed?
    - Do I have enough to answer, or do I need another search round?

    Args:
        reflection: Your reasoning, as plain text.

    Returns:
        A short acknowledgement (the reflection itself is the useful part,
        already visible in your tool call).
    """
    return "Reflection recorded."
