/**
 * k6 load test for RepoPilot API.
 * Usage: k6 run scripts/load-test.js -e API_URL=https://repopilot-api.fly.dev
 *
 * Targets: p95 latency < 500ms for health, < 2000ms for internal endpoints.
 */
import http from "k6/http";
import { check, sleep } from "k6";
import { Rate, Trend } from "k6/metrics";

const errorRate = new Rate("errors");
const healthLatency = new Trend("health_latency");
const internalLatency = new Trend("internal_latency");

export const options = {
  stages: [
    { duration: "30s", target: 20 },
    { duration: "60s", target: 50 },
    { duration: "30s", target: 0 },
  ],
  thresholds: {
    errors: ["rate<0.01"],
    health_latency: ["p(95)<500"],
    internal_latency: ["p(95)<2000"],
  },
};

const BASE = __ENV.API_URL || "http://localhost:8000";
const KEY = __ENV.INTERNAL_API_KEY || "";

export default function () {
  // Health check (public)
  const h = http.get(`${BASE}/healthz`);
  check(h, { "health 200": (r) => r.status === 200 });
  healthLatency.add(h.timings.duration);
  errorRate.add(h.status !== 200);

  // Internal API (gated)
  if (KEY) {
    const r = http.get(`${BASE}/api/v1/repos`, {
      headers: { "X-Internal-Key": KEY },
    });
    check(r, { "repos 200": (r) => r.status === 200 });
    internalLatency.add(r.timings.duration);
    errorRate.add(r.status !== 200);
  }

  sleep(0.5);
}
