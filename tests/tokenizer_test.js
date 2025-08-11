// Simple self-contained tests for tokenizeWithQuotes
// This mirrors the implementation in src/web/static/js/app.js

function tokenizeWithQuotes(input, options = { separator: 'whitespace' }) {
  const sepMode = options.separator || 'whitespace';
  const s = String(input || '');
  const tokens = [];
  let buf = [];
  let inQuote = null;
  let escapeNext = false;

  const isWhitespace = (ch) => /\s/.test(ch) || ch === '\u3000';
  const isCommaSep = (ch) => ch === ',' || ch === '，' || ch === '、';

  const flush = () => {
    if (buf.length === 0) return;
    const t = buf.join('').trim();
    if (t) tokens.push(t);
    buf = [];
  };

  for (let i = 0; i < s.length; i++) {
    const ch = s[i];

    if (escapeNext) { buf.push(ch); escapeNext = false; continue; }
    if (ch === '\\') { escapeNext = true; continue; }

    if (inQuote) { if (ch === inQuote) { inQuote = null; } else { buf.push(ch); } continue; }
    if (ch === '"' || ch === '\'') { inQuote = ch; continue; }

    if (sepMode === 'whitespace') { if (isWhitespace(ch)) { flush(); continue; } }
    else if (sepMode === 'comma') { if (isCommaSep(ch)) { flush(); continue; } }

    buf.push(ch);
  }

  if (inQuote !== null) {
    const t = (inQuote + buf.join('')).trim();
    if (t) tokens.push(t);
  } else {
    flush();
  }
  return tokens;
}

function assertEquals(actual, expected, label) {
  const pass = Array.isArray(actual) && Array.isArray(expected)
    && actual.length === expected.length
    && actual.every((v, i) => v === expected[i]);
  if (!pass) {
    console.error(`✗ ${label}\n  expected: ${JSON.stringify(expected)}\n  actual:   ${JSON.stringify(actual)}`);
    process.exitCode = 1;
  } else {
    console.log(`✓ ${label}`);
  }
}

// Tests for whitespace mode (exclude words)
assertEquals(tokenizeWithQuotes('田中\u3000浩紀', { separator: 'whitespace' }), ['田中', '浩紀'], 'full-width space split');
assertEquals(tokenizeWithQuotes('"田中\u3000浩紀" あああ', { separator: 'whitespace' }), ['田中　浩紀', 'あああ'], 'double-quoted keeps as one token');
assertEquals(tokenizeWithQuotes('\'田中\u3000浩紀\' あああ', { separator: 'whitespace' }), ['田中　浩紀', 'あああ'], 'single-quoted keeps as one token');
assertEquals(tokenizeWithQuotes('"田中', { separator: 'whitespace' }), ['"田中'], 'unclosed double-quote keeps leading quote');
assertEquals(tokenizeWithQuotes('\'田中', { separator: 'whitespace' }), ['\'田中'], 'unclosed single-quote keeps leading quote');
assertEquals(tokenizeWithQuotes('"田中\\"浩紀" いいい', { separator: 'whitespace' }), ['田中"浩紀', 'いいい'], 'escaped quote inside quotes');
assertEquals(tokenizeWithQuotes('AAA\tBBB\nCCC', { separator: 'whitespace' }), ['AAA', 'BBB', 'CCC'], 'tabs and newlines split');

// Tests for comma mode (additional words)
assertEquals(tokenizeWithQuotes('"田中　浩紀", 山田, \'佐藤 太郎\'', { separator: 'comma' }), ['田中　浩紀', '山田', '佐藤 太郎'], 'comma-separated with quotes');
assertEquals(tokenizeWithQuotes(' a , , b ', { separator: 'comma' }), ['a', 'b'], 'ignore empty tokens between commas');

console.log('Done.');

