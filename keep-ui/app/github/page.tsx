'use client';
import { Title, Text } from '@tremor/react';
import Image from 'next/image';

export const dynamic = 'force-dynamic';

function InstallButton() {
  const handleInstallation = () => {
    console.log("Starting the OAuth flow...");
    window.location.href = "https://github.com/apps/keephq/installations/new";
  };

  return (
    <button onClick={handleInstallation} className="py-2 px-4 bg-blue-500 text-white rounded mt-4">
      Start Installation
      <Image src="/keep.svg" alt="Keep" width={24} height={24} className="inline-block ml-2" />
    </button>
  );
}

export default function GitHubPage() {
  return (
    <main className="flex flex-col items-center justify-center h-screen">
      <Title>To start with Keep, first install GitHub Bot</Title>
      <InstallButton />
    </main>
  )};
