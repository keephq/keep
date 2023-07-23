/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  images: {
    domains: [
      "avatars.githubusercontent.com",
      "avatar.vercel.sh",
      "lh3.googleusercontent.com",
    ],
    remotePatterns: [
      {
        protocol: "https",
        hostname: "lh3.googleusercontent.com",
      },
      {
        protocol: "https",
        hostname: "avatars.githubusercontent.com",
      },
    ],
  },
  experimental: {
    appDir: true,
    serverComponentsExternalPackages: ["@tremor/react"],
  },
  compiler: {
    removeConsole:
      process.env.NODE_ENV === "production"
        ? {
            exclude: ["error"],
          }
        : false,
},
  output: "standalone",
  productionBrowserSourceMaps: process.env.ENV === "development",
  async redirects() {
    return [
      {
        source: "/",
        destination: "/providers",
        permanent: true,
      },
    ];
  },
};

module.exports = nextConfig;
