/** @type {import('next').NextConfig} */

const basePath = process.env.KEEP_BASE_PATH ?? ''

const nextConfig = {
  basePath: basePath,
  // expose it in env:
  env: {
    basePath,
  },
  webpack(config, { isServer, dev }) {
    // Ensures webpack config exists
    if (!config) {
      config = {};
    }

    // Modify webpack config only in development mode
    if (dev) {
      Object.defineProperty(config, 'devtool', {
        get() {
            return 'source-map';
        },
        set() {},
      });
      config.devtool = 'source-map';

      // Optionally, configure to include source maps for server-side code
      if (isServer) {
        config.devtool = 'inline-source-map';
      }
    }

    return config;
  },
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
      if (process.env.DISABLE_REDIRECTS === "true"){

      }
      let redirects = [
        {
          source: "/",
          destination: "/providers",
          permanent: true,
        }
      ];
      // Add base path redirects
      if (basePath !== '') {
        redirects = redirects.concat([
        {
          source: "/backend/:path*",
          destination: `${basePath}/backend/:path*`,
          permanent: true,
          basePath: false,
        },
        {
          source: "/api/:path*",
          destination: `${basePath}/api/:path*`,
          permanent: false,
          basePath: false,
        },
        {
          source: `${basePath}/`,
          destination: `${basePath}/providers`,
          permanent: true,
          basePath: false,
        }
      ]);
    }

    return redirects;
  },
};

module.exports = nextConfig;
