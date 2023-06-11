"use client";

import { Card, Title, Text } from "@tremor/react";
import dynamic from "next/dynamic";

const Builder = dynamic(() => import("./builder"), {
  ssr: false, // Prevents server-side rendering
});

export default function Page() {
  return (
    <main className="p-4 md:p-10 mx-auto max-w-7xl h-full">
      <Title>Builder</Title>
      <Text>Alert building kit</Text>
      <Card className="p-4 md:p-10 h-5/6 mx-auto max-w-7xl mt-6">
        <Builder />
      </Card>
    </main>
  );
}
