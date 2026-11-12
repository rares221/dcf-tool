// Every monetary value on the page goes through money(): the currency is the asset's trading currency.
export function money(amount, currency, { compact = false } = {}) {
  if (amount == null || !Number.isFinite(amount)) return '–';
  const opts = { style: 'currency', currency };
  if (compact) {
    opts.notation = 'compact';
    opts.minimumFractionDigits = 0;
    opts.maximumFractionDigits = 1;
  } else if (Math.abs(amount) >= 100) {
    opts.minimumFractionDigits = 0;
    opts.maximumFractionDigits = 0;
  }
  try {
    return new Intl.NumberFormat(undefined, opts).format(amount);
  } catch {
    // Unknown currency code: show the code instead of guessing a symbol.
    return `${currency} ${amount.toFixed(Math.abs(amount) >= 100 ? 0 : 2)}`;
  }
}

export function pct(value, digits = 1) {
  if (value == null || !Number.isFinite(value)) return '–';
  return `${value.toFixed(digits)}%`;
}

export function freshness(ageSeconds) {
  if (ageSeconds < 60) return 'Data fetched just now';
  if (ageSeconds < 3600) return `Data fetched ${Math.round(ageSeconds / 60)} min ago`;
  if (ageSeconds < 86400) return `Data fetched ${Math.round(ageSeconds / 3600)} h ago`;
  return `Data fetched ${Math.round(ageSeconds / 86400)} days ago`;
}
