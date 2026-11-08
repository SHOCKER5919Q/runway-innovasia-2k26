/** @type {import('next').NextConfig} */
const API = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

const nextConfig = {
  reactStrictMode: true,
  images: { unoptimized: true },
  // Proxy the API through Next in development so the browser makes
  // same-origin requests and CORS never gets in the way of a demo.
  async rewrites() {
    return [
      { source: "/api/:path*", destination: `${API}/api/:path*` },
      { source: "/public/:path*", destination: `${API}/public/:path*` },
    ];
  },
};

export default nextConfig;
