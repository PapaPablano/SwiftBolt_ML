// DEPRECATED: Redirects to consolidated /futures?type=chain endpoint.
// Remove after monitoring confirms zero redirect hits (1-2 weeks).

import { serve } from "https://deno.land/std@0.208.0/http/server.ts";
import { handlePreflight } from "../_shared/cors.ts";

serve((req: Request) => {
  const origin = req.headers.get("Origin");
  if (req.method === "OPTIONS") return handlePreflight(origin);

  const url = new URL(req.url);
  const params = url.searchParams;
  params.set("type", "chain");

  const base = url.origin.replace("futures-chain", "futures");
  const redirectUrl = `${url.origin}/functions/v1/futures?${params.toString()}`;

  console.warn(`[DEPRECATED] futures-chain redirect → ${redirectUrl}`);

  return new Response(null, {
    status: 301,
    headers: { Location: redirectUrl },
  });
});
