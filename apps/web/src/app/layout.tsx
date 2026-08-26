import type { Metadata } from "next";
import localFont from "next/font/local";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import "./globals.css";
import "@xyflow/react/dist/style.css";
import { SmoothScroll } from "@/components/smooth-scroll";
import { Cursor } from "@/components/cursor";
import { CommandPalette } from "@/components/command-palette";
import { Providers } from "@/components/providers";

// Clash Display — display/headline voice. Self-hosted variable woff2.
const clash = localFont({
  src: "./fonts/ClashDisplay-Variable.woff2",
  variable: "--font-clash",
  weight: "200 700",
  display: "swap",
});

export const metadata: Metadata = {
  title: "RepoPilot — the triage engineer that never sleeps",
  description:
    "RepoPilot reads every new GitHub issue the moment it lands: classifies it, scores severity, finds duplicates with cited evidence, asks for missing repro info, and routes it to an owner — then waits for your approval.",
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
  openGraph: {
    title: "RepoPilot",
    description:
      "Autonomous GitHub issue triage with human-in-the-loop approvals.",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${clash.variable} ${GeistSans.variable} ${GeistMono.variable}`}
    >
      <body className="antialiased" suppressHydrationWarning>
        <Providers>
          <Cursor />
          <CommandPalette />
          <SmoothScroll>{children}</SmoothScroll>
        </Providers>
      </body>
    </html>
  );
}
