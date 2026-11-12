import { b, el, fill } from './dom.js';
import { hydrate } from './glossary.js';
import { ageText, freshness, money, pct } from './format.js';

const $ = (id) => document.getElementById(id);

// A malformed hash such as #%E0%A4%A must not throw: fall back to the raw text.
function hashTicker() {
  const raw = location.hash.slice(1);
  try { return decodeURIComponent(raw); } catch { return raw; }
}

const state = {
  analysis: null,   // /api/analyze payload
  model: null,      // /api/model payload for the current inputs
  horizon: 5,
  countSbc: true,
  a: null,          // current assumptions {growth, fcf_margin, wacc, terminal_growth}
  loadSeq: 0,       // newest analyze request
  seq: 0,           // newest model request; older responses are dropped
  peerSeq: 0,       // newest peer reload
  ticker: '',       // what the user asked for (shown in messages)
  loading: false,
  peers: [],        // peer tickers currently compared (excluding the company itself)
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
const term = (key, label) => el('span', { 'data-g': key }, label);
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
  ++state.peerSeq; // a peer reload for the previous company must not land on this one
  state.ticker = raw;
  state.loading = true;
  $('ticker').value = raw;
  render();
  const analysis = await getJson(`/api/analyze?ticker=${encodeURIComponent(raw)}`);
  if (mine !== state.loadSeq) return;
  state.loading = false;
  state.analysis = analysis;
  state.model = null;
  state.peers = (analysis.peers?.rows ?? []).slice(1).map((r) => r.ticker);
  fill($('peerMsg'), '');
  if (analysis.suggested) {
    state.a = suggestedAssumptions(analysis.suggested);
    state.countSbc = true;
    state.horizon = 5;
    syncSliders();
  } else {
    state.a = null;
  }
  render();
  if (analysis.suggested) recalc();
}

function go(ticker) {
  if (hashTicker() === ticker) load(ticker);
  else location.hash = encodeURIComponent(ticker);
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
const CARDS = ['company', 'takeaway', 'scenCard', 'impCard', 'assumpRow', 'waccCard', 'peersCard', 'histRow', 'sources'];
const CONTEXT_ONLY = ['company', 'peersCard', 'histRow', 'sources'];
const HAS_CONTEXT = new Set(['bank', 'loss_making', 'insufficient_data']); // no fair value, but history and peers still shown

function showCards(ids) {
  for (const id of CARDS) $(id).hidden = !ids.includes(id);
}

function render() {
  const a = state.analysis;
  fill($('blocker'));
  fill($('banners'));
  fill($('statePanel'));
  if (state.loading) { $('main').hidden = true; fill($('blocker'), loadingPanel()); return; }
  if (!a) { $('main').hidden = true; return; }
  const usable = USABLE.has(a.status);
  if (!usable && !HAS_CONTEXT.has(a.status)) { $('main').hidden = true; fill($('blocker'), blockerFor(a)); return; }
  $('main').hidden = false;
  if (!usable) {
    showCards(CONTEXT_ONLY);
    $('flagsCard').hidden = true;
    renderCompany(a);
    renderPeers(a);
    renderHistory(a);
    fill($('banners'), bannersFor(a));
    fill($('statePanel'), declinedPanel(a));
    hydrate();
    return;
  }
  showCards(CARDS);
  $('flagsCard').hidden = false;
  fill($('banners'), bannersFor(a));
  renderCompany(a);
  document.querySelectorAll('#pills button').forEach((btn) => btn.classList.toggle('on', Number(btn.dataset.n) === state.horizon));
  const m = state.model && state.model.status === 'ok' ? state.model : null;
  const failed = state.model != null && !m; // the model call came back as an error or a validation failure
  for (const id of ['impCard', 'torCard', 'waccCard']) $(id).hidden = !m;
  renderAssumptions(a, m);
  renderTakeaway(a, m, failed);
  renderScenarios(a, m, failed);
  renderImplied(a, m);
  renderTornado(a, m);
  renderWacc(a, m);
  renderPeers(a);
  renderHistory(a);
  renderFlags(a, m);
  hydrate();
}

// ---------- states and banners ----------
const DISCLAIMER = 'This page is an educational estimate, not financial advice.';
const CLAMP_LABEL = { growth: 'revenue growth', fcf_margin: 'FCF margin', wacc: 'discount rate' };
const retryButton = () => el('button', { type: 'button', class: 'mb', 'data-retry': '' }, 'Retry');

function loadingPanel() {
  return el('div', { class: 'card', role: 'status' },
    el('h1', {}, `Analyzing ${state.ticker}…`),
    el('p', { class: 'muted small', style: 'margin:4px 0 12px' }, 'Fetching statements, price and peers. The first lookup of a ticker takes a few seconds; repeat lookups are faster.'),
    el('div', { class: 'sk', style: 'width:60%' }), el('div', { class: 'sk', style: 'height:60px' }),
    el('div', { class: 'sk', style: 'width:85%' }), el('div', { class: 'sk', style: 'width:40%' }));
}

function blockerFor(a) {
  const panel = (title, ...children) => el('div', { class: 'card state' }, el('h1', {}, title), ...children,
    el('p', { class: 'small muted' }, DISCLAIMER));
  if (a.status === 'not_found') {
    return panel(`We couldn't find "${state.ticker}"`,
      el('p', { class: 'muted' }, "The ticker doesn't match any listed company in our data source."),
      el('h2', {}, 'What you can try'),
      el('ul', {},
        a.suggestions.length ? el('li', {}, 'Closest matches: ', a.suggestions.map((t) => el('button', { type: 'button', class: 'chip', 'data-ticker': t }, t))) : null,
        el('li', {}, 'Tickers for non-US exchanges need a suffix, for example ', b('SAP.DE')),
        el('li', {}, 'Nothing else is shown, so there is no half-empty analysis to misread')));
  }
  if (a.status === 'no_fx') {
    const c = a.company;
    return panel(`${c.name}: we can't convert the reported figures reliably`,
      el('p', { class: 'muted' }, `This stock trades in ${c.currency} but reports its financial statements in ${c.statement_currency}, and we couldn't get a reliable ${c.statement_currency} to ${c.currency} exchange rate. Showing numbers without converting them would be wrong, so no fair value is shown.`),
      el('p', {}, retryButton()));
  }
  return panel('Something went wrong on our side',
    el('p', { class: 'muted' }, "We couldn't get data for this ticker right now. The data provider may be busy or down. Please try again in a moment."),
    el('p', {}, retryButton()));
}

function declinedPanel(a) {
  const name = a.company.name;
  const copy = {
    bank: [`${name}: this type of company needs a different model`,
      'Banks and insurers earn money by lending and investing other people\'s money, so "free cash flow" does not mean what it does for other companies. Valuing them properly needs a different method (dividends or excess returns) that this tool does not support yet.'],
    loss_making: [`${name}: a DCF would be misleading here`,
      'It had negative free cash flow in the latest year or in several of the last years. A standard DCF built on negative or tiny cash flow gives meaningless or extreme values, and a precise-looking number would be worse than none.'],
    insufficient_data: a.notes.includes('shares_missing')
      ? [`${name}: no share count available`,
        'We could not find a share count or a market cap for this company, so a value per share cannot be calculated.']
      : [`${name}: not enough history for a DCF`,
        'We found fewer than 2 years of financial statements, which is not enough to project a company\'s cash flow with any confidence.'],
  }[a.status];
  return el('div', { class: 'card state' }, el('h1', {}, copy[0]), el('p', { class: 'muted', style: 'margin:0 0 10px' }, copy[1]),
    el('h2', {}, 'What you can still see'),
    el('ul', {}, el('li', {}, 'The track record and the peer comparison below'), el('li', {}, 'No fair value range is shown')),
    el('p', { class: 'small muted' }, DISCLAIMER));
}

function bannersFor(a) {
  const notes = a.notes, c = a.company, out = [];
  const banner = (...children) => out.push(el('div', { class: 'banner', role: 'status' }, ...children));
  if (notes.includes('stale')) {
    banner(b('Data may be old.'), ` This was last updated ${ageText(a.data_age_seconds)}, because the data provider was unavailable. `, retryButton());
  }
  const missing = [];
  if (notes.includes('years_missing')) missing.push(`only ${a.history.length} years of statements were available`);
  if (notes.includes('beta_missing')) missing.push('beta was unavailable (1.0 is assumed)');
  if (notes.includes('tax_missing') || notes.includes('interest_missing')) missing.push('the tax rate or cost of debt was unavailable (defaults are used)');
  if (notes.includes('sbc_missing')) missing.push('no stock-based pay data was found (treated as zero)');
  if (notes.includes('shares_missing')) missing.push('the share count was unavailable');
  if (missing.length) {
    banner(b('Some data is missing:'), ` ${missing.join('; ')}. Treat the range as rougher than usual. `, retryButton());
  }
  if (notes.includes('non_us')) {
    banner(b(`${c.ticker} trades in ${c.currency}.`), ` Prices and fair values are shown in ${c.currency}, the currency this stock trades in. The discount rate starts from assumed defaults for this currency (risk-free rate and risk premium); move the discount rate slider if you disagree.`);
  }
  if (notes.includes('fx_converted') && a.fx) {
    banner(b('Currency conversion:'), ` the company reports in ${a.fx.from}. Reported figures were converted to ${a.fx.to} at ${Number(a.fx.rate.toPrecision(4))} (the current exchange rate), because the stock trades in ${a.fx.to}.`);
  }
  const clamped = notes.filter((n) => n.startsWith('suggestion_clamped:')).map((n) => CLAMP_LABEL[n.split(':')[1]]).filter(Boolean);
  if (clamped.length) {
    banner(b('Outside the usual range:'), ` the suggested ${clamped.join(' and ')} for this company is outside the slider range, so it was limited to the edge of the range. Treat the result with extra care.`);
  }
  return out;
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
  } else {
    $('mEff').textContent = '';
  }
  const edited = SLIDERS.some(([, key]) => state.a[key] !== s[key]) || !state.countSbc;
  $('edited').hidden = !edited;
  $('reset').disabled = !edited;
}

function renderTakeaway(a, m, failed) {
  const node = $('takeaway');
  if (failed) {
    fill(node, el('p', { style: 'margin:0' }, "We couldn't recalculate these numbers just now. ",
      el('button', { type: 'button', class: 'mb', 'data-retry-model': '' }, 'Retry')),
    el('span', { class: 'fine' }, 'Educational estimate, not financial advice.'));
    return;
  }
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

function renderScenarios(a, m, failed) {
  const cur = a.company.currency, price = a.company.price;
  $('pxLabel').textContent = `Price ${money(price, cur)}`;
  for (const id of ['bar', 'scale', 'verdict']) $(id).hidden = !m;
  if (!m) {
    fill($('scen'), el('p', { class: 'muted' }, failed ? 'Not available right now.' : 'Calculating…'));
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

  if (s.bull <= 0) { // every case floors at zero: the debt outweighs the projected cash
    fill($('verdict'), "These assumptions give a value of zero per share: the company's debt is larger than the cash we project it will generate. ",
      'A DCF cannot put a positive price on that, so check the debt and cash flow figures in the track record before relying on this result.');
    return;
  }
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
    row(['+ ', term('beta', 'Beta'), ' × ', term('erp', 'equity risk premium')], 'how jumpy the stock is × extra return investors want for owning stocks', `${w.beta.toFixed(1)} × ${pct(w.erp)}`),
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


const PEER_METRICS = [
  { k: 'market_cap', name: 'Market cap', hint: 'size', fmt: (v, cur) => money(v, cur, { compact: true }) },
  { k: 'growth', name: 'Revenue growth', hint: 'last year', fmt: (v) => pct(v) },
  { k: 'fcf_margin', name: 'FCF margin', hint: 'cash kept per 100 of sales', fmt: (v) => pct(v) },
  { k: 'fcf_yield', name: 'FCF yield', hint: 'cash earned ÷ price, higher = cheaper', fmt: (v) => pct(v) },
  { k: 'forward_pe', name: 'Forward P/E', hint: 'price ÷ earnings, higher = pricier', fmt: (v) => `${v.toFixed(1)}x` },
  { k: 'beta', name: 'Beta', hint: '1 = moves with market', fmt: (v) => v.toFixed(1) },
];

function renderPeers(a) {
  const cur = a.company.currency, subject = a.company.ticker;
  const rows = a.peers.rows;
  fill($('chips'),
    el('span', { class: 'chip' }, `${subject} (you)`),
    state.peers.map((t) => el('span', { class: 'chip' }, t, el('button', { type: 'button', 'aria-label': `Remove ${t}` }, '×'))),
    el('button', { type: 'button', class: 'chip add', id: 'addPeerBtn' }, '+ add ticker'));

  const cell = (v, m) => (v == null ? el('span', { class: 'muted' }, 'n/a') : m.fmt(v, cur));
  const head = el('tr', {}, el('th', {}, 'Metric'),
    rows.map((r, i) => el('th', { class: i === 0 ? 'me' : '' }, r.ticker)),
    el('th', {}, 'Peer median'), el('th', {}, `${subject} vs peers`));
  const body = PEER_METRICS.map((m) => {
    const reading = a.peers.readings[m.k];
    const text = reading.label === '' ? '–' : reading.diff_pct == null || reading.label === 'in line' ? reading.label
      : `${reading.label} (${reading.diff_pct > 0 ? '+' : ''}${Math.round(reading.diff_pct)}%)`;
    return el('tr', {},
      el('td', {}, m.name, el('span', { class: 'hint' }, m.hint)),
      rows.map((r, i) => el('td', { class: i === 0 ? 'me' : '' }, cell(r[m.k], m))),
      el('td', {}, cell(a.peers.medians[m.k], m)),
      el('td', {}, text));
  });
  fill($('peers'), head, body);

  const medG = a.peers.medians.growth, medM = a.peers.medians.fcf_margin;
  if (!state.a) {
    fill($('peerNote'), 'Peers are shown for context only.');
  } else if (rows.length < 2 || medG == null) {
    fill($('peerNote'), 'No peers loaded. Add tickers above to compare.');
  } else {
    const verdict = state.a.growth > medG * 1.15 ? 'You are assuming faster growth than most peers, so be ready to explain why.'
      : state.a.growth < medG * 0.85 ? 'You are assuming slower growth than most peers, which is cautious.' : 'That is in line with peers.';
    fill($('peerNote'), 'Your base growth assumption is ', b(`${state.a.growth}%`), ' against a peer median of ', b(pct(medG)),
      medM == null ? '. ' : [', and your margin assumption is ', b(`${state.a.fcf_margin}%`), ' against ', b(pct(medM)), '. '], verdict);
  }
}

function renderHistory(a) {
  const cur = a.company.currency;
  $('histTitle').textContent = `Track record (last ${a.history.length} years)`;
  const maxRev = Math.max(...a.history.map((h) => h.revenue));
  fill($('hist'), a.history.map((h) => el('div', { class: 'col' },
    el('div', { class: 'plot' }, el('i', { style: `height:${(h.revenue / maxRev) * 86}px` })),
    el('div', { class: 'lab' }, String(h.year), el('b', {}, money(h.revenue, cur, { compact: true })),
      `${pct(h.fcf_margin, 0)} FCF margin`, el('br'), `${pct(h.fcf_margin_after_sbc, 0)} after stock pay`))));
}

function renderFlags(a, m) {
  const cur = a.company.currency;
  const items = [];
  const li = (cls, ...children) => items.push(el('li', { class: cls }, ...children));
  if (m) {
    const share = Math.round(m.terminal_share * 100);
    li(share > 65 ? 'mid-c' : 'ok', term('tv', 'Terminal value'), ' is ', b(`${share}%`),
      ' of the base estimate. ', share > 65 ? 'Most of the answer depends on what happens after the forecast period.' : 'The answer does not lean too heavily on the far future.');
  }
  const negative = a.history.filter((h) => h.fcf_margin != null && h.fcf_margin < 0).length;
  if (negative === 0) li('ok', term('fcf', 'Free cash flow'), ` was positive in all ${a.history.length} years, so a DCF is a reasonable tool here.`);
  else li('mid-c', term('fcf', 'Free cash flow'), ` was negative in ${negative} of the last ${a.history.length} years, so treat the result with extra caution.`);
  if (m) {
    const pctRev = pct(a.base.sbc_pct);
    if (state.countSbc) {
      li('ok', term('sbc', 'Stock-based pay'), ` (about ${pctRev} of revenue) is counted as a cost. Ignoring it would raise the base estimate by about ${money(m.sbc_effect, cur)} a share.`);
    } else {
      li('mid-c', term('sbc', 'Stock-based pay'), ` (about ${pctRev} of revenue) is `, b('not counted'), ', which flatters the estimate by about ', b(money(m.sbc_effect, cur)), ' a share.');
    }
  }
  const sg = a.share_growth;
  if (sg != null) {
    const n = a.history.length - 1;
    if (sg > 0.5) {
      li('mid-c', `Share count grew about ${pct(sg)} a year over the last ${n} years (`, term('dilution', 'dilution'), "), so each share's slice is shrinking. ",
        state.countSbc ? 'Counting stock pay as a cost is how the model accounts for this.' : 'Counting stock pay as a cost would account for this.');
    } else if (sg < -0.5) {
      li('ok', `Share count fell about ${pct(Math.abs(sg))} a year over the last ${n} years (buybacks), so each share's slice is growing.`);
    } else {
      li('ok', 'Share count has been roughly stable, so there is little ', term('dilution', 'dilution'), '.');
    }
  }
  li('mid-c', 'Analyst growth estimates are not available on free sources, so growth here is history-based.');
  li('muted', 'Banks, insurers and companies with negative cash flow show a "DCF is a poor fit" message instead of a number.');
  fill($('flags'), items);
}

// ---------- events ----------
$('search').addEventListener('submit', (e) => {
  e.preventDefault();
  const t = $('ticker').value.trim().toUpperCase();
  if (!t) return;
  go(t);
});

document.addEventListener('click', (e) => {
  if (e.target.closest('[data-retry-model]')) { recalc(); return; }
  const chip = e.target.closest('#blocker [data-ticker]');
  if (chip) { go(chip.dataset.ticker); return; }
  if (e.target.closest('[data-retry]')) load(state.ticker);
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

async function reloadPeers(tickers) {
  const mine = ++state.peerSeq;
  const requested = tickers.map((t) => t.trim().toUpperCase()).filter(Boolean);
  const url = `/api/analyze?ticker=${encodeURIComponent(state.analysis.company.ticker)}&peers=${encodeURIComponent(requested.join(','))}`;
  const result = await getJson(url);
  if (mine !== state.peerSeq || !result.peers) return;
  state.analysis.peers = result.peers;
  state.peers = result.peers.rows.slice(1).map((r) => r.ticker);
  const missing = requested.filter((t) => !state.peers.includes(t));
  fill($('peerMsg'), missing.length ? `Couldn't load ${missing.join(', ')}, so it was not added.` : '');
  render();
}

$('chips').addEventListener('click', (e) => {
  if (e.target.id === 'addPeerBtn') {
    $('addPeerRow').hidden = false;
    $('addPeer').focus();
    return;
  }
  const btn = e.target.closest('button[aria-label^="Remove "]');
  if (btn) reloadPeers(state.peers.filter((t) => t !== btn.getAttribute('aria-label').slice(7)));
});

$('addPeer').addEventListener('keydown', (e) => {
  if (e.key !== 'Enter') return;
  e.preventDefault();
  const t = $('addPeer').value.trim().toUpperCase();
  $('addPeer').value = '';
  $('addPeerRow').hidden = true;
  if (t && !state.peers.includes(t)) reloadPeers([...state.peers, t]);
});

window.addEventListener('hashchange', () => {
  const t = hashTicker();
  if (t) load(t);
});

if (location.hash.length > 1) load(hashTicker());
