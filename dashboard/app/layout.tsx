import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "aidustrial — Adrar Operations Command",
  description:
    "Agentic operations layer for the Baladna Algeria integrated dairy complex, Adrar Province.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
