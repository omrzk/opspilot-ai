/** @type {import('next').NextConfig} */
// Optional base path lets the app be hosted under a sub-path, e.g. /opspilot
// on a portfolio domain. Set NEXT_PUBLIC_BASE_PATH at build time.
const basePath = process.env.NEXT_PUBLIC_BASE_PATH || "";

const nextConfig = {
  output: "standalone",
  reactStrictMode: true,
  basePath: basePath || undefined,
  env: {
    NEXT_PUBLIC_BASE_PATH: basePath,
  },
};

export default nextConfig;
