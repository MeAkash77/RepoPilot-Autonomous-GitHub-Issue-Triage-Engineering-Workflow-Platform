// Auth.js v5 — real GitHub sign-in via the repopilot-gh GitHub App's user
// OAuth. JWT sessions (no DB table needed); the GitHub login is carried in the
// token and forwarded to the API by the BFF proxy.

import NextAuth from "next-auth";
import GitHub from "next-auth/providers/github";

export const { handlers, auth, signIn, signOut } = NextAuth({
  providers: [
    GitHub({
      clientId: process.env.AUTH_GITHUB_ID,
      clientSecret: process.env.AUTH_GITHUB_SECRET,
      authorization: { params: { scope: "read:user" } },
    }),
  ],
  session: { strategy: "jwt" },
  callbacks: {
    async jwt({ token, profile }) {
      if (profile?.login) token.login = profile.login as string;
      return token;
    },
    async session({ session, token }) {
      if (token.login) session.user.login = token.login as string;
      return session;
    },
    async redirect({ url, baseUrl }) {
      // Honor explicit callbackUrl if it's on this origin.
      if (url.startsWith(baseUrl) && url !== baseUrl && url !== `${baseUrl}/`)
        return url;
      if (url.startsWith("/") && url !== "/") return `${baseUrl}${url}`;
      // Default: post-install OAuth and bare sign-in both land on dashboard.
      return `${baseUrl}/dashboard`;
    },
  },
});
