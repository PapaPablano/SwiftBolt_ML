// Shared CORS headers for Supabase Edge Functions
// Used for local development and cross-origin requests

export const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers":
    "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
};

/**
 * Creates a CORS preflight response for OPTIONS requests
 */
export function handleCorsOptions(): Response {
  return new Response(null, {
    status: 204,
    headers: corsHeaders,
  });
}

/**
 * Adds CORS headers to a JSON response
 */
export function jsonResponse(
  data: unknown,
  status = 200
): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: {
      ...corsHeaders,
      "Content-Type": "application/json",
    },
  });
}

/**
 * Creates an error response with CORS headers
 */
export function errorResponse(
  message: string,
  status = 400
): Response {
  return jsonResponse({ error: message }, status);
}
