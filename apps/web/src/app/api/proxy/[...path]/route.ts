// Auth-aware BFF relay to the FastAPI backend. Verifies the Auth.js session
// server-side, then forwards to the API with the shared internal key and the
// signed-in user's GitHub login. The browser never reaches the API directly;
// API_URL and INTERNAL_API_KEY stay server-only. SSE bodies stream through.

import { NextRequest } from "next/server";
import { auth } from "@/auth";

const API_URL = process.env.API_URL ?? "http://localhost:8000";
const INTERNAL_KEY = process.env.INTERNAL_API_KEY ?? "";

async function relay(req: NextRequest, path: string[]): Promise<Response> {
  const session = await auth();
  const target = `${API_URL}/api/v1/${path.join("/")}${req.nextUrl.search}`;

  const headers: Record<string, string> = {
    "content-type": req.headers.get("content-type") ?? "application/json",
  };
  if (INTERNAL_KEY) headers["x-internal-key"] = INTERNAL_KEY;
  if (session?.user?.login) headers["x-user-login"] = session.user.login;

  const res = await fetch(target, {
    method: req.method,
    headers,
    body:
      req.method === "GET" || req.method === "HEAD"
        ? undefined
        : await req.text(),
    // @ts-expect-error duplex is required by node fetch for streamed bodies
    duplex: "half",
    cache: "no-store",
  });
  return new Response(res.body, {
    status: res.status,
    headers: {
      "content-type": res.headers.get("content-type") ?? "application/json",
      "cache-control": "no-cache",
    },
  });
}

type Ctx = { params: Promise<{ path: string[] }> };

export async function GET(req: NextRequest, ctx: Ctx) {
  return relay(req, (await ctx.params).path);
}
export async function POST(req: NextRequest, ctx: Ctx) {
  return relay(req, (await ctx.params).path);
}
export async function PATCH(req: NextRequest, ctx: Ctx) {
  return relay(req, (await ctx.params).path);
}
