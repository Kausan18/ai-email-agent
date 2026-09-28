# backend/planner/decision_schema.py
"""
PlannerDecision — the contract object emitted by the planner.

Every downstream module (prompt builder, verifier, dashboard API)
reads from this object. Never change field names — only add new ones.
"""

from __future__ import annotations
from typing import Literal
from pydantic import BaseModel, Field


class PlannerDecision(BaseModel):
    # ── Core decision ──────────────────────────────────────────────────
    reply_required: bool = Field(
        description="Whether a reply should be generated for this email."
    )
    reply_strategy: Literal["generate", "clarify", "no_reply"] = Field(
        description=(
            "generate  → produce a draft reply. "
            "clarify   → ask user for missing context before generating. "
            "no_reply  → no draft produced (newsletters, promos, acks)."
        )
    )

    # ── Memory ─────────────────────────────────────────────────────────
    memory_action: Literal["store_new", "update_existing", "skip"] = Field(
        description=(
            "Mirrors what the memory writer did (or should do). "
            "Logged here for the audit trail and dashboard badge."
        )
    )

    # ── Retrieval ──────────────────────────────────────────────────────
    retrieval_needed: bool = Field(
        description="Whether context retrieval was relevant for this email."
    )
    retrieval_confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence score from RetrievedContext (0.0 if no retrieval).",
    )

    # ── Calendar ───────────────────────────────────────────────────────
    calendar_check_needed: bool = Field(
        description="True when the email involves scheduling and calendar was consulted."
    )

    # ── Constraints ────────────────────────────────────────────────────
    constraints: list[str] = Field(
        default_factory=list,
        description=(
            "Hard rules the prompt builder must inject into the generation prompt. "
            "E.g. 'do not commit to any date or time'."
        ),
    )

    # ── Confidence ─────────────────────────────────────────────────────
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description=(
            "Planner's overall confidence in this decision. "
            "Drives dashboard colour (>=0.7 green, 0.4–0.69 amber, <0.4 red) "
            "and prompt hedging instruction."
        ),
    )

    # ── Generation strategy ────────────────────────────────────────────
    generation_strategy: Literal["fine_tuned"] = Field(
        default="fine_tuned",
        description=(
            "Which generation backend to use. "
            "Always fine_tuned in V2. V3 adds rag and hybrid."
        ),
    )

    # ── Explainability ─────────────────────────────────────────────────
    reasoning: str = Field(
        description=(
            "Human-readable sentence shown in the dashboard planner panel. "
            "Must be non-empty. Written for a non-technical reader."
        )
    )