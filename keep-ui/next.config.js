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
        hostname: "s.gravatar.com"
      },
      {
        protocol: "https",
        hostname: "avatar.vercel.sh"
      }
    ],
  },
  experimental: {
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
  rewrites: async () => {
    return {
      beforeFiles: [
        {
          source: "/backend/:slug*",
          destination: process.env.API_URL + "/:slug*",
        },
      ],
    };
  },
};

module.exports = nextConfig;
