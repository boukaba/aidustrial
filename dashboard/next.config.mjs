/** @type {import('next').NextConfig} */
const nextConfig = {
  // The dashboard is entirely client-side; export it as static files so the
  // FastAPI service can serve it from the same origin as the WebSocket. This
  // is what makes the public demo one URL instead of two services.
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
