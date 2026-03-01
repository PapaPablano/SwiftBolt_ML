// supabase/functions/_shared/response.ts
// Standardized response helpers for all Edge Functions.

import { getCorsHeaders } from "./cors.ts";

/**
 * Returns a successful JSON response.
 * The data is returned directly (flat), not wrapped in { data: ... }.
 * This maintains backward compatibility with existing clients.
 */
export function jsonOk(
  data: unknown,
  origin: string | null,
  status = 200,
): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { ...getCorsHeaders(origin), "Content-Type": "application/json" },
  });
}

/**
 * Returns a standardized error response.
 * Always returns { error: string } — never leaks DB error details.
 */
export function jsonError(
  message: string,
  origin: string | null,
  status = 400,
  code?: string,
): Response {
  const body: Record<string, string> = { error: message };
  if (code) body.code = code;
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...getCorsHeaders(origin), "Content-Type": "application/json" },
  });
}

/**
 * Returns a 401 Unauthorized response.
 */
export function jsonUnauthorized(origin: string | null): Response {
  return jsonError("Authentication required", origin, 401, "unauthorized");
}

/**
 * Returns a 404 Not Found response.
 */
export function jsonNotFound(resource: string, origin: string | null): Response {
  return jsonError(`${resource} not found`, origin, 404, "not_found");
}

/**
 * Returns a 500 Internal Server Error response.
 * Logs the actual error internally.
 */
export function jsonServerError(
  err: unknown,
  origin: string | null,
  context: string,
): Response {
  console.error(`[${context}] Internal error:`, err);
  return jsonError("An internal error occurred", origin, 500, "internal_error");
}
