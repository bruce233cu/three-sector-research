import "jsr:@supabase/functions-js/edge-runtime.d.ts";
import { createClient } from "https://esm.sh/@supabase/supabase-js@2";

const json = (body: unknown, status = 200) => new Response(JSON.stringify(body), {
  status,
  headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" },
});

Deno.serve(async (req: Request) => {
  if (req.method !== "GET") return json({ error: "method_not_allowed" }, 405);
  const supplied = req.headers.get("apikey");
  const publicKey = Deno.env.get("SUPABASE_ANON_KEY") ?? Deno.env.get("SB_PUBLISHABLE_KEY");
  // Publishable keys are intentionally browser-safe. Supabase injects the
  // legacy anon key into Functions, while Sites may use the modern format.
  const accepted = supplied && ((publicKey && supplied === publicKey) || supplied.startsWith("sb_publishable_"));
  if (!accepted) return json({ error: "unauthorized" }, 401);

  const supabase = createClient(
    Deno.env.get("SUPABASE_URL")!,
    Deno.env.get("SUPABASE_SERVICE_ROLE_KEY")!,
    { auth: { persistSession: false } },
  );
  const { data, error } = await supabase.rpc("get_mainline_phase1d_status");
  if (error) return json({ error: "mainline_query_failed" }, 500);
  return json(data);
});
