import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "aidustrial, Adrar Operations Command",
  description:
    "An agentic operations layer for industrial agro-complexes. A simulated Adrar dairy twin, built from published Baladna Algeria parameters; every reading is simulated.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
