import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  // Pin the tracing root to this app so stray lockfiles higher up the tree are ignored.
  outputFileTracingRoot: path.join(typeof __dirname !== "undefined" ? __dirname : process.cwd()),
  eslint: {
    // Lint runs as part of `next build`; keep the codebase clean rather than skipping it.
    ignoreDuringBuilds: false,
  },
  typescript: {
    ignoreBuildErrors: false,
  },
};

export default nextConfig;
