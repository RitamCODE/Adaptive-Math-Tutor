"""The four narrative LLM touchpoints allowed by CLAUDE.md.

This is the only module in `backend/` permitted to reference an LLM client.
Verify isolation with:

    git ls-files 'backend/*.py' | xargs grep -l openai

Every public function here is fail-open: a missing API key, a network
error, a timeout, or a malformed response all collapse to `None` rather
than raising. Callers treat `None` as "no narrative available" and fall
back to plain, pre-existing text — grading, mastery, and curriculum
selection never depend on any of this.
"""

import logging
import os
from pathlib import Path

from backend.models.state import Misconception

logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """Populate os.environ from a repo-root .env file, if present.

    Minimal, dependency-free stand-in for python-dotenv (CLAUDE.md requires
    asking before adding a new library). Existing environment variables take
    precedence over the file.
    """
    env_path = Path(__file__).resolve().parents[2] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


_load_dotenv()

_MODEL = os.environ.get("OPENAI_NARRATIVE_MODEL", "gpt-4o-mini")
_TIMEOUT_SEC = 5.0
_MAX_WORD_PROBLEM_WORDS = 20


def _word_count(text: str) -> int:
    return len(text.split())


def _client():
    """An OpenAI client, or None if no API key is configured.

    Wrapped with langsmith's `wrap_openai` so every completion call this
    module makes auto-emits a traced LLM run (prompt, completion, token
    counts) to LangSmith when the `LANGSMITH_*` env vars are set — this is
    langsmith's own client-level instrumentation, not LangChain's runnable
    system, which matters here because these calls run from FastAPI
    background tasks and a separate narrative endpoint, never from inside
    `graph.app.invoke()`, so LangGraph's graph-level auto-tracing alone
    would never see them. Wrapping failure degrades to an untraced client
    rather than no client at all, and when tracing env vars are unset,
    `wrap_openai` is a no-op at call time.
    """
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, timeout=_TIMEOUT_SEC, max_retries=0)
    except Exception:
        logger.warning("failed to construct OpenAI client", exc_info=True)
        return None
    try:
        from langsmith.wrappers import wrap_openai

        return wrap_openai(client)
    except Exception:
        logger.warning("failed to wrap OpenAI client for LangSmith tracing; continuing untraced", exc_info=True)
        return client


def _complete(system: str, user: str, max_tokens: int = 120) -> str | None:
    """Single choke point for every chat-completion call in this module."""
    client = _client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.create(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            max_tokens=max_tokens,
        )
        text = resp.choices[0].message.content
        return text.strip() if text else None
    except Exception:
        logger.warning("LLM narrative call failed", exc_info=True)
        return None


def flavor_word_problem(
    question: str, correct_answer: int, skill_tag: str, difficulty: float
) -> str | None:
    """Touchpoint 1: wrap a plain numeric problem in a one-line story.

    Optional — callers show the plain `question` unchanged when this
    returns None. Constrained hard per CLAUDE.md's copy-limits table and
    revision-plan Part 7.4: an unconstrained model will happily produce a
    30-word sentence with a word a first-grader can't decode, and then the
    app is measuring reading, not math. If the first attempt overruns the
    20-word cap, regenerate once with a nudge before giving up (never a
    retry loop).
    """
    system = (
        "You write a single short, fun one-line word-problem story for a "
        "K-5 math student. Hard constraints: 20 words maximum. Exactly one "
        "common first name. Exactly one concrete, countable object (like "
        "apples or stickers, not an abstract noun). Write all numbers as "
        "digits, never spelled out. One simple sentence, no subordinate "
        "clauses (no 'which', 'because', 'and then'). Keep the original "
        "numbers and operation exactly as given. Do not reveal or restate "
        "the answer. Output only the one-line story, no preamble."
    )
    user = f"Skill: {skill_tag}\nDifficulty: {difficulty}\nProblem: {question}"
    result = _complete(system, user)
    if result is None or _word_count(result) <= _MAX_WORD_PROBLEM_WORDS:
        return result

    retry_user = (
        f"{user}\n\nYour previous attempt was too long: \"{result}\". "
        f"Rewrite it in {_MAX_WORD_PROBLEM_WORDS} words or fewer."
    )
    result = _complete(system, retry_user)
    if result is None or _word_count(result) > _MAX_WORD_PROBLEM_WORDS:
        return None
    return result


def mastery_moment_narrative(
    skill: str, misconceptions: list[Misconception], attempt_count: int
) -> str | None:
    """Touchpoint 2: name the specific pattern the student overcame on `skill`.

    Fires once, on the advance_skill transition.
    """
    bug_types = ", ".join(sorted({m.bug_type for m in misconceptions})) or "none logged"
    system = (
        "You write one or two encouraging sentences for a K-5 math student "
        "who just mastered a skill, naming the specific mistake pattern "
        "they overcame. Be concrete and specific, not generic praise."
    )
    user = (
        f"Skill just mastered: {skill}\n"
        f"Attempts taken: {attempt_count}\n"
        f"Misconception patterns hit along the way: {bug_types}"
    )
    return _complete(system, user)


def effort_reward_narrative(skill: str, attempt_count: int, avg_time_sec: float) -> str | None:
    """Touchpoint 3: one line differentiating a struggled-through vs. quick pass.

    Fires at the mastery moment only (on the advance_skill transition), using
    real attempt-count and average time-per-attempt data for `skill`.
    """
    system = (
        "You write one short reward-framing line for a K-5 math student who "
        "just answered correctly. If their attempt count is high or their "
        "average time is long, acknowledge the effort/persistence. If both "
        "are low, praise the speed/confidence instead. One sentence only."
    )
    user = (
        f"Skill: {skill}\n"
        f"Attempts so far on this skill: {attempt_count}\n"
        f"Average time per attempt (seconds): {avg_time_sec:.1f}"
    )
    return _complete(system, user)


def boss_battle_narrative(skill: str) -> str | None:
    """Touchpoint 4: short framing text naming the skill being confirmed.

    Fires alongside the mastery-moment narrative, on entry into the newly
    selected skill after an advance_skill transition.
    """
    system = (
        "You write one short, exciting 'boss battle' framing line for a "
        "K-5 math student about to start practicing a new skill. Name the "
        "skill in plain, kid-friendly language. One sentence only."
    )
    user = f"New skill: {skill}"
    return _complete(system, user)
