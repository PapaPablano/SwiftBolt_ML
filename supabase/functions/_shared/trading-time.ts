/**
 * Trading time utilities — shared across live trading executor.
 * All times use America/New_York timezone for US equity market alignment.
 */

/**
 * Get midnight ET for today. Uses Intl.DateTimeFormat for automatic EST/EDT handling.
 * Used by: handleSummary (date filter), checkDailyLossLimit (daily P&L boundary).
 */
export function getETStartOfDay(): Date {
  const now = new Date();
  const etFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = etFormatter.formatToParts(now);
  const year = parts.find((p) => p.type === "year")?.value;
  const month = parts.find((p) => p.type === "month")?.value;
  const day = parts.find((p) => p.type === "day")?.value;
  // America/New_York handles EST/EDT automatically
  return new Date(`${year}-${month}-${day}T00:00:00`);
}

/**
 * Get next market open time (9:30 AM ET next weekday).
 */
export function nextMarketOpen(): Date {
  const now = new Date();
  const etStr = now.toLocaleString("en-US", { timeZone: "America/New_York" });
  const etNow = new Date(etStr);
  const day = etNow.getDay();
  const hours = etNow.getHours();
  const minutes = etNow.getMinutes();
  const timeMinutes = hours * 60 + minutes;

  // If before 9:30 on a weekday, next open is today 9:30
  if (day >= 1 && day <= 5 && timeMinutes < 570) {
    const today = getETStartOfDay();
    today.setHours(9, 30, 0, 0);
    return today;
  }

  // Otherwise, next weekday 9:30
  let daysUntilOpen = 1;
  const nextDay = (day + 1) % 7;
  if (nextDay === 0) daysUntilOpen = 2; // Sunday → Monday
  else if (nextDay === 6) daysUntilOpen = 3; // Saturday → Monday

  const nextOpen = new Date(
    now.getTime() + daysUntilOpen * 24 * 60 * 60 * 1000,
  );
  const formatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const p = formatter.formatToParts(nextOpen);
  const y = p.find((pp) => pp.type === "year")?.value;
  const m = p.find((pp) => pp.type === "month")?.value;
  const d = p.find((pp) => pp.type === "day")?.value;
  return new Date(`${y}-${m}-${d}T09:30:00`);
}

/**
 * Get end of trading day (midnight ET tonight).
 */
export function endOfTradingDay(): Date {
  const tomorrow = new Date(Date.now() + 24 * 60 * 60 * 1000);
  const etFormatter = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/New_York",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  });
  const parts = etFormatter.formatToParts(tomorrow);
  const year = parts.find((p) => p.type === "year")?.value;
  const month = parts.find((p) => p.type === "month")?.value;
  const day = parts.find((p) => p.type === "day")?.value;
  return new Date(`${year}-${month}-${day}T00:00:00`);
}
