/**
 * FastAPI Client Helper
 *
 * Provides utilities for calling FastAPI endpoints from Edge Functions.
 */

/**
 * Fetch with timeout and error handling
 */
export async function fetchWithTimeout(
  url: string,
  options: RequestInit,
  timeout = 30000,
): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeout);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    clearTimeout(timeoutId);
    return response;
  } catch (error) {
    clearTimeout(timeoutId);
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error("Request timeout");
    }
    throw error;
  }
}

/**
 * Get FastAPI base URL from environment
 */
export function getFastApiUrl(): string {
  const url = Deno.env.get("FASTAPI_URL");
  if (!url) {
    throw new Error(
      "FASTAPI_URL environment variable not set. Set it in Supabase Dashboard → Edge Functions → Environment Variables",
    );
  }
  return url;
}

/**
 * Call FastAPI endpoint with error handling
 */
export async function callFastApi<T>(
  endpoint: string,
  options: RequestInit = {},
  timeout = 30000,
): Promise<T> {
  const baseUrl = getFastApiUrl();
  const url = `${baseUrl}${endpoint}`;

  console.log(`[FastAPI] Calling ${url}`);

  try {
    const response = await fetchWithTimeout(
      url,
      {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...options.headers,
        },
      },
      timeout,
    );

    if (!response.ok) {
      let errorMessage = `HTTP ${response.status}`;
      try {
        const errorData = await response.json();
        errorMessage = errorData.detail || errorData.error || errorMessage;
      } catch {
        // If JSON parsing fails, use status text
        errorMessage = response.statusText || errorMessage;
      }
      throw new Error(errorMessage);
    }

    return await response.json() as T;
  } catch (error) {
    console.error(`[FastAPI] Error calling ${url}:`, error);
    if (error instanceof Error) {
      throw error;
    }
    throw new Error(`FastAPI request failed: ${String(error)}`);
  }
}
