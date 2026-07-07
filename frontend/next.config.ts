import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Emit a self-contained server bundle so the Docker image
  // doesn't need node_modules at runtime.
  output: "standalone",
};

export default nextConfig;
