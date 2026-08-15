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
};

export default nextConfig;
