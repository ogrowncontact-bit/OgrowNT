import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  transpilePackages: [
    "@inner/ui",
    "@inner/assessment-engine",
    "@inner/content",
    "@inner/db",
    "@inner/ai",
    "@inner/payments",
    "@inner/email",
    "@inner/pdf",
  ],
  async headers() {
    return [
      {
        // Baseline hardening applied site-wide. A full Content-Security-Policy
        // needs allowlisting Stripe/analytics script origins and belongs to a
        // dedicated pass — these headers are safe, non-breaking defaults.
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
