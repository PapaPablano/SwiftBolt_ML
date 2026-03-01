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

  if (!res.ok) {
    const errorText = await res.text().catch(() => 'Unknown error');
    throw new Error(`${name} failed: ${res.status} ${errorText}`);
  }
  return res.json();
}

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
