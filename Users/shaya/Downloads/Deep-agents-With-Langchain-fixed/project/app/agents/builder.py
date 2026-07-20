"""
Multi-agent builder
=====================
Assembles a Supervisor / Researcher(s) / Critic architecture on top of the
`deepagents` library, instead of hand-rolling a parallel LangGraph graph.

Why build it this way:
- `deepagents.create_deep_agent` already gives us planning (`write_todos`),
  context offloading (virtual file system), and delegation (`task` tool +
  subagents) for free, on top of LangGraph. Re-implementing those primitives
  by hand would duplicate working infrastructure, not improve on it.
- A "Planner/Researcher/Observer" pattern maps directly onto deep-agent
  subagents: the **main agent IS the supervisor/planner**, the
  **researcher subagent** does the deep-dive web research (context
  quarantine — its noisy search context never pollutes the supervisor's),
  and the **critic subagent** plays the observer role, reviewing the
  supervisor's draft before it's sent to the user.

This module exposes a single entry point, `build_agent(cfg)`, used by the
Streamlit app. It mirrors the shape of the project's existing
`build_agent` (same cfg keys, same backend choices) so it's a drop-in
upgrade rather than a rewrite.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st
from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend, StateBackend, StoreBackend
from deepagents.backends.utils import create_file_data

from app.agents.prompts import CRITIC_PROMPT, RESEARCHER_PROMPT, SUPERVISOR_PROMPT
from app.agents.schemas import CritiqueResult, ResearchFindings
from app.tools.reflection import think_tool
from app.tools.search import fetch_full_content, internet_search

ROOT_DIR = Path(__file__).resolve().parent.parent.parent
DEMO_DIR = ROOT_DIR / "deepagentsdemo"

# Tools every role gets access to for quick checks; researchers additionally
# get the search tools, defined below.
BASE_TOOLS = [think_tool]
RESEARCH_TOOLS = [internet_search, fetch_full_content, think_tool]


def load_agents_md() -> str:
    path = DEMO_DIR / "projects" / "AGENTS.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def load_skill_seed_files() -> dict:
    """Read every file under deepagentsdemo/skills/ into in-state file data
    so a StateBackend agent can discover and read skills."""
    files = {}
    skills_root = DEMO_DIR / "skills"
    if skills_root.exists():
        for f in skills_root.rglob("*.md"):
            virtual = "/skills/" + f.relative_to(skills_root).as_posix()
            files[virtual] = create_file_data(f.read_text(encoding="utf-8"))
    return files


def _build_subagents(num_researchers: int) -> list[dict]:
    """Build the researcher(s) + critic subagent specs.

    `num_researchers` > 1 just registers additional differently-named
    researcher subagents (e.g. researcher_1, researcher_2) with identical
    instructions — this lets the supervisor fan a question out across
    several isolated-context researchers and gives the UI something
    concrete to show as "parallel researchers" without requiring true
    concurrent execution support from the runtime.
    """
    subagents = []
    names = (
        ["researcher"]
        if num_researchers <= 1
        else [f"researcher_{i + 1}" for i in range(num_researchers)]
    )
    for name in names:
        subagents.append(
            {
                "name": name,
                "description": (
                    "Delegate a single, specific research question to this "
                    "subagent. It searches the web (snippets-first), "
                    "reflects with think_tool, and returns structured "
                    "ResearchFindings (summary, key_points, confidence, "
                    "sources, knowledge_gaps)."
                ),
                "system_prompt": RESEARCHER_PROMPT,
                "tools": RESEARCH_TOOLS,
                "response_format": ResearchFindings,
            }
        )

    subagents.append(
        {
            "name": "critic",
            "description": (
                "Review a draft answer plus the research findings behind "
                "it for unsupported claims or missing citations BEFORE the "
                "supervisor sends the answer to the user. Give it the "
                "draft text and the findings as input."
            ),
            "system_prompt": CRITIC_PROMPT,
            "tools": [think_tool],
            "response_format": CritiqueResult,
        }
    )
    return subagents


def build_agent(cfg: dict[str, Any]):
    """Create the supervisor deep agent wired up per the sidebar config.

    Returns:
        (agent, seed_files) — `seed_files` must be passed as `files=` in the
        invoke payload when using StateBackend (it has no disk to read
        AGENTS.md / skills from, so they're seeded into per-thread state).
    """
    seed_files: dict[str, Any] = {}

    # --- backend selection (where files/memory live) ------------------------
    if cfg["backend"] == "StateBackend (in-state, per thread)":
        backend = StateBackend()
        if cfg["use_agents_md"]:
            seed_files["/projects/AGENTS.md"] = create_file_data(load_agents_md())
        if cfg["use_skills"]:
            seed_files.update(load_skill_seed_files())
        memory_paths = ["/projects/AGENTS.md"] if cfg["use_agents_md"] else None

    elif cfg["backend"] == "FilesystemBackend (real disk)":
        backend = FilesystemBackend(root_dir=str(DEMO_DIR), virtual_mode=True)
        memory_paths = ["/projects/AGENTS.md"] if cfg["use_agents_md"] else None

    else:  # StoreBackend (cross-thread memory)
        store = st.session_state.store
        backend = StoreBackend(store=store, namespace=lambda rt: ("memories",))
        if not st.session_state.get("store_seeded"):
            if cfg["use_agents_md"]:
                store.put(
                    ("memories",),
                    "/projects/AGENTS.md",
                    create_file_data(load_agents_md()),
                )
            if cfg["use_skills"]:
                for path, data in load_skill_seed_files().items():
                    store.put(("memories",), path, data)
            st.session_state.store_seeded = True
        memory_paths = ["/projects/AGENTS.md"] if cfg["use_agents_md"] else None

    # --- multi-agent team: supervisor (main) + researcher(s) + critic ------
    subagents = _build_subagents(cfg.get("num_researchers", 1))

    kwargs: dict[str, Any] = dict(
        model=cfg["model"],
        tools=BASE_TOOLS,
        system_prompt=cfg["system_prompt"],
        backend=backend,
        subagents=subagents,
        checkpointer=st.session_state.checkpointer,
    )
    if cfg["use_skills"]:
        kwargs["skills"] = ["/skills/"]
    if memory_paths:
        kwargs["memory"] = memory_paths
    if cfg["backend"].startswith("StoreBackend"):
        kwargs["store"] = st.session_state.store

    return create_deep_agent(**kwargs), seed_files


DEFAULT_SUPERVISOR_PROMPT = SUPERVISOR_PROMPT
