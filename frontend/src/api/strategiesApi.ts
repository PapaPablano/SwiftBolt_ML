const supabaseUrl = import.meta.env.VITE_SUPABASE_URL ?? '';
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY ?? '';
const functionsUrl = `${supabaseUrl}/functions/v1`;

async function invokeFunction(
  name: string,
  options: { method?: string; body?: unknown; token?: string }
) {
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    apikey: supabaseAnonKey,
  };
  if (options.token) headers['Authorization'] = `Bearer ${options.token}`;

  const res = await fetch(`${functionsUrl}/${name}`, {
    method: options.method ?? 'GET',
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  // #136: Surface 429 rate limit errors with actionable message
  if (res.status === 429) {
    throw new Error('rate_limited: Too many trading requests. Please wait before retrying.');
  }

  if (!res.ok) {
    const errorText = await res.text().catch(() => 'Unknown error');
    throw new Error(`${name} failed: ${res.status} ${errorText}`);
  }
  return res.json();
}

// Live Trading API (mirrors paper-trading-executor pattern)
export const liveTradingApi = {
  positions: (token: string) =>
    invokeFunction('live-trading-executor?action=positions', { token }).then(
      (d) => d.positions ?? [],
    ),

  trades: (token: string) =>
    invokeFunction('live-trading-executor?action=trades', { token }).then(
      (d) => d.trades ?? [],
    ),

  summary: (token: string) =>
    invokeFunction('live-trading-executor?action=summary', { token }),

  brokerStatus: (token: string) =>
    invokeFunction('live-trading-executor?action=broker_status', { token }),

  closePosition: (positionId: string, token: string) =>
    invokeFunction('live-trading-executor', {
      method: 'POST',
      body: { action: 'close_position', position_id: positionId },
      token,
    }),

  execute: (symbol: string, timeframe: string, token: string) =>
    invokeFunction('live-trading-executor', {
      method: 'POST',
      body: { action: 'execute', symbol, timeframe },
      token,
    }),

  disconnectBroker: (token: string) =>
    invokeFunction('live-trading-executor', {
      method: 'POST',
      body: { action: 'disconnect_broker' },
      token,
    }),
};

export const strategiesApi = {
  list: (token: string, _offset = 0) =>
    invokeFunction('strategies', { token }).then((d) => d.strategies ?? []),

  get: (id: string, token: string) =>
    invokeFunction(`strategies?id=${id}`, { token }).then((d) => d.strategy),

  create: (strategy: unknown, token: string) =>
    invokeFunction('strategies', { method: 'POST', body: strategy, token }),

  update: (id: string, strategy: unknown, token: string) =>
    invokeFunction(`strategies?id=${id}`, { method: 'PUT', body: strategy, token }),

  delete: (id: string, token: string) =>
    invokeFunction(`strategies?id=${id}`, { method: 'DELETE', token }),
};
