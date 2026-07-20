"""
Deep Agents Research Console — Streamlit app
==============================================
Run with:  streamlit run streamlit_app.py

About the .env loading and the "printed 7 times" symptom
-----------------------------------------------------------
This isn't actually a duplicate-load bug. Streamlit re-runs the *entire*
script top to bottom on every interaction (every keystroke in a text_area,
every button click, every chat message) — and during local development,
`streamlit run` also has a file-watcher that restarts the script process
whenever it detects a saved change to this file. Each of those is either a
genuinely fresh process or a fresh session, so each one legitimately prints
once. The `st.session_state` guard below is correct and sufficient — it
prevents *re*-loading .env on every rerun within one browser session. If
you still see multiple prints, check for multiple browser tabs/sessions
open against the same app (each gets independent session_state), or note
that file-watcher restarts during active editing are expected, not a bug.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).parent

# --- Load .env exactly once per Streamlit session ---------------------------
if "env_loaded" not in st.session_state:
    env_path = ROOT_DIR / ".env"
    if env_path.exists():
        load_dotenv(env_path, override=True)
        print(f"✅ Loaded .env from: {env_path}")
    else:
        print("⚠️ No .env file found! Copy .env.example to .env and fill in your keys.")
    st.session_state.env_loaded = True

# Some setups never set OPENAI_API_KEY but deepagents' default provider
# profile still probes for it at import time in some code paths — a
# harmless placeholder avoids a spurious "key not found" error for people
# who aren't using OpenAI at all.
if not os.getenv("OPENAI_API_KEY"):
    os.environ["OPENAI_API_KEY"] = "sk-dummy-key-for-openrouter"

from langgraph.checkpoint.memory import MemorySaver
from langgraph.store.memory import InMemoryStore

from app.agents.builder import DEFAULT_SUPERVISOR_PROMPT, build_agent
from app.export.exporters import ReportData, to_html, to_markdown, to_pdf_bytes
from app.storage import db

db.init_db()

# ---------------------------------------------------------------------------
# MODEL CHOICES
# ---------------------------------------------------------------------------
# Ordering reflects *actually verified* free-tier reliability for tool-calling
# agents, not vendor marketing claims:
#
# - Gemini 2.0 Flash: generous free quota, but shared across ALL your apps —
#   if you've used it elsewhere today you may hit 429 RESOURCE_EXHAUSTED
#   immediately. There is no code fix for an exhausted daily quota; only
#   waiting for reset or switching provider helps.
# - Groq qwen3-32b: fast, but its free tier caps at 6,000 tokens PER MINUTE
#   (not per request) — this agent's system prompt + tool schemas + research
#   history can exceed that on a single call. llama-3.1-8b-instant has a much
#   higher practical free-tier ceiling for this kind of multi-tool agent, so
#   it's listed first as the more reliable Groq option.
# - OpenRouter ":free" models vary in whether tool-calling *actually* works
#   end-to-end (vendor docs claim support; real-world behavior is mixed).
#   llama-3.3-70b-instruct:free has the most consistent track record for
#   agentic/tool-calling workloads of the free OpenRouter models; Gemma
#   variants were removed from this list after inconsistent tool-call
#   support in practice.
MODEL_CHOICES = [
    "groq:llama-3.1-8b-instant",
    "groq:qwen/qwen3-32b",
    "google_genai:gemini-2.0-flash",
    "google_genai:gemini-1.5-flash",
    "openrouter:meta-llama/llama-3.3-70b-instruct:free",
    "openrouter:deepseek/deepseek-chat-v3.1:free",
]

# Auto-fallback order when the selected model fails. Deliberately does NOT
# include google_genai:gemini-1.5-pro (50 req/day free cap — too easy to
# exhaust as a silent fallback) or any model requiring a key you haven't
# configured (checked at call time, see `available_fallback_models`).
FALLBACK_MODELS = [
    "groq:llama-3.1-8b-instant",
    "google_genai:gemini-2.0-flash",
    "openrouter:meta-llama/llama-3.3-70b-instruct:free",
    "groq:qwen/qwen3-32b",
]

# Rough free-tier ceilings used for the pre-flight token check, in tokens.
# These are the binding TPM/per-call constraints reported by each provider's
# free tier as of testing — not academic, just enough to fail fast with a
# clear message instead of waiting for the API to reject the call.
MODEL_TOKEN_LIMITS = {
    "groq:qwen/qwen3-32b": 6_000,
    "groq:llama-3.1-8b-instant": 6_000,
    "google_genai:gemini-2.0-flash": 1_000_000,
    "google_genai:gemini-1.5-flash": 1_000_000,
    "openrouter:meta-llama/llama-3.3-70b-instruct:free": 100_000,
    "openrouter:deepseek/deepseek-chat-v3.1:free": 100_000,
}
DEFAULT_TOKEN_LIMIT = 32_000

PHASES = ["Planning", "Researching", "Reviewing", "Done"]


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token for English text).

    Deliberately NOT using tiktoken here: tiktoken downloads its BPE file
    from openaipublic.blob.core.windows.net on first use, which fails in any
    network-restricted environment (corporate proxies, sandboxes, offline
    dev). For the purpose of this app — a pre-flight guard against Groq's
    6K TPM free-tier ceiling, not exact billing — a dependency-free
    heuristic is more robust than an exact count that might not be
    computable at all.
    """
    return max(1, len(text) // 4)


def available_fallback_models(preferred: list[str]) -> list[str]:
    """Filter a model list down to ones whose required API key is actually
    set, so the fallback loop doesn't waste a round-trip discovering that."""
    out = []
    for m in preferred:
        provider = m.split(":")[0]
        key_name = {
            "groq": "GROQ_API_KEY",
            "google_genai": "GOOGLE_API_KEY",
            "openrouter": "OPENROUTER_API_KEY",
            "openai": "OPENAI_API_KEY",
        }.get(provider)
        if key_name is None or os.getenv(key_name):
            out.append(m)
    return out


# ---------------------------------------------------------------------------
# RENDERING HELPERS
# ---------------------------------------------------------------------------
def extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for block in content:
            if isinstance(block, dict) and block.get("type") == "text":
                parts.append(block.get("text", ""))
            elif isinstance(block, str):
                parts.append(block)
        return "\n".join(parts)
    return str(content)


def infer_phase(tool_name: str | None) -> str | None:
    if tool_name == "write_todos":
        return "Planning"
    if tool_name in ("task",):
        return "Researching"
    if tool_name in ("internet_search", "fetch_full_content", "think_tool"):
        return "Researching"
    return None


def render_steps(messages, live_status=None) -> list[dict]:
    todo_snapshots = []
    for msg in messages:
        msg_type = getattr(msg, "type", "")
        if msg_type == "ai" and getattr(msg, "tool_calls", None):
            for tc in msg.tool_calls:
                name, args = tc["name"], tc["args"]

                if live_status is not None:
                    phase = infer_phase(name)
                    if phase:
                        live_status.update(label=f"🧠 {phase}…")

                if name == "write_todos":
                    todos = args.get("todos", [])
                    todo_snapshots.append(todos)
                    with st.expander("📋 Planning — write_todos", expanded=False):
                        for todo in todos:
                            icon = {
                                "pending": "⬜",
                                "in_progress": "🔄",
                                "completed": "✅",
                            }.get(todo.get("status"), "⬜")
                            st.markdown(f"{icon} {todo.get('content', todo)}")

                elif name == "task":
                    subagent = args.get("subagent_type", "task")
                    icon = "🕵️" if "research" in subagent else (
                        "🧐" if subagent == "critic" else "🤖"
                    )
                    with st.expander(f"{icon} Delegated to — {subagent}", expanded=False):
                        st.markdown(args.get("description", ""))

                elif name == "think_tool":
                    with st.expander("🤔 Reflection", expanded=False):
                        st.markdown(args.get("reflection", ""))

                elif name == "internet_search":
                    with st.expander(
                        f"🔎 Search (snippets) — \u201c{args.get('query', '')}\u201d",
                        expanded=False,
                    ):
                        st.json(args)

                elif name == "fetch_full_content":
                    with st.expander(
                        f"📄 Full fetch — {args.get('url', '')}", expanded=False
                    ):
                        st.json(args)

                elif name in (
                    "write_file", "edit_file", "read_file", "ls", "glob", "grep",
                ):
                    label = args.get("file_path") or args.get("path") or ""
                    with st.expander(
                        f"📁 File system — {name} {label}", expanded=False
                    ):
                        st.json(args)
                else:
                    with st.expander(f"🛠️ Tool — {name}", expanded=False):
                        st.json(args)

        elif msg_type == "tool":
            text = extract_text(msg.content)
            if len(text) > 700:
                text = text[:700] + " …(truncated)"
            with st.expander(
                f"↩️ Result — {getattr(msg, 'name', 'tool')}", expanded=False
            ):
                st.code(text)

    return todo_snapshots


def render_files(files: dict):
    if not files:
        return
    with st.expander(f"🗂️ Virtual files in state ({len(files)})", expanded=False):
        for path, data in files.items():
            content = data.get("content", "") if isinstance(data, dict) else str(data)
            st.markdown(f"**`{path}`**")
            st.code(content[:1500] + (" …(truncated)" if len(content) > 1500 else ""))


def render_export_buttons(query: str, answer: str, model: str, sources: list[str], files: dict, key_prefix: str):
    report = ReportData(
        query=query,
        answer=answer,
        model=model,
        created_at=datetime.now(timezone.utc),
        sources=sources,
        files={p: (d.get("content", "") if isinstance(d, dict) else str(d)) for p, d in files.items()},
    )
    col1, col2, col3 = st.columns(3)
    col1.download_button(
        "⬇️ Markdown", to_markdown(report),
        file_name="research_report.md", mime="text/markdown",
        use_container_width=True, key=f"{key_prefix}_md",
    )
    col2.download_button(
        "⬇️ HTML", to_html(report),
        file_name="research_report.html", mime="text/html",
        use_container_width=True, key=f"{key_prefix}_html",
    )
    col3.download_button(
        "⬇️ PDF", to_pdf_bytes(report),
        file_name="research_report.pdf", mime="application/pdf",
        use_container_width=True, key=f"{key_prefix}_pdf",
    )


def extract_sources_from_messages(messages) -> list[str]:
    import re
    sources: list[str] = []
    for msg in messages:
        if getattr(msg, "type", "") == "tool":
            text = extract_text(msg.content)
            for url in re.findall(r"https?://[^\s\"'\)\]]+", text):
                if url not in sources:
                    sources.append(url)
    return sources[:20]


def classify_error(error_str: str) -> str:
    """Bucket a provider error into a category the UI can speak to plainly.
    Returns one of: 'quota', 'token_limit', 'auth', 'not_found', 'other'.
    """
    s = error_str.lower()
    if "429" in s or "resource_exhausted" in s or "quota" in s:
        return "quota"
    if "413" in s or "too large" in s or "tokens per minute" in s or "tpm" in s:
        return "token_limit"
    if "api key" in s or "credentials" in s or "401" in s or "unauthorized" in s:
        return "auth"
    if "404" in s or "not found" in s or "does not exist" in s:
        return "not_found"
    return "other"


def invoke_with_fallback(cfg: dict, payload: dict, config: dict, fallback_models: list[str], status):
    """Try multiple models in sequence until one works.

    Critically, this REBUILDS the agent for each model in the fallback list
    (via build_agent({**cfg, "model": model_name})) rather than reusing a
    single pre-built agent. Reusing one agent object across "different"
    models doesn't actually change which LLM gets called — the model is
    baked in at construction time — which was the root cause of fallback
    silently not working (it kept calling the same underlying model under
    different cosmetic status labels).

    Returns:
        (result, used_model, seed_files) on success, or (None, None, None)
        if every model in the list failed.
    """
    last_error = None
    last_category = "other"
    tried_models = []

    for model_name in fallback_models:
        tried_models.append(model_name)
        try:
            status.update(label=f"🔄 Trying {model_name.split(':')[-1]}…", state="running")

            agent, seed_files = build_agent({**cfg, "model": model_name})
            call_payload = dict(payload)
            if seed_files:
                call_payload["files"] = seed_files

            # Pre-flight token check for models with a known, tight free-tier
            # ceiling (e.g. Groq's 6K TPM) — fail fast with a clear message
            # rather than waiting for the API's 413.
            limit = MODEL_TOKEN_LIMITS.get(model_name, DEFAULT_TOKEN_LIMIT)
            prompt_text = call_payload["messages"][-1]["content"]
            sys_prompt_text = cfg.get("system_prompt", "")
            est = estimate_tokens(prompt_text) + estimate_tokens(sys_prompt_text)
            # The agent's own tool schemas + subagent prompts add real
            # overhead beyond the visible system prompt; pad the estimate
            # rather than under-count.
            est = int(est * 1.6)
            if est > limit:
                status.update(
                    label=f"⚠️ {model_name.split(':')[-1]} likely too small "
                          f"for this request (~{est} est. tokens > {limit} limit), skipping…",
                    state="running",
                )
                last_error = (
                    f"Estimated ~{est} tokens exceeds {model_name}'s "
                    f"~{limit}-token free-tier ceiling for a single call."
                )
                last_category = "token_limit"
                continue

            result = agent.invoke(call_payload, config=config)
            return result, model_name, seed_files

        except Exception as e:
            last_error = e
            category = classify_error(str(e))
            last_category = category

            if category == "quota":
                status.update(
                    label=f"⚠️ {model_name.split(':')[-1]} quota exhausted, "
                          f"switching to next model…", state="running",
                )
            elif category == "token_limit":
                status.update(
                    label=f"⚠️ {model_name.split(':')[-1]} hit its token/size "
                          f"limit, trying a model with more headroom…", state="running",
                )
            elif category == "auth":
                # No point trying this provider again this session, but DO
                # keep trying other providers rather than aborting entirely.
                status.update(
                    label=f"⚠️ {model_name.split(':')[-1]} auth failed "
                          f"(check its API key in .env), trying next…", state="running",
                )
            elif category == "not_found":
                status.update(
                    label=f"⚠️ {model_name.split(':')[-1]} not available, trying next…",
                    state="running",
                )
            else:
                status.update(
                    label=f"⚠️ {model_name.split(':')[-1]} failed, trying next…",
                    state="running",
                )
            continue

    status.update(label="❌ All models failed", state="error")

    friendly = {
        "quota": "Every provider's free quota looks exhausted right now.",
        "token_limit": "This request is too large for the free-tier models tried.",
        "auth": "One or more API keys look invalid or missing.",
        "not_found": "One or more selected models aren't available from their provider.",
        "other": "All providers returned an error.",
    }.get(last_category, "All providers returned an error.")

    st.error(f"🚫 {friendly}\n\nLast error: {last_error}")
    st.markdown(
        "**What to try:**\n"
        "1. ⏳ Wait a few minutes if this is a quota (429) error — daily/per-minute quotas reset on their own.\n"
        "2. ✂️ Try a shorter question if this is a token-limit (413) error.\n"
        "3. 🔑 Double-check the relevant key in `.env` if this is an auth error.\n"
        "4. 🔄 Manually pick a different model from the sidebar.\n"
    )
    st.info(f"📋 Tried: {', '.join(m.split(':')[-1] for m in tried_models)}")
    return None, None, None


# ---------------------------------------------------------------------------
# STREAMLIT APP
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Deep Agents Research Console", page_icon="🧠", layout="wide")
st.title("🧠 Deep Agents Research Console")
st.caption(
    "Supervisor → Researcher(s) → Critic multi-agent team · Live phase tracking · "
    "SQLite session history · Skills & AGENTS.md context · Swappable backends · "
    "Markdown / HTML / PDF export · Auto-model fallback"
)

# --- Session state init ------------------------------------------------------
if "checkpointer" not in st.session_state:
    st.session_state.checkpointer = MemorySaver()
if "store" not in st.session_state:
    st.session_state.store = InMemoryStore()
if "thread_id" not in st.session_state:
    st.session_state.thread_id = str(uuid.uuid4())
if "history" not in st.session_state:
    st.session_state.history = []
if "session_created" not in st.session_state:
    st.session_state.session_created = False
if "current_model" not in st.session_state:
    st.session_state.current_model = MODEL_CHOICES[0]

# --- Sidebar: Agent configuration --------------------------------------------
with st.sidebar:
    st.header("⚙️ Agent configuration")

    model = st.selectbox(
        "Model",
        MODEL_CHOICES,
        index=0,
        help="Select a model. 'groq:' models are fastest with free tier.",
    )

    num_researchers = st.slider(
        "Researcher subagents", min_value=1, max_value=3, value=1,
    )

    backend = st.radio(
        "Backend (where files/memory live)",
        [
            "StateBackend (in-state, per thread)",
            "FilesystemBackend (real disk)",
            "StoreBackend (cross-thread store)",
        ],
    )

    st.subheader("Features")
    use_agents_md = st.checkbox("Load AGENTS.md context (memory=)", value=True)
    use_skills = st.checkbox("Skills (/skills/)", value=True)

    with st.expander("🧑‍🤝‍🧑 Multi-agent team", expanded=False):
        st.markdown(
            "- **Supervisor** (main agent) — plans with `write_todos`, delegates, synthesizes.\n"
            "- **researcher** *(×{n})* — snippets-first web search, `think_tool` reflection.\n"
            "- **critic** — reviews draft for unsupported claims or missing citations.".format(n=num_researchers)
        )

    system_prompt = st.text_area("Supervisor system prompt", DEFAULT_SUPERVISOR_PROMPT, height=220)

    st.divider()
    st.caption(f"🧵 Thread: `{st.session_state.thread_id[:8]}…`")
    col1, col2 = st.columns(2)
    if col1.button("🆕 New session", use_container_width=True):
        st.session_state.thread_id = str(uuid.uuid4())
        st.session_state.history = []
        st.session_state.session_created = False
        st.rerun()
    if col2.button("🗑️ Reset all", use_container_width=True):
        for k in ("checkpointer", "store", "store_seeded", "thread_id", "history", "session_created", "current_model"):
            st.session_state.pop(k, None)
        st.rerun()

    # --- API Key Status & token awareness -----------------------------------
    st.divider()
    st.header("📊 Status & usage")
    st.caption("Key presence (not validity — an invalid key still shows ✅ here):")
    st.info(f"{'✅' if os.getenv('OPENROUTER_API_KEY') else '❌'} OpenRouter")
    st.info(f"{'✅' if os.getenv('TAVILY_API_KEY') else '❌'} Tavily")
    st.info(f"{'✅' if os.getenv('GROQ_API_KEY') else '❌'} Groq")
    st.info(f"{'✅' if os.getenv('GOOGLE_API_KEY') else '❌'} Google (Gemini)")

    st.caption(f"📌 Selected: `{model}`")
    if st.session_state.get("current_model") and st.session_state.current_model != model:
        st.caption(f"↪️ Last actually used: `{st.session_state.current_model}` (fallback occurred)")

    # Honest token estimate for the CURRENT system prompt against the
    # selected model's known free-tier ceiling. This is a rough, local
    # estimate (see estimate_tokens docstring) — NOT a live "remaining
    # quota" figure. No provider exposes remaining free-tier quota without
    # an authenticated usage-API call per key, which isn't wired up here;
    # showing a fabricated number would be worse than showing nothing.
    sys_tokens = estimate_tokens(system_prompt)
    limit = MODEL_TOKEN_LIMITS.get(model, DEFAULT_TOKEN_LIMIT)
    pct = min(100, int(100 * sys_tokens / limit))
    st.caption(f"🧮 System prompt ≈ {sys_tokens:,} tokens (rough estimate)")
    st.progress(pct / 100, text=f"{pct}% of {model.split(':')[-1]}'s ~{limit:,}-token free-tier ceiling")
    if pct > 70:
        st.warning(
            "Your system prompt alone is using most of this model's free-tier "
            "headroom — add a long question on top and you may hit a 413/429. "
            "Consider a shorter system prompt or a higher-ceiling model."
        )

    # --- Session history (SQLite) -------------------------------------------
    st.divider()
    st.header("🗂️ Research history")
    past_sessions = db.list_sessions(limit=30)
    if not past_sessions:
        st.caption("No past sessions yet — your first query will start one.")
    else:
        for s in past_sessions:
            is_current = s.session_id == st.session_state.thread_id
            label = f"{'🟢 ' if is_current else ''}{s.title or '(untitled)'}"
            sub = datetime.fromtimestamp(s.updated_at).strftime("%b %d, %H:%M")
            with st.container(border=True):
                st.markdown(f"**{label}**")
                st.caption(f"{sub} · {s.model.split(':')[-1]}")
                bcol1, bcol2 = st.columns(2)
                if bcol1.button("Open", key=f"open_{s.session_id}", use_container_width=True, disabled=is_current):
                    st.session_state.thread_id = s.session_id
                    st.session_state.session_created = True
                    msgs = db.get_messages(s.session_id)
                    st.session_state.history = [(m.role, m.content, None, None) for m in msgs]
                    st.rerun()
                if bcol2.button("Delete", key=f"del_{s.session_id}", use_container_width=True):
                    db.delete_session(s.session_id)
                    st.rerun()

# --- Build agent config ------------------------------------------------------
cfg = {
    "model": model,
    "backend": backend,
    "use_agents_md": use_agents_md,
    "use_skills": use_skills,
    "num_researchers": num_researchers,
    "system_prompt": system_prompt,
}

cfg_key = str(sorted(cfg.items()))
if st.session_state.get("cfg_key") != cfg_key:
    st.session_state.agent, st.session_state.seed_files = build_agent(cfg)
    st.session_state.cfg_key = cfg_key
    st.session_state.current_model = model

# --- Replay chat history -----------------------------------------------------
for i, (role, text, steps, files) in enumerate(st.session_state.history):
    with st.chat_message(role):
        if steps:
            render_steps(steps)
        st.markdown(text)
        if files:
            render_files(files)
        if role == "assistant":
            render_export_buttons(
                query=st.session_state.history[i - 1][1] if i > 0 else "",
                answer=text,
                model=model,
                sources=extract_sources_from_messages(steps or []),
                files=files or {},
                key_prefix=f"hist_{i}",
            )

# --- Chat input / agent invocation -------------------------------------------
if prompt := st.chat_input("Ask me anything — research, code, AWS, LangGraph…"):
    if not st.session_state.session_created:
        db.create_session(st.session_state.thread_id, title=prompt, model=model, backend=backend)
        st.session_state.session_created = True

    db.add_message(st.session_state.thread_id, "user", prompt)

    with st.chat_message("user"):
        st.markdown(prompt)
    st.session_state.history.append(("user", prompt, None, None))

    payload = {"messages": [{"role": "user", "content": prompt}]}
    if st.session_state.seed_files:
        payload["files"] = st.session_state.seed_files

    config = {
        "configurable": {"thread_id": st.session_state.thread_id},
        "recursion_limit": 100,
    }

    todo_snapshots: list = []
    used_model = None
    with st.chat_message("assistant"):
        # Only fall back to models whose API key is actually present —
        # otherwise the loop wastes time discovering that at call time.
        fallback_list = [model] + [
            m for m in available_fallback_models(FALLBACK_MODELS) if m != model
        ]

        with st.status("🧠 Planning…", expanded=True) as status:
            try:
                result, used_model, used_seed_files = invoke_with_fallback(
                    cfg, payload, config, fallback_list, status,
                )

                if result is None:
                    db.touch_session(st.session_state.thread_id, status="error")
                    st.stop()

                # The agent that actually answered may differ from the one
                # built for the sidebar's selected model (that's the whole
                # point of fallback) — keep seed_files in sync with whichever
                # model ran, since they were (re)computed per build_agent call.
                st.session_state.seed_files = used_seed_files or {}

                if used_model and used_model != model:
                    st.session_state.current_model = used_model
                    status.update(label=f"✅ Used {used_model.split(':')[-1]}", state="running")

            except Exception as e:
                status.update(label="❌ Error", state="error")
                st.error(f"❌ Agent error: {e}")
                db.touch_session(st.session_state.thread_id, status="error")
                st.stop()

            all_msgs = result["messages"]
            turn_start = max(
                (i for i, m in enumerate(all_msgs) if getattr(m, "type", "") == "human"),
                default=0,
            )
            new_msgs = all_msgs[turn_start + 1:]

            todo_snapshots = render_steps(new_msgs, live_status=status)
            status.update(label="✅ Done", state="complete")

        answer = extract_text(all_msgs[-1].content) or "*(no text response)*"
        st.markdown(answer)

        files = {
            p: d for p, d in result.get("files", {}).items()
            if p not in st.session_state.seed_files
        }
        render_files(files)

        sources = extract_sources_from_messages(new_msgs)
        render_export_buttons(
            query=prompt, answer=answer, model=used_model or model,
            sources=sources, files=files, key_prefix="live",
        )

        if used_model and used_model != model:
            st.caption(f"💡 Used fallback model: `{used_model}` (selected model didn't respond — see status log above)")


    db.add_message(st.session_state.thread_id, "assistant", answer)
    if todo_snapshots:
        db.save_todo_snapshot(st.session_state.thread_id, todo_snapshots[-1])
    db.touch_session(st.session_state.thread_id, status="completed")

    st.session_state.history.append(("assistant", answer, new_msgs, files))