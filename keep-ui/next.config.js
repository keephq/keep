/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "lh3.googleusercontent.com",
      },
      {
        protocol: "https",
        hostname: "avatars.githubusercontent.com",
      },
      {
        protocol: "https",
        hostname: "s.gravatar.com",
      },
      {
        protocol: "https",
        hostname: "avatar.vercel.sh",
      },
      {
        protocol: "https",
        hostname: "ui-avatars.com",
      },
    ],
  },
  compiler: {
    removeConsole: false,
  },
  output: "standalone",
  productionBrowserSourceMaps: true,
  async redirects() {
    return process.env.DISABLE_REDIRECTS === "true"
      ? []
      : [
          {
            source: "/",
            destination: "/incidents",
            permanent: process.env.ENV === "production",
          },
        ];
  },
  async headers() {
    // Allow Keycloak Server as a CORS origin since we use SSO wizard as iframe
    const keycloakIssuer = process.env.KEYCLOAK_ISSUER;
    const keycloakServer = keycloakIssuer
      ? keycloakIssuer.split("/auth")[0]
      : "http://localhost:8181";
    return [
      {
        source: "/:path*",
        headers: [
          {
            key: "Access-Control-Allow-Origin",
            value: keycloakServer,
          },
        ],
      },
    ];
  },
};

module.exports = nextConfig;
