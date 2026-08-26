// Lightweight liveness check for the status pill. Server-side pings the API's
// root health endpoint so the browser never touches the backend directly.

const API_URL = process.env.API_URL ?? "http://localhost:8000";

export async function GET() {
  try {
    const res = await fetch(`${API_URL}/healthz`, { cache: "no-store" });
    return Response.json({ ok: res.ok }, { status: res.ok ? 200 : 503 });
  } catch {
    return Response.json({ ok: false }, { status: 503 });
  }
}
