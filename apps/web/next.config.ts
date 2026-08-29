import path from "node:path";
import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Vercel's Root Directory is apps/web, but the pnpm workspace store (and
  // Prisma's generated query-engine binary inside it) lives at the repo
  // root. Without this, Next.js's output file tracing can't follow the
  // pnpm symlinks out to node_modules/.pnpm/@prisma+client.../.prisma/client,
  // so the engine binary never makes it into the serverless function bundle
  // — every prisma.* call throws PrismaClientInitializationError in prod.
  outputFileTracingRoot: path.join(__dirname, "../../"),
  // The tracer's static analysis can't follow Prisma's runtime-computed
  // require() for the platform-specific engine .node file even with the
  // root fixed above, so it has to be included explicitly. Must stay a
  // relative pattern — Next.js path.join()s this onto its own base path
  // internally, so an absolute path here silently doubles into garbage
  // like ".../apps/web/vercel/path0/..." instead of being used as-is.
  // Relative to this config file's own directory (apps/web), two levels
  // up reaches the monorepo root where the pnpm store actually lives.
  outputFileTracingIncludes: {
    "/**/*": ["../../node_modules/.pnpm/@prisma+client*/node_modules/.prisma/client/**/*"],
  },
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
