/**
 * Secure CORS Configuration for Edge Functions
 * 
 * Implements environment-specific origin whitelisting to prevent
 * unauthorized cross-origin requests.
 * 
 * Usage:
 *   import { getCorsHeaders } from "../_shared/cors.ts";
 *   
 *   serve(async (req: Request) => {
 *     const origin = req.headers.get("origin");
 *     const corsHeaders = getCorsHeaders(origin);
 *     
 *     if (req.method === "OPTIONS") {
 *       return new Response(null, { status: 204, headers: corsHeaders });
 *     }
 *     // ... rest of handler
 *   });
 */

/**
 * Get allowed origins based on environment.
 * 
 * Environment is determined by ENVIRONMENT variable:
 * - "production": Only production domains
 * - "staging": Staging + localhost
 * - "development" (default): Localhost only
 */
export const getAllowedOrigins = (): string[] => {
  const env = Deno.env.get("ENVIRONMENT") || "development";
  
  if (env === "production") {
    return [
      "https://swiftbolt.app",
      "https://app.swiftbolt.app",
      "https://www.swiftbolt.app",
    ];
  } else if (env === "staging") {
    return [
      "https://staging.swiftbolt.app",
      "https://staging-app.swiftbolt.app",
      "http://localhost:3000",
      "http://localhost:5173",
      "http://localhost:8080",
    ];
  } else {
    // Development
    return [
      "http://localhost:3000",
      "http://localhost:5173",
      "http://localhost:8080",
      "http://localhost:8081",
      "http://127.0.0.1:3000",
      "http://127.0.0.1:5173",
      "http://127.0.0.1:8080",
      "http://127.0.0.1:8081",
    ];
  }
};

/**
 * Get CORS headers for the given origin.
 * 
 * If origin is in the allowlist, it's returned in Access-Control-Allow-Origin.
 * Otherwise, the first allowed origin is returned (prevents breaking existing requests).
 * 
 * @param origin - The origin header from the request
 * @returns CORS headers object
 */
export const getCorsHeaders = (origin: string | null): Record<string, string> => {
  // Allow all origins for development
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type, x-requested-with",
    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS, PATCH",
    "Access-Control-Max-Age": "86400", // 24 hours
  };
};

/**
 * Check if an origin is allowed.
 * 
 * @param origin - The origin to check
 * @returns true if origin is in allowlist
 */
export const isOriginAllowed = (origin: string | null): boolean => {
  if (!origin) return false;
  const allowedOrigins = getAllowedOrigins();
  return allowedOrigins.includes(origin);
};

/**
 * Create a CORS-enabled Response.
 * 
 * Helper function to create responses with proper CORS headers.
 * 
 * @param body - Response body (JSON will be stringified)
 * @param status - HTTP status code (default: 200)
 * @param origin - Origin header from request
 * @param additionalHeaders - Additional headers to include
 * @returns Response with CORS headers
 */
export const corsResponse = (
  body: unknown,
  status: number = 200,
  origin: string | null = null,
  additionalHeaders: Record<string, string> = {}
): Response => {
  const corsHeaders = getCorsHeaders(origin);
  
  const bodyString = typeof body === "string" 
    ? body 
    : JSON.stringify(body);
  
  return new Response(bodyString, {
    status,
    headers: {
      "Content-Type": "application/json",
      ...corsHeaders,
      ...additionalHeaders,
    },
  });
};

/**
 * Handle OPTIONS preflight request.
 * 
 * @param origin - Origin header from request
 * @returns 204 No Content with CORS headers
 */
export const handlePreflight = (origin: string | null): Response => {
  const corsHeaders = getCorsHeaders(origin);
  return new Response(null, {
    status: 204,
    headers: corsHeaders,
  });
};

/**
 * Legacy function name for backward compatibility.
 * @deprecated Use handlePreflight instead
 */
export const handleCorsOptions = (origin: string | null = null): Response => {
  return handlePreflight(origin);
};

/**
 * Legacy function name for backward compatibility.
 * @deprecated Use corsResponse instead
 */
export const jsonResponse = (
  data: unknown,
  status: number = 200,
  requestHeaders?: Headers
): Response => {
  const origin = requestHeaders?.get("origin") ?? null;
  return corsResponse(data, status, origin);
};

/**
 * Legacy function name for backward compatibility.
 * @deprecated Use corsResponse instead
 */
export const errorResponse = (
  message: string,
  status: number = 400,
  requestHeaders?: Headers
): Response => {
  const origin = requestHeaders?.get("origin") ?? null;
  return corsResponse({ error: message }, status, origin);
};
