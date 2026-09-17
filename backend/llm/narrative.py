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
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

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
_MAX_NARRATIVE_WORDS = 20  # mirrors frontend/src/lib/copy.js's MAX_NARRATIVE_WORDS —
                           # shared by the mastery-card lines


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
    """Single choke point for every plain-text chat-completion call in this module."""
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


def _complete_within_budget(system: str, user: str, max_words: int) -> str | None:
    """Shared choke point for every word-budgeted plain-text narrative in this module.

    An unconstrained model will happily write two sentences — a generic
    opener plus the actually-specific detail — that together overrun the
    caller's word cap; frontend/src/lib/copy.js then truncates on sentence
    boundaries and keeps only the generic first half. Stating the exact
    budget in the prompt up front (and regenerating once with a nudge if the
    first attempt still overruns) means the model's own sentence already
    fits, so truncation rarely has to do this trimming at all.
    """
    result = _complete(system, user)
    if result is None or _word_count(result) <= max_words:
        return result

    retry_user = (
        f"{user}\n\nYour previous attempt was too long: \"{result}\". "
        f"Rewrite it in {max_words} words or fewer."
    )
    result = _complete(system, retry_user)
    if result is None or _word_count(result) > max_words:
        return None
    return result


_T = TypeVar("_T", bound=BaseModel)


def _complete_structured(system: str, user: str, response_model: type[_T]) -> _T | None:
    """Structured-output counterpart to `_complete`: the response is validated
    against `response_model` (a pydantic model, so its shape is guaranteed)
    instead of returned as free text.
    """
    client = _client()
    if client is None:
        return None
    try:
        resp = client.chat.completions.parse(
            model=_MODEL,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            response_format=response_model,
            max_tokens=300,
        )
        return resp.choices[0].message.parsed
    except Exception:
        logger.warning("LLM structured narrative call failed", exc_info=True)
        return None


def _complete_structured_within_budget(
    system: str, user: str, response_model: type[_T], max_words: int
) -> _T | None:
    """Structured-output counterpart to `_complete_within_budget`: retries the
    whole call once, not just the offending field, if any line overruns —
    re-prompting a single field in isolation would recreate the same
    thin-context, no-shared-visibility problem the merged call exists to fix.
    """
    result = _complete_structured(system, user, response_model)
    if result is None:
        return None

    overrun = {
        field: getattr(result, field)
        for field in response_model.model_fields
        if _word_count(getattr(result, field)) > max_words
    }
    if not overrun:
        return result

    overrun_desc = "; ".join(f'{field}: "{text}"' for field, text in overrun.items())
    retry_user = (
        f"{user}\n\nYour previous attempt had lines that were too long: "
        f"{overrun_desc}. Rewrite every line in {max_words} words or fewer."
    )
    result = _complete_structured(system, retry_user, response_model)
    if result is None:
        return None
    if any(_word_count(getattr(result, field)) > max_words for field in response_model.model_fields):
        return None
    return result


def flavor_word_problem(
    question: str, correct_answer: int, skill_tag: str, difficulty: float
) -> str | None:
    """Touchpoint 1: wrap a plain numeric problem in a one-line story.

    Optional — callers show the plain `question` unchanged when this
    returns None. Constrained hard per CLAUDE.md's copy-limits table and
    revision-plan Part 7.4: an unconstrained model will happily produce a
    30-word sentence with a word a first-grader can't decode, and then the
    app is measuring reading, not math.
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
    return _complete_within_budget(system, user, _MAX_WORD_PROBLEM_WORDS)


class _NarrativesNoBoss(BaseModel):
    mastery_narrative: str
    reward_narrative: str


class _NarrativesWithBoss(BaseModel):
    mastery_narrative: str
    reward_narrative: str
    boss_battle_narrative: str


@dataclass
class MasteryCardNarratives:
    mastery_narrative: str
    reward_narrative: str
    boss_battle_narrative: str | None  # None when there's no next skill to hype


def _mastery_card_system_prompt(has_misconceptions: bool, has_boss_battle: bool) -> str:
    parts = [
        "You write the narrative lines for a K-5 math student's mastery-moment "
        "card, which just fired because they mastered a skill. This card shows "
        + ("three" if has_boss_battle else "two")
        + " short lines together, in the same card, at the same moment: a "
        "mastery line naming what they just overcame, a reward line framing "
        "their effort versus their speed"
        + (
            ", and a boss-battle line hyping the skill they're about to start next"
            if has_boss_battle
            else ""
        )
        + ". Because the reader sees all of them at once, write them as "
        "distinct beats, not restatements of each other: give each line a "
        "different sentence opener and a different sentence structure, and "
        "never restate the same number, fact, or phrase in more than one line.",
        f"Hard constraint: every line is {_MAX_NARRATIVE_WORDS} words maximum. "
        "One sentence per line, except mastery_narrative which may be up to "
        "two short sentences. Be concrete and specific, not generic praise.",
        "mastery_narrative: "
        + (
            "Name the specific mistake pattern the student overcame, using "
            "the pattern name given."
            if has_misconceptions
            else "This student had a clean run with no mistakes logged, so "
            "instead of generic congratulations, call out their fluency or "
            "speed using the actual attempt count and time given."
        ),
        "reward_narrative: Contrast effort against speed. If their attempt "
        "count is high or their average time is long, acknowledge the effort "
        "and persistence it took. If both are low, praise their speed and "
        "confidence instead.",
    ]
    if has_boss_battle:
        parts.append(
            "boss_battle_narrative: One short, exciting line naming the next "
            "skill they're about to practice, in plain kid-friendly language."
        )
    return "\n\n".join(parts)


def _mastery_card_user_prompt(
    skill: str,
    misconceptions: list[Misconception],
    attempt_count: int,
    avg_time_sec: float,
    next_skill: str | None,
) -> str:
    bug_types = ", ".join(sorted({m.bug_type for m in misconceptions}))
    lines = [
        f"Skill just mastered: {skill}",
        f"Attempts taken: {attempt_count}",
        f"Average time per attempt: {avg_time_sec:.1f} seconds",
    ]
    if bug_types:
        lines.append(f"Misconception patterns hit along the way: {bug_types}")
    else:
        lines.append("No misconceptions were logged: this was a clean run.")
    if next_skill is not None:
        lines.append(f"Next skill they're about to start: {next_skill}")
    return "\n".join(lines)


def mastery_card_narrative(
    skill: str,
    misconceptions: list[Misconception],
    attempt_count: int,
    avg_time_sec: float,
    next_skill: str | None = None,
) -> MasteryCardNarratives | None:
    """Touchpoints 2-4 merged: the mastery, reward, and boss-battle lines from
    one structured call sharing full context, so the three lines read as
    distinct beats instead of three isolated, near-identical prompts.

    Fires once, at the mastery moment (the advance_skill transition, or a
    quest-ending answer that mastered its skill). `next_skill` is the skill
    the student is about to start next; pass None when there isn't one (the
    true end of the whole quest) and the boss-battle line is simply not
    requested, rather than asked for and left blank.
    """
    has_boss_battle = next_skill is not None
    system = _mastery_card_system_prompt(bool(misconceptions), has_boss_battle)
    user = _mastery_card_user_prompt(skill, misconceptions, attempt_count, avg_time_sec, next_skill)
    response_model = _NarrativesWithBoss if has_boss_battle else _NarrativesNoBoss

    parsed = _complete_structured_within_budget(system, user, response_model, _MAX_NARRATIVE_WORDS)
    if parsed is None:
        return None
    return MasteryCardNarratives(
        mastery_narrative=parsed.mastery_narrative,
        reward_narrative=parsed.reward_narrative,
        boss_battle_narrative=getattr(parsed, "boss_battle_narrative", None),
    )
