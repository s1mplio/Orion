import type { NextConfig } from "next";

// Where the Next.js server forwards API calls. The browser only ever
// talks to this site, so the backend needs no public address.
const BACKEND_URL =
  process.env.ORION_BACKEND_URL || "http://127.0.0.1:8000";

const nextConfig: NextConfig = {
  // Allow opening the dev server from any address on the local
  // network. A fixed IP breaks whenever the router reassigns it,
  // and a blocked origin leaves the page rendered but unclickable.
  allowedDevOrigins: ["127.0.0.1", "192.168.*.*"],

  // Proxy /api/* to the FastAPI backend. Keeping API calls on the
  // same HTTPS origin avoids mixed-content blocking, which is what
  // lets the camera work from a LAN address or a phone.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND_URL}/:path*`,
      },
    ];
  },

  experimental: {
    // Chat and vision wait on the model; the 30s default is too short.
    proxyTimeout: 10 * 60 * 1000,
  },
};

export default nextConfig;
