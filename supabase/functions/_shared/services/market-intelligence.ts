import { AlpacaClient } from "../providers/alpaca-client.ts";

export interface MarketStatus {
  isOpen: boolean;
  nextOpen: string;
  nextClose: string;
  timestamp: string;
}

export interface TradingDay {
  date: string;
  open: string;
  close: string;
  sessionOpen: string;
  sessionClose: string;
}

export interface CorporateAction {
  symbol: string;
  type: string;
  date: string;
  ratio?: number;
  amount?: number;
  metadata: any;
}

export type CorporateActionType =
  | "stock_split"
  | "reverse_split"
  | "dividend"
  | "merger"
  | "spin_off";

export class MarketIntelligence {
  private alpaca: AlpacaClient;
  private calendarCache: Map<string, TradingDay[]> = new Map();

  constructor(alpaca: AlpacaClient) {
    this.alpaca = alpaca;
  }

  async getMarketStatus(date?: Date): Promise<MarketStatus> {
    const clock = await this.alpaca.queryMarketClock();

    return {
      isOpen: clock.is_open,
      nextOpen: clock.next_open,
      nextClose: clock.next_close,
      timestamp: clock.timestamp,
    };
  }

  async getMarketCalendar(start: string, end: string): Promise<TradingDay[]> {
    const cacheKey = `${start}-${end}`;
    if (this.calendarCache.has(cacheKey)) {
      return this.calendarCache.get(cacheKey)!;
    }

    const calendar = await this.alpaca.queryMarketCalendar({
      start,
      end,
    });

    const tradingDays = calendar.map((day) => ({
      date: day.date,
      open: day.open,
      close: day.close,
      sessionOpen: day.session_open || day.open,
      sessionClose: day.session_close || day.close,
    }));

    this.calendarCache.set(cacheKey, tradingDays);
    return tradingDays;
  }

  async getCorporateActions(
    symbols: string[],
    types: CorporateActionType[] = ["stock_split", "reverse_split", "dividend"],
  ): Promise<CorporateAction[]> {
    // Map our types to Alpaca's API types
    const alpacaTypes = types.map((t) => {
      if (t === "stock_split" || t === "reverse_split") return "split";
      return t; // dividend, merger, spin_off map directly
    });

    const actions = await this.alpaca.queryCorporateActions({
      symbols: symbols.join(","),
      types: [...new Set(alpacaTypes)].join(","), // Remove duplicates
      start: this.getOneYearAgo(),
      end: this.getToday(),
    });

    return actions.map((action) => ({
      symbol: action.initiating_symbol,
      type: action.ca_type,
      date: action.ex_date,
      ratio: action.new_rate && action.old_rate
        ? action.new_rate / action.old_rate
        : undefined,
      amount: action.cash,
      metadata: action,
    }));
  }

  private getOneYearAgo(): string {
    const date = new Date();
    date.setDate(date.getDate() - 90); // Alpaca API limit is 90 days
    return date.toISOString().split("T")[0];
  }

  private getToday(): string {
    return new Date().toISOString().split("T")[0];
  }
}
