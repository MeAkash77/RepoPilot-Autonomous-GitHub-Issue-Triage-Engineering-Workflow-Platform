import { encode } from "next-auth/jwt";
import fs from "fs";
import path from "path";

export default async function globalSetup() {
  const secret = process.env.AUTH_SECRET;
  if (!secret) return; // auth not configured — dashboard tests will fail gracefully

  const token = await encode({
    token: {
      name: "Test User",
      email: "test@example.com",
      picture: null,
      login: "testuser",
      sub: "99999999",
    },
    secret,
    salt: "authjs.session-token",
    maxAge: 60 * 60 * 24,
  });

  const state = {
    cookies: [
      {
        name: "authjs.session-token",
        value: token,
        domain: "localhost",
        path: "/",
        httpOnly: true,
        secure: false,
        sameSite: "Lax" as const,
      },
    ],
  };

  const outPath = path.join(__dirname, ".auth-state.json");
  fs.writeFileSync(outPath, JSON.stringify(state));
}
