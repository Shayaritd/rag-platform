"""
Structured output schemas
==========================
Pydantic models passed as `response_format=` to deep-agent subagents. The
LLM is constrained to return JSON matching these shapes, which makes the
researcher's and critic's output reliably parseable by the UI instead of
free-form prose.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResearchFindings(BaseModel):
    """Structured findings returned by a researcher subagent."""

    summary: str = Field(description="2-4 sentence summary of what was found")
    key_points: list[str] = Field(
        default_factory=list,
        description="Bullet list of the most important individual facts/findings",
    )
    confidence: float = Field(
        description="Confidence in these findings, from 0.0 (low) to 1.0 (high)"
    )
    sources: list[str] = Field(
        default_factory=list, description="Source URLs that support the findings"
    )
    knowledge_gaps: list[str] = Field(
        default_factory=list,
        description="Open questions or gaps this research did not resolve",
    )


class CritiqueResult(BaseModel):
    """Structured self-critique returned by the critic/observer subagent."""

    verdict: str = Field(
        description="One of: 'approved', 'needs_more_research', 'unsupported_claims'"
    )
    unsupported_claims: list[str] = Field(
        default_factory=list,
        description="Claims in the draft answer that are not backed by a cited source",
    )
    missing_citations: list[str] = Field(
        default_factory=list,
        description="Statements that should have a citation but don't",
    )
    notes: str = Field(default="", description="Free-text notes for the supervisor")
