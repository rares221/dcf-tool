import { b, el, fill } from './dom.js';
import { freshness, money, pct } from './format.js';

const $ = (id) => document.getElementById(id);

const state = {
  analysis: null,   // /api/analyze payload
  model: null,      // /api/model payload for the current inputs
  horizon: 5,
  countSbc: true,
  a: null,          // current assumptions {growth, fcf_margin, wacc, terminal_growth}
  loadSeq: 0,       // newest analyze request
  seq: 0,           // newest model request; older responses are dropped
};

const KEY_LABEL = { wacc: 'discount rate', growth: 'revenue growth', margin: 'FCF margin', terminal_growth: 'long-term growth' };
const POSITION = {
  below: ['below the whole range, so it looks ', 'cheap'],
  lower: ['in the lower part of the range, leaning ', 'cheaper'],
  middle: ['in the middle of the range, roughly ', 'fairly priced'],
  upper: ['in the upper part of the range, leaning ', 'pricier'],
  above: ['above the whole range, so it looks ', 'expensive'],
};
const USABLE = new Set(['ok', 'partial']);

// ---------- data loading ----------
async function getJson(url, options) {
  try {
    const res = await fetch(url, options);
    return await res.json();
  } catch {
    return { status: 'error' };
  }
}

async function load(raw) {
  const mine = ++state.loadSeq;
  $('ticker').value = raw;
  const analysis = await getJson(`/api/analyze?ticker=${encodeURIComponent(raw)}`);
  if (mine !== state.loadSeq) return;
  state.analysis = analysis;
  state.model = null;
  if (analysis.suggested) {
    const s = analysis.suggested;
    state.a = { growth: s.growth, fcf_margin: s.fcf_margin, wacc: s.wacc, terminal_growth: s.terminal_growth };
    state.countSbc = true;
    state.horizon = 5;
  }
  render();
  if (analysis.suggested) recalc();
}

async function recalc() {
  const mine = ++state.seq;
  const body = { ticker: state.analysis.company.ticker, horizon: state.horizon, ...state.a, count_sbc: state.countSbc };
  const model = await getJson('/api/model', {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body),
  });
  if (mine !== state.seq) return; // a newer request superseded this one
  state.model = model;
  render();
}

// ---------- rendering ----------
function render() {
  const a = state.analysis;
  const usable = a && USABLE.has(a.status);
  $('main').hidden = !usable;
  fill($('banners'), a && !usable ? el('div', { class: 'banner', role: 'status' }, `Could not analyze this ticker (${a.status}).`) : null);
  if (!usable) return;
  renderCompany(a);
  document.querySelectorAll('#pills button').forEach((btn) => btn.classList.toggle('on', Number(btn.dataset.n) === state.horizon));
  const m = state.model && state.model.status === 'ok' ? state.model : null;
  renderTakeaway(a, m);
  renderScenarios(a, m);
}

function renderCompany(a) {
  const c = a.company;
  const sub = [c.sector, c.industry].filter(Boolean).join(' · ');
  fill($('company'), el('div', { class: 'head' },
    el('div', {},
      el('h1', {}, c.name, ' ', el('span', { class: 'muted', style: 'font-weight:400' }, `(${c.ticker})`)),
      el('div', { class: 'small muted' }, [sub, `market cap ${money(c.market_cap, c.currency, { compact: true })}`].filter(Boolean).join(' · ')),
      el('div', { class: 'small muted' }, freshness(a.data_age_seconds)),
    ),
    el('div', { class: 'price' }, el('b', {}, money(c.price, c.currency)), el('div', { class: 'small muted' }, `current price (${c.currency})`)),
  ));
}

function renderTakeaway(a, m) {
  const node = $('takeaway');
  if (!m) { fill(node, el('p', { style: 'margin:0' }, 'Calculating…')); return; }
  const c = a.company, s = m.scenarios, cur = c.currency;
  const [lead, word] = POSITION[m.position];
  const years = a.history.length - 1;
  const parts = [
    `Under your assumptions, ${c.name}'s price of `, b(money(c.price, cur)), ` is ${lead}`, b(word),
    ` (${money(s.bear, cur)} to ${money(s.bull, cur)}, base ${money(s.base, cur)}). The assumption that swings the answer most is the `,
    b(KEY_LABEL[m.sensitivity[0].key]), '. ',
  ];
  if (m.implied_growth != null) {
    parts.push('The market is pricing in about ', b(pct(m.implied_growth)), ' yearly growth');
    if (a.history_cagr != null) parts.push(`, against ${pct(a.history_cagr)} over the last ${years} ${years === 1 ? 'year' : 'years'}`);
    parts.push('.');
  }
  fill(node, el('p', { style: 'margin:0' }, ...parts),
    el('span', { class: 'fine' }, 'Educational estimate, not financial advice. Change the assumptions below and everything updates.'));
}

function renderScenarios(a, m) {
  const cur = a.company.currency, price = a.company.price;
  $('pxLabel').textContent = `Price ${money(price, cur)}`;
  if (!m) {
    fill($('scen'), el('p', { class: 'muted' }, 'Calculating…'));
    return;
  }
  const s = m.scenarios, g = a.suggested;
  const card = (cls, label, value, note, color) => el('div', { class: `scen-card ${cls}` },
    el('small', {}, label), el('b', color ? { style: `color:${color}` } : {}, money(value, cur)), el('small', {}, note));
  fill($('scen'),
    card('bear', 'Bear', s.bear, 'weaker growth and margin, higher discount rate', 'var(--bad)'),
    card('base', 'Base', s.base, `growth ${pct(state.a.growth, 1)}, margin ${pct(state.a.fcf_margin, 1)}`),
    card('bull', 'Bull', s.bull, 'stronger growth and margin, lower discount rate', 'var(--good)'));

  const lo = Math.min(s.bear, price) * 0.8, hi = Math.max(s.bull, price) * 1.15;
  const pos = (x) => ((x - lo) / (hi - lo)) * 100;
  $('rng').style.left = `${pos(s.bear)}%`;
  $('rng').style.width = `${pos(s.bull) - pos(s.bear)}%`;
  $('mid').style.left = `${pos(s.base)}%`;
  $('px').style.left = `${pos(price)}%`;
  $('sMin').textContent = money(lo, cur);
  $('sMax').textContent = money(hi, cur);
  $('sRange').textContent = `Range ${money(s.bear, cur)} to ${money(s.bull, cur)} (base ${money(s.base, cur)})`;

  const where = m.position === 'below' ? 'below the whole range, which would suggest it is cheap under these assumptions'
    : m.position === 'above' ? 'above the whole range, which would suggest it is expensive under these assumptions'
      : 'inside the range, so these assumptions do not clearly call it cheap or expensive';
  const r = m.implied_return;
  fill($('verdict'), `Today's price is ${where}. If the price moved to the base estimate over ${state.horizon} years, that is about `,
    b(`${pct(r.base)} a year`), ` (bear ${pct(r.bear)}, bull ${pct(r.bull)}), before dividends.`);
  void g;
}

// ---------- events ----------
$('search').addEventListener('submit', (e) => {
  e.preventDefault();
  const t = $('ticker').value.trim().toUpperCase();
  if (!t) return;
  if (decodeURIComponent(location.hash.slice(1)) === t) load(t);
  else location.hash = encodeURIComponent(t);
});

$('pills').addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  if (!btn || !state.analysis || !state.analysis.suggested) return;
  state.horizon = Number(btn.dataset.n);
  render();
  recalc();
});

window.addEventListener('hashchange', () => {
  const t = decodeURIComponent(location.hash.slice(1));
  if (t) load(t);
});

if (location.hash.length > 1) load(decodeURIComponent(location.hash.slice(1)));
