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
const SLIDERS = [['g', 'growth'], ['m', 'fcf_margin'], ['w', 'wacc'], ['t', 'terminal_growth']];
const USABLE = new Set(['ok', 'partial']);
const GAP = 1; // discount rate must stay at least this far above long-term growth (matches the API)

// ---------- data loading ----------
async function getJson(url, options) {
  try {
    const res = await fetch(url, options);
    return await res.json();
  } catch {
    return { status: 'error' };
  }
}

function suggestedAssumptions(s) {
  return { growth: s.growth, fcf_margin: s.fcf_margin, wacc: s.wacc, terminal_growth: s.terminal_growth };
}

function syncSliders() {
  const limits = state.analysis.limits;
  for (const [id, key] of SLIDERS) {
    const input = $(id);
    input.min = limits[key][0];
    input.max = limits[key][1];
  }
  $('w').min = Math.max(limits.wacc[0], state.a.terminal_growth + GAP);
  for (const [id, key] of SLIDERS) $(id).value = state.a[key];
}

async function load(raw) {
  const mine = ++state.loadSeq;
  $('ticker').value = raw;
  const analysis = await getJson(`/api/analyze?ticker=${encodeURIComponent(raw)}`);
  if (mine !== state.loadSeq) return;
  state.analysis = analysis;
  state.model = null;
  if (analysis.suggested) {
    state.a = suggestedAssumptions(analysis.suggested);
    state.countSbc = true;
    state.horizon = 5;
    syncSliders();
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

let recalcQueued = false;
function scheduleRecalc() {
  if (recalcQueued) return;
  recalcQueued = true;
  requestAnimationFrame(() => { recalcQueued = false; recalc(); });
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
  renderAssumptions(a, m);
  renderTakeaway(a, m);
  renderScenarios(a, m);
  renderImplied(a, m);
  renderTornado(a, m);
  renderWacc(a, m);
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

function renderAssumptions(a, m) {
  const s = a.suggested;
  $('gv').textContent = `${state.a.growth}%`;
  $('mv').textContent = `${state.a.fcf_margin}%`;
  $('wv').textContent = `${state.a.wacc.toFixed(1)}%`;
  $('tv').textContent = `${state.a.terminal_growth}%`;
  $('sbcHint').textContent = `${a.company.name} pays about ${pct(a.base.sbc_pct)} of revenue in shares. Reported cash flow ignores this cost.`;
  document.querySelectorAll('#sbcSeg button').forEach((btn) => btn.classList.toggle('on', (btn.dataset.v === '1') === state.countSbc));
  if (m) {
    $('mEff').textContent = state.countSbc
      ? `Margin used in the model: ${pct(m.margin_used)} (reported ${pct(state.a.fcf_margin)} minus ${pct(a.base.sbc_pct)} stock pay)`
      : `Margin used in the model: ${pct(m.margin_used)} (stock pay ignored)`;
  }
  const edited = SLIDERS.some(([, key]) => state.a[key] !== s[key]) || !state.countSbc;
  $('edited').hidden = !edited;
  $('reset').disabled = !edited;
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
  const s = m.scenarios;
  const card = (cls, label, value, note, color) => el('div', { class: `scen-card ${cls}` },
    el('small', {}, label), el('b', color ? { style: `color:${color}` } : {}, money(value, cur)), el('small', {}, note));
  fill($('scen'),
    card('bear', 'Bear', s.bear, 'weaker growth and margin, higher discount rate', 'var(--bad)'),
    card('base', 'Base', s.base, `growth ${pct(state.a.growth)}, margin ${pct(state.a.fcf_margin)}`),
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
}

function renderImplied(a, m) {
  if (!m) return;
  const cur = a.company.currency;
  const imp = m.implied_growth;
  const off = imp == null;
  $('impBig').textContent = off ? 'Off the chart' : `${pct(imp)} a year`;
  $('impSub').textContent = off
    ? "No realistic growth rate reaches today's price with these settings."
    : `starting growth that today's price of ${money(a.company.price, cur)} needs, fading toward ${state.a.terminal_growth}% over time`;
  $('setImp').disabled = off;

  const years = a.history.length - 1;
  const peerMedian = a.peers.medians.growth;
  const rows = [['Implied by price', imp, true], ['Your base assumption', state.a.growth, false],
    [`${a.company.name}, last ${years} ${years === 1 ? 'year' : 'years'}`, a.history_cagr, false], ['Peer median', peerMedian, false]]
    .filter(([, v]) => v != null || off);
  const scale = Math.max(...rows.map(([, v]) => Math.max(v ?? 0, 0)), 1);
  fill($('impCmp'), rows.map(([name, v, hl]) => [
    el('span', {}, name),
    el('div', { class: 't' }, el('i', { class: hl ? 'hl' : '', style: `width:${(Math.max(v ?? 0, 0) / scale) * 100}%` })),
    el('span', { class: 'v' }, v == null ? '--' : pct(v)),
  ]));

  const hist = a.history_cagr;
  const ceiling = Math.max(hist ?? -Infinity, peerMedian ?? -Infinity);
  let note;
  if (off) note = 'Treat this as a sign the price is hard to justify (or the settings are extreme).';
  else if (Number.isFinite(ceiling) && imp > ceiling + 1 && peerMedian != null && hist != null) {
    note = ['The price assumes the company will grow ', b('faster than it has recently and faster than its peers'), '. That is a demanding bet.'];
  } else if (hist != null && imp > hist + 1) note = ['The price assumes some ', b('acceleration'), " compared with the company's recent growth."];
  else if (hist != null && imp < hist - 1) note = ['The price needs ', b('less growth than the company has recently delivered'), ', which leaves some room for disappointment.'];
  else note = ['The price roughly matches ', b('recent growth'), ', so the market is not assuming anything unusual.'];
  fill($('impNote'), note);
}

function renderTornado(a, m) {
  if (!m) return;
  const cur = a.company.currency;
  const bars = m.sensitivity;
  const lo = Math.min(...bars.map((x) => x.low)) * 0.95;
  const hi = Math.max(...bars.map((x) => x.high)) * 1.05;
  const pos = (x) => ((x - lo) / (hi - lo)) * 100;
  const label = (key) => KEY_LABEL[key].charAt(0).toUpperCase() + KEY_LABEL[key].slice(1);
  fill($('tor'), bars.map((x) => [
    el('span', {}, label(x.key), el('br'), el('span', { class: 'muted small' }, `±${x.delta} pt`)),
    el('div', { class: 't' },
      el('i', { style: `left:${pos(x.low)}%;width:${pos(x.high) - pos(x.low)}%` }),
      el('u', { style: `left:${pos(m.scenarios.base)}%` }),
      el('em', { style: `left:${pos(x.low)}%;transform:translateX(-110%)` }, money(x.low, cur)),
      el('em', { style: `left:${pos(x.high)}%;padding-left:4px` }, money(x.high, cur))),
  ]));
}

function renderWacc(a, m) {
  if (!m) return;
  const cur = a.company.currency;
  $('wPV').textContent = `${money(100, cur)} received in ${state.horizon} years is worth about ${money(m.pv_of_100, cur)} today at a ${state.a.wacc.toFixed(1)}% discount rate.`;

  const w = a.suggested.wacc_breakdown;
  const rfNote = a.suggested.risk_free_source === 'fred' ? '10-year US Treasury yield (FRED)' : 'default assumption for this currency (editable)';
  const row = (name, hint, value, tot) => [
    el('span', { class: tot ? 'tot' : '' }, name, hint ? el('span', { class: 'hint' }, hint) : null),
    el('span', { class: `r${tot ? ' tot' : ''}` }, value),
  ];
  fill($('waccCalc'),
    row('Risk-free rate', rfNote, pct(w.risk_free)),
    row('+ Beta × equity risk premium', 'how jumpy the stock is × extra return investors want for owning stocks', `${w.beta.toFixed(1)} × ${pct(w.erp)}`),
    row('= Cost of equity', '', pct(w.cost_of_equity), true),
    row('Cost of debt after tax', `${pct(w.cost_of_debt_pre_tax)} interest × (1 − ${w.tax_rate.toFixed(0)}% tax)`, `${w.cost_of_debt_after_tax.toFixed(2)}%`),
    row('Mix', `market cap ${money(a.company.market_cap, cur, { compact: true })} vs debt ${money(a.base.debt, cur, { compact: true })}`,
      `${Math.round(w.equity_weight * 100)}% equity / ${Math.round(w.debt_weight * 100)}% debt`),
    row('= WACC', '', pct(w.wacc), true));

  const bar = m.sensitivity.find((x) => x.key === 'wacc');
  const base = m.scenarios.base;
  if (bar && base > 0) {
    const down = Math.round((bar.low / base - 1) * 100), up = Math.round((bar.high / base - 1) * 100);
    fill($('waccSens'), 'Why it matters: raising the rate by 1 point lowers the base fair value by ', b(money(base - bar.low, cur)),
      ` (${down}%). Lowering it by 1 point raises it by `, b(money(bar.high - base, cur)),
      ` (+${up}%). A small change in a number nobody can pin down exactly moves the answer a lot, which is why we show a range.`);
  } else fill($('waccSens'), '');
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
  scheduleRecalc();
});

for (const [id, key] of SLIDERS) {
  $(id).addEventListener('input', () => {
    if (!state.a) return;
    state.a[key] = Number($(id).value);
    if (state.a.wacc < state.a.terminal_growth + GAP) { // keep the discount rate above long-term growth
      if (key === 't') state.a.wacc = state.a.terminal_growth + GAP;
      else state.a.wacc = Math.max(state.a.wacc, state.a.terminal_growth + GAP);
    }
    $('w').min = Math.max(state.analysis.limits.wacc[0], state.a.terminal_growth + GAP);
    $('w').value = state.a.wacc;
    render();
    scheduleRecalc();
  });
}

$('sbcSeg').addEventListener('click', (e) => {
  const btn = e.target.closest('button');
  if (!btn || !state.a) return;
  state.countSbc = btn.dataset.v === '1';
  render();
  scheduleRecalc();
});

$('reset').addEventListener('click', () => {
  state.a = suggestedAssumptions(state.analysis.suggested);
  state.countSbc = true;
  syncSliders();
  render();
  scheduleRecalc();
});

$('setImp').addEventListener('click', () => {
  const imp = state.model && state.model.implied_growth;
  if (imp == null) return;
  const [lo, hi] = state.analysis.limits.growth;
  state.a.growth = Math.min(hi, Math.max(lo, Math.round(imp * 2) / 2));
  syncSliders();
  render();
  scheduleRecalc();
});

window.addEventListener('hashchange', () => {
  const t = decodeURIComponent(location.hash.slice(1));
  if (t) load(t);
});

if (location.hash.length > 1) load(decodeURIComponent(location.hash.slice(1)));
