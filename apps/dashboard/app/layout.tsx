import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "OgrowNT — AI Quant System",
  description: "Private AI quant research & paper trading desk",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen font-mono antialiased">{children}</body>
    </html>
  );
}
