const QUESTION_RE = /^(\d+)\s*([+-])\s*(\d+)$/;

export function parseQuestion(question) {
  const match = QUESTION_RE.exec(question.trim());
  if (!match) return null;
  const [, a, operator, b] = match;
  return { a: Number(a), operator, b: Number(b) };
}

export function toBlocks(n) {
  const hundreds = Math.floor(n / 100);
  const tens = Math.floor((n % 100) / 10);
  const ones = n % 10;
  return { hundreds, tens, ones };
}
