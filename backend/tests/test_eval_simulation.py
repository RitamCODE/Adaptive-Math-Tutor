"""Sanity checks for the simulated-learner evaluation harness
(backend/eval/). These don't test the app's own engine logic (that's
test_graph.py, test_curriculum.py, etc.) -- they test that the harness
itself drives the real engine correctly and that the non-adaptive baseline
actually behaves non-adaptively.
"""

import random

import backend.graph as graph_module
from backend.eval.baseline import _make_fixed_schedule_select_next_skill, non_adaptive_condition
from backend.eval.driver import run_session
from backend.eval.synthetic_learner import SkillTrueParams, SyntheticLearner, SKILLS, effective_p_slip
from backend.models.bkt import is_mastered
from backend.models.bkt import is_mastered as bkt_is_mastered
from backend.models.state import EngagementState, LastResponse, SessionState
from backend.graph import app
from backend.skills._arithmetic import default_rng as _problem_rng
from backend.skills._arithmetic import parse_operands
from backend.skills.skill_graph import DEFAULT_SKILL_GRAPH
from backend.tests.conftest import make_state


def _certain_learner(
    student_id: str, *, knows_from_start: bool, learns: bool, width_sensitivity_true: float = 0.0
) -> SyntheticLearner:
    """A learner with no randomness in its outcomes, for deterministic
    sanity checks: either always-correct-from-turn-1 or never-correct."""
    params = SkillTrueParams(
        p_init_true=1.0 if knows_from_start else 0.0,
        p_slip_true=0.0,
        p_guess_true=0.0,
        p_learn_true=1.0 if learns else 0.0,
        width_sensitivity_true=width_sensitivity_true,
    )
    return SyntheticLearner(
        student_id=student_id,
        true_params={skill: params for skill in SKILLS},
        rng=random.Random(0),
    )


def test_high_ability_learner_reaches_true_mastery_on_all_skills():
    learner = _certain_learner("high", knows_from_start=True, learns=True)
    result = run_session(learner)

    assert all(result.true_mastered.values()), result.true_mastered
    assert all(result.engine_mastered.values()), result.engine_mastered


def test_zero_ability_learner_hits_the_fatigue_stop_and_never_masters():
    learner = _certain_learner("zero", knows_from_start=False, learns=False)
    result = run_session(learner)

    assert result.final_state.next_action == "end_session"
    assert result.turns == 4  # 3 wrong attempts + demotion fallback + 1 more wrong -> fatigue stop
    assert not any(result.true_mastered.values())
    assert not any(result.engine_mastered.values())


def _invoke(state: SessionState) -> SessionState:
    return SessionState.model_validate(app.invoke(state.model_dump()))


def _initial_state() -> SessionState:
    return SessionState(
        student_id="s", session_id="sess", skill_mastery={}, misconception_log=[],
        current_problem=None, last_response=None,
        engagement=EngagementState(streak=0, xp=0, frustration_signal=False, consecutive_wrong=0),
        next_action="new_problem",
    )


def _operand_width(question: str) -> int:
    a, _op, b = parse_operands(question)
    return max(len(str(a)), len(str(b)))


def test_baseline_ignores_real_mastery_and_switches_skill_only_at_the_fixed_count():
    with non_adaptive_condition(problems_per_skill=4):
        state = _invoke(_initial_state())
        assert state.current_problem.skill_tag == "addition_no_carry"

        for _ in range(3):
            answer = state.current_problem.correct_answer
            state = state.model_copy(update={"last_response": LastResponse(answer=answer, correct=False, time_taken_sec=5.0)})
            state = _invoke(state)

        # After 3 correct answers the real engine would already call this
        # skill mastered (MASTERY_MIN_RUN=3) -- the baseline must not have
        # switched yet, since its own budget is 4.
        assert is_mastered("addition_no_carry", state)
        assert state.current_problem.skill_tag == "addition_no_carry"
        assert _operand_width(state.current_problem.question) == 1  # PINNED_TIER=0

        answer = state.current_problem.correct_answer
        state = state.model_copy(update={"last_response": LastResponse(answer=answer, correct=False, time_taken_sec=5.0)})
        state = _invoke(state)

        assert state.current_problem.skill_tag == "addition_carry"


def test_fixed_schedule_selector_does_not_skip_a_still_locked_skill():
    """Even once a skill's fixed budget is exhausted, the selector must not
    advance to a skill that isn't REALLY unlocked yet (its prerequisite
    hasn't reached genuine sustained BKT mastery) -- a fixed pace that
    outruns real prerequisite mastery should stall, not skip ahead."""
    served = {"addition_no_carry": 999}
    select = _make_fixed_schedule_select_next_skill(served, problems_per_skill=4)
    state = make_state()  # empty skill_mastery: addition_no_carry is not really mastered

    assert select(state, DEFAULT_SKILL_GRAPH) == "addition_no_carry"


def test_engine_mastered_metric_uses_the_real_unpatched_is_mastered():
    """driver.run_session's `engine_mastered` must be computed from
    backend.models.bkt.is_mastered directly, never from backend.graph's own
    name (the one baseline.py patches for routing) -- otherwise a baseline
    run's headline number would be measured by the very rule it's supposed
    to be tested against, silently inflating or deflating it."""
    import backend.eval.driver as driver_module

    # driver.py's `real_is_mastered` must be the identical function object as
    # backend.models.bkt.is_mastered, imported directly from bkt.py rather
    # than through backend.graph (which is what gets monkeypatched).
    assert driver_module.real_is_mastered is bkt_is_mastered

    with non_adaptive_condition(problems_per_skill=1):
        # Inside the patched block, backend.graph.is_mastered is NOT the real
        # function -- confirms the patch is active for this assertion to mean
        # anything.
        assert graph_module.is_mastered is not bkt_is_mastered

        learner = _certain_learner("metric-check", knows_from_start=True, learns=True)
        result = run_session(learner)

    # The metric must agree with calling the real function directly against
    # the session's own final mastery/mastery_run state, independent of
    # whatever `problems_served` bookkeeping the routing patch used.
    expected = {skill: bkt_is_mastered(skill, result.final_state) for skill in SKILLS}
    assert result.engine_mastered == expected
    assert all(result.engine_mastered.values())  # this learner is high-ability, sanity check


def test_digit_width_increases_true_slip_probability():
    """Without a width-dependent term, the digit-width ladder would have no
    causal effect on the simulated outcome at all -- BKT mastery and
    digit-width are mutually independent BY DESIGN in the real engine
    (backend/skills/_difficulty_ladder.py's own docstring), so if the
    synthetic learner's correctness also ignored width, the ladder would be
    fully inert in the simulation too."""
    params = SkillTrueParams(
        p_init_true=1.0, p_slip_true=0.1, p_guess_true=0.05, p_learn_true=0.0,
        width_sensitivity_true=0.08,
    )
    # addition_carry's own narrowest tier is 2 digits (WIDTH_LADDER["addition_carry"][0]).
    p_slip_at_narrowest = effective_p_slip(params, "addition_carry", digit_width=2)
    p_slip_one_wider = effective_p_slip(params, "addition_carry", digit_width=3)

    assert p_slip_at_narrowest == 0.1
    assert p_slip_one_wider == 0.1 + 0.08
    assert p_slip_one_wider > p_slip_at_narrowest


def _strip_nondeterministic_ids(dump: dict) -> dict:
    """Problem.problem_id (backend/models/state.py) comes from uuid4(), which
    draws from OS entropy and is never reproducible no matter what gets
    seeded -- strip it (and the copy inside last_diagnosis) so the comparison
    isn't polluted by an identifier that was never supposed to be stable."""
    dump = dict(dump)
    if dump.get("current_problem"):
        dump["current_problem"] = {k: v for k, v in dump["current_problem"].items() if k != "problem_id"}
    if dump.get("last_diagnosis"):
        dump["last_diagnosis"] = {k: v for k, v in dump["last_diagnosis"].items() if k != "problem_id"}
    return dump


def test_adaptive_condition_is_unaffected_by_a_preceding_baseline_run():
    """The three patches in non_adaptive_condition() must be scoped strictly
    to its own `with` block. Runs the same deterministic learner before and
    after a baseline session in the same process and requires an identical
    trajectory (modulo the two sources of legitimate, unrelated
    non-determinism noted below).

    The skill generators (e.g. addition_no_carry.py's `generate`) fall back
    to a single shared `random.Random()` instance --
    backend.skills._arithmetic's `default_rng`, seeded from OS entropy once
    at import time -- whenever `generate_problem` doesn't pass a seeded one
    of its own, which it never does. That instance is reseeded identically
    right before each of the two adaptive runs below so problem CONTENT is
    also pinned, isolating the comparison to exactly one question: did the
    intervening baseline run leave anything behind. Problem.problem_id
    (uuid4-based) can't be pinned this way at all -- it's stripped by
    `_strip_nondeterministic_ids` instead."""
    assert graph_module.is_mastered is bkt_is_mastered  # nothing patched before this test runs

    _problem_rng.seed(20260917)
    result_before = run_session(_certain_learner("before", knows_from_start=True, learns=True))

    with non_adaptive_condition():
        run_session(_certain_learner("between", knows_from_start=True, learns=True))

    assert graph_module.is_mastered is bkt_is_mastered  # restored once the `with` block exits

    _problem_rng.seed(20260917)
    result_after = run_session(_certain_learner("after", knows_from_start=True, learns=True))

    before_dump = _strip_nondeterministic_ids(
        result_before.final_state.model_dump(exclude={"student_id", "session_id"})
    )
    after_dump = _strip_nondeterministic_ids(
        result_after.final_state.model_dump(exclude={"student_id", "session_id"})
    )
    assert before_dump == after_dump
    assert result_before.turns == result_after.turns
    assert result_before.engine_mastered == result_after.engine_mastered
    assert result_before.true_mastered == result_after.true_mastered
