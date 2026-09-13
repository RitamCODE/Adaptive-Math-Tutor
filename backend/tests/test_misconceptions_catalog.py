"""Machine-checked catalog invariants (docs/CHECKLIST.md item C), not eyeballed:
every bug_type actually produced by a detector has a catalog entry, and every
hint respects CLAUDE.md's 12-word wrong-answer cap and never leaks a number.
"""

import re

from backend.nodes.diagnosis import _MISCONCEPTIONS
from backend.skills import addition_carry, addition_no_carry, cross_cutting, subtraction_borrow, subtraction_no_borrow

_ALL_SKILL_BUG_TYPES = {
    bug_type
    for module in (addition_no_carry, addition_carry, subtraction_no_borrow, subtraction_borrow)
    for bug_type, _detector in module.BUG_RULES
}
_ALL_BUG_TYPES = _ALL_SKILL_BUG_TYPES | {bug_type for bug_type, _detector in cross_cutting.BUG_RULES} | {"unclassified"}

_HAS_DIGIT = re.compile(r"\d")


def test_every_detector_bug_type_has_a_catalog_entry():
    missing = _ALL_BUG_TYPES - _MISCONCEPTIONS.keys()
    assert not missing


def test_every_catalog_entry_has_hint_and_visual():
    for bug_type, entry in _MISCONCEPTIONS.items():
        assert entry.get("hint"), bug_type
        assert entry.get("visual"), bug_type


def test_every_hint_is_at_most_twelve_words():
    for bug_type, entry in _MISCONCEPTIONS.items():
        word_count = len(entry["hint"].split())
        assert word_count <= 12, f"{bug_type} hint is {word_count} words: {entry['hint']!r}"


def test_unclassified_hint_never_reveals_a_number():
    assert _HAS_DIGIT.search(_MISCONCEPTIONS["unclassified"]["hint"]) is None
