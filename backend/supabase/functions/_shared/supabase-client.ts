// Shared Supabase client for Edge Functions
// Uses Deno environment variables for configuration

import { createClient, SupabaseClient } from "https://esm.sh/@supabase/supabase-js@2";

let supabaseClient: SupabaseClient | null = null;

/**
 * Gets or creates a Supabase client using service role credentials.
 * Service role bypasses RLS for server-side operations.
 */
export function getSupabaseClient(): SupabaseClient {
  if (supabaseClient) {
    return supabaseClient;
  }

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const supabaseServiceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");

  if (!supabaseUrl || !supabaseServiceKey) {
    throw new Error(
      "Missing required environment variables: SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY"
    );
  }

  supabaseClient = createClient(supabaseUrl, supabaseServiceKey, {
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });

  return supabaseClient;
}

/**
 * Creates a Supabase client using the user's JWT token.
 * Respects RLS policies for user-specific operations.
 */
export function getSupabaseClientWithAuth(
  authHeader: string | null
): SupabaseClient {
  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const supabaseAnonKey = Deno.env.get("SUPABASE_ANON_KEY");

  if (!supabaseUrl || !supabaseAnonKey) {
    throw new Error(
      "Missing required environment variables: SUPABASE_URL or SUPABASE_ANON_KEY"
    );
  }

  return createClient(supabaseUrl, supabaseAnonKey, {
    global: {
      headers: authHeader ? { Authorization: authHeader } : {},
    },
    auth: {
      autoRefreshToken: false,
      persistSession: false,
    },
  });
}
