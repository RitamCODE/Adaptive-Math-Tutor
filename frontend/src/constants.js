export const SKILL_DISPLAY_NAMES = {
  addition_no_carry: "Addition (no carrying)",
  addition_carry: "Addition with Carrying",
  subtraction_no_borrow: "Subtraction (no borrowing)",
  subtraction_borrow: "Subtraction with Borrowing",
};

export const BUG_TYPE_HINTS = {
  no_carry: "Remember to carry the extra ten into the next column!",
  reversed_operands:
    "Careful — subtract the second number from the first, not the other way around.",
  no_borrow_smaller_from_larger:
    "When the top digit is smaller, borrow from the next column instead of just taking the difference.",
  off_by_ten_in_borrow:
    "You're close! Double-check the column where you borrowed — it's off by ten.",
};

export const GENERIC_WRONG_ANSWER_HINT = "Double-check your steps and try again!";
