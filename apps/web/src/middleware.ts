// Protect the dashboard: once GitHub OAuth is configured, unauthenticated
// visitors are bounced to sign-in. When OAuth isn't configured yet (local dev
// before credentials are set), the gate stays open so the app is still usable.

import { auth } from "@/auth";

const AUTH_CONFIGURED = !!process.env.AUTH_GITHUB_ID;

export default auth((req) => {
  if (
    AUTH_CONFIGURED &&
    !req.auth &&
    req.nextUrl.pathname.startsWith("/dashboard")
  ) {
    const url = new URL("/api/auth/signin", req.nextUrl.origin);
    url.searchParams.set("callbackUrl", req.nextUrl.pathname);
    return Response.redirect(url);
  }
});

export const config = {
  matcher: ["/dashboard/:path*"],
};
