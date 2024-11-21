const { withSentryConfig } = require("@sentry/nextjs");

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  transpilePackages: ["next-auth"],
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
        : process.env.REMOVE_CONSOLE === "true",
  },
  output: "standalone",
  productionBrowserSourceMaps:
    process.env.ENV === "development" || process.env.SENTRY_DISABLED !== "true",
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

const sentryConfig = {
  // For all available options, see:
  // https://github.com/getsentry/sentry-webpack-plugin#options

  org: "keep-hq",
  project: "keep-ui",

  // Only print logs for uploading source maps in CI
  silent: !process.env.CI,

  // For all available options, see:
  // https://docs.sentry.io/platforms/javascript/guides/nextjs/manual-setup/

  // Automatically annotate React components to show their full name in breadcrumbs and session replay
  reactComponentAnnotation: {
    enabled: true,
  },

  // Route browser requests to Sentry through a Next.js rewrite to circumvent ad-blockers.
  // This can increase your server load as well as your hosting bill.
  // Note: Check that the configured route will not match with your Next.js middleware, otherwise reporting of client-
  // side errors will fail.
  tunnelRoute: "/monitoring",

  // Hides source maps from generated client bundles
  hideSourceMaps: true,

  // Automatically tree-shake Sentry logger statements to reduce bundle size
  disableLogger: true,

  // Enables automatic instrumentation of Vercel Cron Monitors. (Does not yet work with App Router route handlers.)
  // See the following for more information:
  // https://docs.sentry.io/product/crons/
  // https://vercel.com/docs/cron-jobs
  automaticVercelMonitors: true,
};

const isSentryDisabled =
  process.env.SENTRY_DISABLED === "true" ||
  process.env.NODE_ENV === "development";

// Compose the final config
let config = nextConfig;

// Add Sentry if enabled
if (!isSentryDisabled) {
  config = withSentryConfig(config, sentryConfig);
}

// Add Bundle Analyzer only when analysis is requested
if (process.env.ANALYZE === "true") {
  config = require("@next/bundle-analyzer")({
    enabled: true,
  })(config);
}

module.exports = config;
