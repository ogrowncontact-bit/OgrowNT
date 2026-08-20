/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  // Dev-server-only: lets a local browser-based verification tool (e.g.
  // Playwright hitting 127.0.0.1) load HMR/static chunks in this sandboxed
  // environment. No effect on production builds -- allowedDevOrigins is a
  // `next dev` safety check only.
  allowedDevOrigins: ["127.0.0.1", "localhost"],
};

export default nextConfig;
