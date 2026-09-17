/**
 * The pure state of a column-arithmetic board: digits, places, regrouping.
 *
 * Kept out of the component (and free of JSX) so the arithmetic that decides
 * when a column is short, which column lends to it, and how many columns are
 * drawn can be reasoned about — and checked — on its own. The component owns
 * pointers, animation and rendering; none of that appears here.
 */

export const MAX_PLACES = 4;
export const PLACE_LABEL = ["Ones", "Tens", "Hundreds", "Thousands"];
export const TOKEN_TYPE = ["stick", "bundle", "flat", "cube"];

/** Digits of `n` as an array indexed by place: index 0 is the ones. */
export function digitsOf(n, places) {
  const out = [];
  let rest = n;
  for (let i = 0; i < places; i += 1) {
    out.push(rest % 10);
    rest = Math.floor(rest / 10);
  }
  return out;
}

export function withAt(list, index, value) {
  const next = list.slice();
  next[index] = value;
  return next;
}

/** How many places the board tracks. Addition keeps one spare on the left so
 *  a carry out of the top place has somewhere to land (86 + 94 needs a
 *  hundreds column). */
export function placeCount(operation, a, b) {
  const widest = Math.max(String(a).length, String(b).length);
  return Math.min(operation === "add" ? widest + 1 : String(a).length, MAX_PLACES);
}

/** How many places are drawn. The spare addition column appears only once a
 *  carry has actually reached it — which is both what happens on paper and
 *  what keeps three-digit addition inside the card, since every visible
 *  column has to be wide enough to hold 48px blocks. It also means the column
 *  count can't hint at how wide the answer is going to be. */
export function visiblePlaceCount(operation, a, b, board) {
  const places = placeCount(operation, a, b);
  if (operation !== "add" || places <= 1) return places;
  const top = places - 1;
  // Only a carry that actually arrived earns the column. Resolving it doesn't:
  // work runs right to left, so the spare column eventually becomes active and
  // resolves to zero on its own, which would otherwise pop an empty column
  // into existence at the very end of a problem that never needed one.
  const used = board.carried[top] || board.work[top] > 0;
  return used ? places : places - 1;
}

export function initBoard(operation, a, b, places, key) {
  const da = digitsOf(a, places);
  const db = digitsOf(b, places);
  return {
    // Which problem this board belongs to. State updates are asynchronous, so
    // on the first commit after the problem changes the reset effect has not
    // landed yet and the effects in the component still close over the
    // *previous* board — which, read against the new problem's digits,
    // resolved a column nobody had touched and wrote a wrong answer digit
    // under the rule.
    key,
    // Subtraction: the minuend's digits as they stand *after* any borrowing.
    regrouped: da.slice(),
    // Subtraction: how many of this column's take-away slots are filled.
    removed: da.map(() => 0),
    // Addition: blocks still waiting in each addend's row.
    poolA: da.slice(),
    poolB: db.slice(),
    // Addition: blocks gathered in the column's work zone, below the rule.
    work: da.map(() => 0),
    // Addition: this column received a carry (drives the little "1" mark).
    carried: da.map(() => false),
    answer: da.map(() => null),
    active: 0,
  };
}

/**
 * Which column needs a block broken open, and where it comes from.
 *
 * When the column below is empty the pad moves up rather than reaching past
 * it: 300 - 134 borrows a hundred into the tens first, then a ten into the
 * ones — two steps the student causes and watches, which is what borrowing
 * across a zero actually is.
 */
export function computeBorrow(available, needed, active, places) {
  if (active >= places || available[active] >= needed[active]) return null;
  let to = active;
  while (to + 1 < places && available[to + 1] === 0) to += 1;
  if (to + 1 >= places) return null;
  return { to, from: to + 1 };
}

/** Break one block of `place` into ten of the place below. */
export function unbundle(board, place) {
  return {
    ...board,
    regrouped: withAt(
      withAt(board.regrouped, place, board.regrouped[place] - 1),
      place - 1,
      board.regrouped[place - 1] + 10
    ),
  };
}

/** Bundle ten loose blocks of `place` into one of the place above. */
export function bundle(board, place) {
  return {
    ...board,
    work: withAt(
      withAt(board.work, place, board.work[place] - 10),
      place + 1,
      board.work[place + 1] + 1
    ),
    carried: withAt(board.carried, place + 1, true),
  };
}
