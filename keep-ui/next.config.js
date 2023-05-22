/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    domains: [
      "avatars.githubusercontent.com",
      "avatar.vercel.sh",
      "lh3.googleusercontent.com",
    ],
    remotePatterns: [
      {
        protocol: 'https',
        hostname: 'lh3.googleusercontent.com',
      }
    ]
  },
  experimental: {
    appDir: true,
    serverComponentsExternalPackages: ["@tremor/react"],
  },
  output: "standalone",
};

module.exports = nextConfig;
