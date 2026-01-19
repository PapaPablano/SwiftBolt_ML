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
 * Includes cache-control headers to prevent stale data
 */
export function jsonResponse(
  data: unknown,
  status = 200,
  reqHeaders?: Headers
): Response {
  const headers: Record<string, string> = {
    ...corsHeaders,
    "Content-Type": "application/json",
    "Cache-Control": "no-cache, no-store, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
  };

  const json = JSON.stringify(data);
  const accepts = reqHeaders?.get("accept-encoding") ?? "";
  const supportsGzip = accepts.toLowerCase().includes("gzip");

  if (supportsGzip) {
    headers["Content-Encoding"] = "gzip";
    const compressed = new CompressionStream("gzip");
    const writer = compressed.writable.getWriter();
    writer.write(new TextEncoder().encode(json));
    writer.close();
    return new Response(compressed.readable, {
      status,
      headers,
    });
  }

  return new Response(json, {
    status,
    headers,
  });
}

/**
 * Creates an error response with CORS headers
 */
export function errorResponse(
  message: string,
  status = 400,
  reqHeaders?: Headers
): Response {
  return jsonResponse({ error: message }, status, reqHeaders);
}
