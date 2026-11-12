// Plain-language definitions. Elements marked data-g="<key>" get a tooltip (hover, keyboard focus, tap).
export const GLOSSARY = {
  fcf: 'Free cash flow: the cash left after running the business and paying for equipment and buildings. It is what could be paid out to owners.',
  fcfm: 'FCF margin: out of every 100 units of sales, how many turn into free cash flow.',
  tv: 'Terminal value: the value of all cash flows after the forecast period, assuming they grow at a steady long-term rate forever. It is usually most of a DCF answer.',
  beta: 'Beta: how much a stock tends to move compared with the whole market. 1 = moves with it, above 1 = jumpier, below 1 = steadier.',
  erp: 'Equity risk premium: the extra yearly return investors demand for owning stocks instead of safe government bonds.',
  wacc: "Discount rate (WACC): how hard future cash is shrunk back into today's money. Higher = riskier or more demanding investors = lower value today. Explained in detail further down.",
  ltg: 'Long-term growth: the steady rate cash flow is assumed to grow forever after the forecast period. It is normally kept near the long-run growth of the economy, around 2 to 3%.',
  sbc: 'Stock-based pay: compensation given to employees in shares. It costs existing owners, because new shares make each share a smaller slice, but it does not show up as cash leaving in free cash flow.',
  dilution: 'Dilution: when a company issues new shares, each existing share represents a smaller slice of the company.',
  impl: 'Reverse DCF: instead of estimating a value, we ask what growth the current price requires.',
  cagr: 'CAGR: compound annual growth rate, the steady yearly growth that would get you from the first number to the last.',
  horizon: 'Forecast horizon: how many years we project explicitly before assuming steady long-term growth. Longer horizons rely more on guesses.',
};

export function hydrate(root = document) {
  root.querySelectorAll('[data-g]').forEach((node) => {
    const text = GLOSSARY[node.dataset.g];
    if (!text) return;
    node.classList.add('term');
    node.setAttribute('tabindex', '0');
    node.dataset.tip = text;
  });
}
