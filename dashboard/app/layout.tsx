import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "aidustrial — Adrar Operations Command",
  description:
    "An agentic operations layer for industrial agro-complexes, built around the published parameters of the Baladna Algeria project, Adrar Province.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
