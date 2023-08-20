import { Card, Title, Subtitle } from "@tremor/react";

export default function Layout({ children }: { children: any }) {
  return (
    <>
      <main className="p-4 md:p-10 mx-auto max-w-7xl h-full">
        <Title>Settings</Title>
        <Subtitle>Setup and configure Keep</Subtitle>
        <Card className="mt-10 p-4 md:p-10 mx-auto">{children}</Card>
      </main>
    </>
  );
}
