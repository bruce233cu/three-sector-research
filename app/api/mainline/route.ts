import { NextResponse } from "next/server";

export async function GET() {
  const url = process.env.SUPABASE_URL;
  const key = process.env.SUPABASE_PUBLISHABLE_KEY;
  if (!url || !key) return NextResponse.json({ error: "mainline runtime configuration missing" }, { status: 503 });
  try {
    const response = await fetch(`${url}/functions/v1/mainline-status`, {
      headers: { apikey: key, Authorization: `Bearer ${key}` },
      cache: "no-store",
    });
    const body = await response.text();
    if (!response.ok) return NextResponse.json({ error: "mainline status unavailable" }, { status: 502 });
    return new NextResponse(body, { headers: { "content-type": "application/json; charset=utf-8", "cache-control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "mainline status unavailable" }, { status: 502 });
  }
}
