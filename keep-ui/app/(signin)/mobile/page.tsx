// page.tsx - Server Component
import { Card, Title, Text } from "@tremor/react";
import { GithubButton } from "./GithubButton";
import "../../globals.css";
import Image from "next/image";

export default function MobileLanding() {
  return (
    <main className="min-h-screen bg-gray-50 p-6">
      <Card
        className="max-w-md mx-auto flex flex-col items-center justify-center space-y-6 h-[80vh]"
        decoration="top"
        decorationColor="orange"
      >
        {/* Logo/Icon Section */}
        <Image
          src="https://cdn.prod.website-files.com/66adeb018210ff2165886994/66adf6e44b8335a91b6f6b1d_image%201.png"
          alt="Keep Logo"
          width={128}
          height={128}
          priority
          className="object-contain"
        />

        {/* Main Message */}
        <Title className="text-center">Mobile Support Coming Soon!</Title>

        {/* Description */}
        <Text className="text-center">
          We're not supporting mobile devices yet, but we're working on it!
        </Text>

        {/* GitHub Button - Now a client component */}
        <GithubButton />

        {/* Desktop Alternative */}
        <Text className="text-sm text-gray-500 text-center">
          Want to try it now? Visit us on your desktop browser!
        </Text>
      </Card>
    </main>
  );
}
